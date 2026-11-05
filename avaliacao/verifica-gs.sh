#!/usr/bin/env bash
# =============================================================================
# verifica-gs.sh - Checklist automatico da Global Solution (FIAP Store)
# Cloud Developer II - Kubernetes e Serverless
#
# Uso:   ./avaliacao/verifica-gs.sh [https://endereco-do-ingress]
#
# - Executa SOMENTE leituras no cluster (get, auth can-i) e dois testes de
#   conexao via "kubectl exec". Nao cria, altera nem apaga nada.
# - Compativel com o bash 3.2 do macOS. Requer: kubectl e curl.
# - Pontua 80 dos 100 pontos. Os itens MANUAIS (5 pts) e os DESAFIOS AO VIVO
#   (15 pts) sao avaliados pelo professor durante a demonstracao.
# =============================================================================
set -u

APP_NS="store-prod"
DATA_NS="store-data"
URL="${1:-}"

if [ -t 1 ]; then
  VERDE=$'\033[0;32m'; VERM=$'\033[0;31m'; AMAR=$'\033[0;33m'; NEG=$'\033[1m'; FIM=$'\033[0m'
else
  VERDE=""; VERM=""; AMAR=""; NEG=""; FIM=""
fi

PONTOS=0
MAXIMO=0
FALHAS=""

k() { kubectl "$@" 2>/dev/null; }

# item <id> <pontos> <descricao> <ok:0|1> <detalhe>
item() {
  local id="$1" pts="$2" desc="$3" ok="$4" det="$5"
  MAXIMO=$((MAXIMO + pts))
  if [ "$ok" = "0" ]; then
    PONTOS=$((PONTOS + pts))
    printf "  %s[OK]   %s%-4s %-62s %2s/%-2s%s\n" "$VERDE" "$FIM" "$id" "$desc" "$pts" "$pts" ""
  else
    printf "  %s[FALHA]%s %-4s %-62s %2s/%-2s\n" "$VERM" "$FIM" "$id" "$desc" "0" "$pts"
    FALHAS="${FALHAS}${id} "
  fi
  if [ -n "$det" ]; then printf "         %s-> %s%s\n" "$AMAR" "$det" "$FIM"; fi
}

secao() { printf "\n%s%s%s\n" "$NEG" "$1" "$FIM"; }

# se_vazio <valor> <texto se vazio> <texto se preenchido>
se_vazio() { if [ -z "$1" ]; then echo "$2"; else echo "$3"; fi; }

# verdadeiro (0) se a string $1 contem a palavra $2
contem() { case " $1 " in *" $2 "*) return 0 ;; *) return 1 ;; esac; }

pode() { # pode <args do can-i...>  -> imprime yes/no
  local r
  r=$(kubectl auth can-i "$@" 2>/dev/null)
  case "$r" in yes*) echo yes ;; *) echo no ;; esac
}

# ----------------------------------------------------------------------------- cabecalho
command -v kubectl >/dev/null || { echo "kubectl nao encontrado"; exit 1; }
CTX=$(k config current-context)
SERVER=$(k config view --minify -o jsonpath='{.clusters[0].cluster.server}')
if ! k get --raw=/readyz >/dev/null; then
  echo "${VERM}Nao foi possivel falar com o cluster (contexto: ${CTX:-nenhum}).${FIM}"
  echo "Confira as credenciais do Learner Lab e rode: aws eks update-kubeconfig --name <cluster>"
  exit 1
fi

echo "==================================================================================="
echo " FIAP Store - Global Solution - verificacao automatica"
echo " Data:     $(date '+%d/%m/%Y %H:%M:%S')"
echo " Contexto: $CTX"
echo " Servidor: $SERVER"
CONTA="-"
command -v aws >/dev/null && CONTA=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "-")
echo " Conta AWS (credenciais atuais): $CONTA"
echo "==================================================================================="

# mapa "no zona pronto" usado por varios itens
NOS=$(k get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"|"}{.metadata.labels.topology\.kubernetes\.io/zone}{"|"}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}')
NOS_PRONTOS=$(echo "$NOS" | awk -F'|' '$3=="True"' | grep -c . || true)
zona_do_no() { echo "$NOS" | awk -F'|' -v n="$1" '$1==n {print $2}'; }

# ============================================================================= A
secao "A. Cluster e imagens (cap. 2 e 6)"

ZONAS=$(echo "$NOS" | awk -F'|' '$3=="True" && $2!="" {print $2}' | sort -u | grep -c . || true)
EKS=1; case "$SERVER" in *eks.amazonaws.com*) EKS=0 ;; esac
OK=1; [ "$EKS" = "0" ] && [ "$NOS_PRONTOS" -ge 3 ] && [ "$ZONAS" -ge 2 ] && OK=0
item A1 3 "Cluster EKS com 3+ nos prontos em 2+ zonas" "$OK" \
  "EKS: $([ "$EKS" = 0 ] && echo sim || echo NAO) | nos prontos: $NOS_PRONTOS | zonas: $ZONAS"

IMGS_APP=$(k get deploy store-api store-worker store-front -n "$APP_NS" \
  -o jsonpath='{range .items[*]}{.spec.template.spec.containers[0].image}{"\n"}{end}')
N_APP=$(echo "$IMGS_APP" | grep -c . || true)
N_ECR=$(echo "$IMGS_APP" | grep -c '\.dkr\.ecr\.' || true)
OK=1; [ "$N_APP" -eq 3 ] && [ "$N_ECR" -eq 3 ] && OK=0
item A2 3 "store-api, store-worker e store-front com imagens do ECR" "$OK" \
  "$N_ECR de $N_APP imagens vem do ECR | registro: $(echo "$IMGS_APP" | head -1 | cut -d/ -f1)"

TODAS_IMGS=""
for ns in "$APP_NS" "$DATA_NS"; do
  TODAS_IMGS="$TODAS_IMGS
$(k get deploy,sts,job -n "$ns" -o jsonpath='{range .items[*]}{range .spec.template.spec.containers[*]}{.image}{"\n"}{end}{end}')
$(k get cronjob -n "$ns" -o jsonpath='{range .items[*]}{range .spec.jobTemplate.spec.template.spec.containers[*]}{.image}{"\n"}{end}{end}')"
done
RUINS=""
for img in $(echo "$TODAS_IMGS" | grep . | sort -u); do
  case "$img" in
    *@sha256:*) ;;
    *:latest) RUINS="$RUINS $img" ;;
    *)
      ultimo="${img##*/}"
      case "$ultimo" in *:*) ;; *) RUINS="$RUINS $img" ;; esac
      ;;
  esac
done
OK=1; [ -z "$RUINS" ] && echo "$TODAS_IMGS" | grep -q . && OK=0
item A3 2 "Nenhuma imagem com tag latest ou sem tag" "$OK" "${RUINS:+problemas:$RUINS}"

# ============================================================================= B
secao "B. Workloads e alta disponibilidade (cap. 3 e 4)"

PRONTAS=$(k get deploy store-api -n "$APP_NS" -o jsonpath='{.status.readyReplicas}')
PRONTAS=${PRONTAS:-0}
OK=1; [ "$PRONTAS" -ge 3 ] && OK=0
item B1 2 "store-api com 3+ replicas prontas" "$OK" "replicas prontas: $PRONTAS"

RP=$(k get deploy store-api -n "$APP_NS" -o jsonpath='{.spec.template.spec.containers[0].readinessProbe.httpGet.path}')
LP=$(k get deploy store-api -n "$APP_NS" -o jsonpath='{.spec.template.spec.containers[0].livenessProbe.httpGet.path}')
OK=1; [ "$RP" = "/ready" ] && [ "$LP" = "/health" ] && OK=0
item B2 2 "store-api: readiness em /ready e liveness em /health" "$OK" "readiness: ${RP:-nenhuma} | liveness: ${LP:-nenhuma}"

SEM_REC=""
for d in store-api store-worker store-front; do
  linhas=$(k get deploy "$d" -n "$APP_NS" -o jsonpath='{range .spec.template.spec.containers[*]}{.name}{" "}{.resources.requests.cpu}{" "}{.resources.requests.memory}{" "}{.resources.limits.cpu}{" "}{.resources.limits.memory}{"\n"}{end}')
  if [ -z "$linhas" ]; then SEM_REC="$SEM_REC $d(inexistente)"; continue; fi
  incompletos=$(echo "$linhas" | awk 'NF<5 {print $1}')
  [ -n "$incompletos" ] && SEM_REC="$SEM_REC $d"
done
OK=1; [ -z "$SEM_REC" ] && OK=0
item B3 2 "requests e limits de CPU e memoria nos 3 Deployments" "$OK" "${SEM_REC:+faltando em:$SEM_REC}"

ZONAS_API=""
for no in $(k get pods -n "$APP_NS" -l app=store-api --field-selector=status.phase=Running -o jsonpath='{range .items[*]}{.spec.nodeName}{"\n"}{end}'); do
  ZONAS_API="$ZONAS_API
$(zona_do_no "$no")"
done
NZ=$(echo "$ZONAS_API" | grep . | sort -u | grep -c . || true)
OK=1; [ "$NZ" -ge 2 ] && OK=0
item B4 3 "Replicas da store-api em 2+ zonas de disponibilidade" "$OK" \
  "zonas: $(echo "$ZONAS_API" | grep . | sort -u | tr '\n' ' ')"

HPA=$(k get hpa store-api -n "$APP_NS" -o jsonpath='{.spec.scaleTargetRef.name}|{.spec.minReplicas}|{.status.currentMetrics[0].resource.current.averageUtilization}')
H_ALVO=$(echo "$HPA" | cut -d'|' -f1); H_MIN=$(echo "$HPA" | cut -d'|' -f2); H_CPU=$(echo "$HPA" | cut -d'|' -f3)
OK=1; [ "$H_ALVO" = "store-api" ] && [ "${H_MIN:-0}" -ge 3 ] && [ -n "$H_CPU" ] && OK=0
item B5 3 "HPA da store-api: minimo 3 e metrica de CPU sendo lida" "$OK" \
  "alvo: ${H_ALVO:-?} | min: ${H_MIN:-?} | CPU atual: ${H_CPU:-desconhecida (metrics-server? requests?)}%"

PDB=$(k get pdb -n "$APP_NS" -o jsonpath='{range .items[*]}{.spec.selector.matchLabels.app}{"|"}{.spec.minAvailable}{"|"}{.spec.maxUnavailable}{"\n"}{end}' | awk -F'|' '$1=="store-api"' | head -1)
P_MIN=$(echo "$PDB" | cut -d'|' -f2); P_MAX=$(echo "$PDB" | cut -d'|' -f3)
OK=1
case "$P_MIN" in ''|*%*) ;; *) [ "$P_MIN" -ge 2 ] && OK=0 ;; esac
[ "$P_MAX" = "1" ] && OK=0
item B6 2 "PodDisruptionBudget protegendo a store-api" "$OK" \
  "$(se_vazio "$PDB" "nenhum PDB com selector app=store-api" "minAvailable: ${P_MIN:--} | maxUnavailable: ${P_MAX:--}")"

MU=$(k get deploy store-api -n "$APP_NS" -o jsonpath='{.spec.strategy.rollingUpdate.maxUnavailable}')
NRS=$(k get rs -n "$APP_NS" -l app=store-api --no-headers | grep -c . || true)
OK=1; { [ "$MU" = "0" ] || [ "$MU" = "0%" ]; } && [ "$NRS" -ge 2 ] && OK=0
item B7 2 "Rolling update com maxUnavailable 0 e 2+ revisoes" "$OK" "maxUnavailable: ${MU:-padrao (25%)} | ReplicaSets: $NRS"

# ============================================================================= C
secao "C. Rede e namespaces (cap. 5)"

OK=1; k get ns "$APP_NS" >/dev/null && k get ns "$DATA_NS" >/dev/null && OK=0
item C1 1 "Namespaces store-prod e store-data" "$OK" ""

SVCS=$(k get svc -n "$DATA_NS" -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.type}{"\n"}{end}')
EXPOSTOS=$(echo "$SVCS" | awk '$2=="NodePort" || $2=="LoadBalancer" {print $1}' | tr '\n' ' ')
OK=1
echo "$SVCS" | grep -q '^store-db ' && echo "$SVCS" | grep -q '^store-redis ' && [ -z "$EXPOSTOS" ] && OK=0
item C2 2 "store-db e store-redis so com Services internos" "$OK" "${EXPOSTOS:+expostos para fora do cluster: $EXPOSTOS}"

ROTAS=$(k get ingress store-ingress -n "$APP_NS" -o jsonpath='{range .spec.rules[*].http.paths[*]}{.path}{" "}{.backend.service.name}{"\n"}{end}')
OK=1
echo "$ROTAS" | grep -qE '^/api/?[^ ]* store-api$' && echo "$ROTAS" | grep -qE '^/ store-front$' && OK=0
item C3 3 "Ingress store-ingress: /api -> store-api e / -> store-front" "$OK" \
  "rotas: $(echo "${ROTAS:-nenhuma}" | tr '\n' ';')"

TLS_SECRET=$(k get ingress store-ingress -n "$APP_NS" -o jsonpath='{.spec.tls[0].secretName}')
TLS_TIPO=""
[ -n "$TLS_SECRET" ] && TLS_TIPO=$(k get secret "$TLS_SECRET" -n "$APP_NS" -o jsonpath='{.type}')
if [ -z "$URL" ]; then
  H=$(k get ingress store-ingress -n "$APP_NS" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
  [ -z "$H" ] && H=$(k get svc -A -l app.kubernetes.io/name=traefik -o jsonpath='{.items[0].status.loadBalancer.ingress[0].hostname}')
  [ -n "$H" ] && URL="https://$H"
fi
URL="${URL%/}"
COD="-"
if [ -n "$URL" ] && command -v curl >/dev/null; then
  COD=$(curl -k -s -o /dev/null -m 10 -w '%{http_code}' "$URL/api/produtos" || true)
fi
OK=1; [ "$TLS_TIPO" = "kubernetes.io/tls" ] && [ "$COD" = "200" ] && case "$URL" in https://*) true ;; *) false ;; esac && OK=0
item C4 2 "TLS no Ingress e loja respondendo em HTTPS" "$OK" \
  "secret: ${TLS_SECRET:-nenhum} (${TLS_TIPO:-?}) | GET ${URL:-<sem URL>}/api/produtos -> $COD"

NEGA=$(k get networkpolicy -n "$DATA_NS" -o jsonpath='{range .items[*]}{.metadata.name}{"|"}{.spec.podSelector}{"|"}{.spec.policyTypes}{"|"}{.spec.ingress}{"\n"}{end}' \
  | awk -F'|' '$2=="{}" && $3 ~ /Ingress/ && $4=="" {print $1}')
OK=1; [ -n "$NEGA" ] && OK=0
item C5 2 "NetworkPolicy que nega toda entrada em store-data" "$OK" "${NEGA:+politica: $NEGA}"

DB_FQDN="store-db.$DATA_NS.svc.cluster.local"
# 0 = front BLOQUEADO (correto) | 1 = front conecta no banco | 2 = nao foi possivel testar
front_bloqueado() {
  if k exec -n "$APP_NS" deploy/store-front -- sh -c 'command -v nc' >/dev/null; then
    if k exec -n "$APP_NS" deploy/store-front -- nc -z -w 3 "$DB_FQDN" 5432 >/dev/null; then return 1; fi
    return 0
  fi
  # sem nc: wget do busybox. Postgres nao fala HTTP, mas a mensagem diz se houve conexao.
  local saida
  saida=$(kubectl exec -n "$APP_NS" deploy/store-front -- wget -T 3 -q -O /dev/null "http://$DB_FQDN:5432/" 2>&1)
  case "$saida" in
    *"timed out"*|*"can't connect"*) return 0 ;;
    *"error getting response"*|*"server returned"*|*"invalid"*) return 1 ;;
    *) return 2 ;;
  esac
}
FRONT_BLOQ=1; front_bloqueado; FRONT_BLOQ=$?
API_OK=1
k exec -n "$APP_NS" deploy/store-api -- python -c \
  "import socket; socket.create_connection(('$DB_FQDN', 5432), 3)" >/dev/null && API_OK=0
if [ "$FRONT_BLOQ" = "0" ]; then TXT_FRONT="bloqueado"
elif [ "$FRONT_BLOQ" = "1" ]; then TXT_FRONT="LIBERADO"
else TXT_FRONT="nao testado (exec falhou)"; fi
if [ "$API_OK" = "0" ]; then TXT_API="conecta"; else TXT_API="NAO conecta"; fi
OK=1; [ "$FRONT_BLOQ" = "0" ] && [ "$API_OK" = "0" ] && OK=0
item C6 2 "NetworkPolicy efetiva: front NAO alcanca o banco; api alcanca" "$OK" \
  "front->db: $TXT_FRONT | api->db: $TXT_API"

NQ=$(k get resourcequota -n "$APP_NS" --no-headers | grep -c . || true)
NL=$(k get limitrange -n "$APP_NS" --no-headers | grep -c . || true)
OK=1; [ "$NQ" -ge 1 ] && [ "$NL" -ge 1 ] && OK=0
item C7 2 "ResourceQuota e LimitRange em store-prod" "$OK" "ResourceQuota: $NQ | LimitRange: $NL"

# ============================================================================= D
secao "D. Dados, configuracao e daemons (cap. 7)"

DBP=$(k get sts store-db -n "$DATA_NS" -o jsonpath='{.status.readyReplicas}')
PVC=$(k get pvc -n "$DATA_NS" -o jsonpath='{range .items[*]}{.metadata.name}{"|"}{.status.phase}{"|"}{.spec.storageClassName}{"\n"}{end}' | awk -F'|' '$1 ~ /-store-db-0$/' | head -1)
OK=1; [ "${DBP:-0}" -ge 1 ] && [ "$(echo "$PVC" | cut -d'|' -f2)" = "Bound" ] && OK=0
item D1 3 "StatefulSet store-db pronto com PVC Bound" "$OK" "prontas: ${DBP:-0} | PVC: ${PVC:-nenhum}"

SC=$(echo "$PVC" | cut -d'|' -f3)
PROV=""; [ -n "$SC" ] && PROV=$(k get storageclass "$SC" -o jsonpath='{.provisioner}')
OK=1; [ "$PROV" = "ebs.csi.aws.com" ] && OK=0
item D2 1 "Volume do banco provisionado pelo driver EBS CSI" "$OK" "StorageClass: ${SC:-?} | provisioner: ${PROV:-?}"

CMS=$(k get deploy store-api -n "$APP_NS" -o jsonpath='{.spec.template.spec.containers[0].envFrom[*].configMapRef.name} {.spec.template.spec.containers[0].env[*].valueFrom.configMapKeyRef.name}')
OK=1; contem "$CMS" store-api-config && k get configmap store-api-config -n "$APP_NS" >/dev/null && OK=0
item D3 2 "ConfigMap store-api-config usado pela store-api" "$OK" "ConfigMaps referenciados: ${CMS:-nenhum}"

CAMPOS=$(k get deploy store-api -n "$APP_NS" -o jsonpath='{.spec.template.spec.containers[0].env[*].valueFrom.fieldRef.fieldPath}')
OK=1; contem "$CAMPOS" metadata.name && contem "$CAMPOS" metadata.namespace && contem "$CAMPOS" spec.nodeName && OK=0
item D4 2 "Downward API: nome do Pod, namespace e no na store-api" "$OK" "campos: ${CAMPOS:-nenhum}"

DS=$(k get ds -A -o jsonpath='{range .items[*]}{.metadata.namespace}{" "}{.metadata.name}{" "}{.status.desiredNumberScheduled}{" "}{.status.numberReady}{"\n"}{end}' \
  | awk -v n="$NOS_PRONTOS" '$1!="kube-system" && $3==n && $4==n && n>0 {print $1"/"$2}' | tr '\n' ' ')
OK=1; [ -n "$DS" ] && OK=0
item D5 3 "DaemonSet proprio com um Pod pronto em cada no" "$OK" \
  "$(se_vazio "$DS" "nenhum DaemonSet fora do kube-system cobrindo os $NOS_PRONTOS nos" "DaemonSets: $DS")"

RP=$(k get deploy store-redis -n "$DATA_NS" -o jsonpath='{.status.readyReplicas}')
OK=1; [ "${RP:-0}" -ge 1 ] && OK=0
item D6 1 "Redis store-redis pronto" "$OK" ""

# ============================================================================= E
secao "E. Jobs e Secrets (cap. 8)"

JS=$(k get job db-migrate -n "$APP_NS" -o jsonpath='{.status.succeeded}')
OK=1; [ "${JS:-0}" -ge 1 ] && OK=0
item E1 2 "Job db-migrate concluido" "$OK" "$(se_vazio "$JS" "Job inexistente ou sem sucesso" "execucoes bem-sucedidas: $JS")"

CJ=$(k get cronjob store-report -n "$APP_NS" -o jsonpath='{.spec.schedule}|{.status.lastSuccessfulTime}')
CJ_S=$(echo "$CJ" | cut -d'|' -f1); CJ_T=$(echo "$CJ" | cut -d'|' -f2)
OK=1; [ -n "$CJ_S" ] && [ -n "$CJ_T" ] && OK=0
item E2 3 "CronJob store-report com execucao bem-sucedida" "$OK" "agenda: ${CJ_S:-?} | ultimo sucesso: ${CJ_T:-nunca}"

REFS=$(k get deploy store-api -n "$APP_NS" -o jsonpath='{.spec.template.spec.volumes[*].secret.secretName} {.spec.template.spec.containers[0].env[*].valueFrom.secretKeyRef.name}')
OK=1; contem "$REFS" store-db-credentials && k get secret store-db-credentials -n "$APP_NS" >/dev/null && OK=0
item E3 3 "Senha do banco vinda do Secret store-db-credentials" "$OK" "Secrets referenciados: ${REFS:-nenhum}"

# ============================================================================= F
secao "F. RBAC e seguranca (cap. 9 e 10)"

SA=$(k get deploy store-api -n "$APP_NS" -o jsonpath='{.spec.template.spec.serviceAccountName}')
SA=${SA:-default}
NODES_OK=$(pode get nodes --as="system:serviceaccount:$APP_NS:$SA")
SECRETS=$(pode list secrets -n "$APP_NS" --as="system:serviceaccount:$APP_NS:$SA")
OK=1; [ "$SA" != "default" ] && [ "$NODES_OK" = "yes" ] && [ "$SECRETS" = "no" ] && OK=0
item F1 3 "store-api: ServiceAccount propria, le nodes e NAO le Secrets" "$OK" \
  "SA: $SA | get nodes: $NODES_OK | list secrets: $SECRETS"

SEM_TOKEN=""
for d in store-front store-worker; do
  pod_am=$(k get deploy "$d" -n "$APP_NS" -o jsonpath='{.spec.template.spec.automountServiceAccountToken}')
  sa=$(k get deploy "$d" -n "$APP_NS" -o jsonpath='{.spec.template.spec.serviceAccountName}')
  sa_am=$(k get sa "${sa:-default}" -n "$APP_NS" -o jsonpath='{.automountServiceAccountToken}')
  if [ "$pod_am" = "false" ] || { [ -z "$pod_am" ] && [ "$sa_am" = "false" ]; }; then :; else SEM_TOKEN="$SEM_TOKEN $d"; fi
done
OK=1; [ -z "$SEM_TOKEN" ] && OK=0
item F2 2 "Token da API desligado em store-front e store-worker" "$OK" "${SEM_TOKEN:+token montado em:$SEM_TOKEN}"

dev() { pode "$@" -n "$APP_NS" --as=dev.aluno --as-group=fiap:devs; }
R1=$(dev list pods); R2=$(dev get pods --subresource=log)
R3=$(dev delete pods); R4=$(dev get secrets); R5=$(dev create pods --subresource=exec)
OK=1; [ "$R1$R2$R3$R4$R5" = "yesyesnonono" ] && OK=0
item F3 3 "Grupo fiap:devs: le Pods e logs; sem delete, Secrets ou exec" "$OK" \
  "list pods: $R1 | logs: $R2 | delete: $R3 | secrets: $R4 | exec: $R5"

PSA=$(k get ns "$APP_NS" -o jsonpath='{.metadata.labels.pod-security\.kubernetes\.io/enforce}')
OK=1; [ "$PSA" = "restricted" ] && OK=0
item F4 3 "Pod Security restricted (enforce) em store-prod" "$OK" "enforce: ${PSA:-nenhum}"

INSEGUROS=""
for d in store-api store-worker store-front; do
  v=$(k get deploy "$d" -n "$APP_NS" -o jsonpath='{.spec.template.spec.securityContext.runAsNonRoot}|{.spec.template.spec.securityContext.seccompProfile.type}|{.spec.template.spec.containers[0].securityContext.runAsNonRoot}|{.spec.template.spec.containers[0].securityContext.seccompProfile.type}|{.spec.template.spec.containers[0].securityContext.readOnlyRootFilesystem}|{.spec.template.spec.containers[0].securityContext.allowPrivilegeEscalation}|{.spec.template.spec.containers[0].securityContext.capabilities.drop}')
  nonroot=$(echo "$v" | awk -F'|' '{print ($1=="true" || $3=="true") ? "s" : "n"}')
  seccomp=$(echo "$v" | awk -F'|' '{print ($2=="RuntimeDefault" || $4=="RuntimeDefault" || $2=="Localhost" || $4=="Localhost") ? "s" : "n"}')
  rofs=$(echo "$v" | awk -F'|' '{print $5}')
  ape=$(echo "$v" | awk -F'|' '{print $6}')
  drop=$(echo "$v" | awk -F'|' '{print $7}')
  falta=""
  [ "$nonroot" = "s" ] || falta="$falta runAsNonRoot"
  [ "$seccomp" = "s" ] || falta="$falta seccomp"
  [ "$rofs" = "true" ] || falta="$falta readOnlyRootFilesystem"
  [ "$ape" = "false" ] || falta="$falta allowPrivilegeEscalation"
  case "$drop" in *ALL*) ;; *) falta="$falta drop-ALL" ;; esac
  [ -n "$falta" ] && INSEGUROS="$INSEGUROS $d:[$falta ]"
done
OK=1; [ -z "$INSEGUROS" ] && OK=0
item F5 3 "securityContext completo nos 3 Deployments" "$OK" "${INSEGUROS:+faltando ->$INSEGUROS}"

# ============================================================================= G
secao "G. Serverless e GitOps (cap. 8 e 11)"

SO=$(k get scaledobject store-worker -n "$APP_NS" -o jsonpath='{.spec.scaleTargetRef.name}|{.spec.minReplicaCount}|{.status.conditions[?(@.type=="Ready")].status}|{.spec.triggers[0].type}')
SO_ALVO=$(echo "$SO" | cut -d'|' -f1); SO_MIN=$(echo "$SO" | cut -d'|' -f2)
SO_PRONTO=$(echo "$SO" | cut -d'|' -f3); SO_TIPO=$(echo "$SO" | cut -d'|' -f4)
SO_MIN=${SO_MIN:-0}   # o padrao do KEDA e 0
OK=1; [ "$SO_ALVO" = "store-worker" ] && [ "$SO_MIN" = "0" ] && [ "$SO_PRONTO" = "True" ] && OK=0
item G1 4 "KEDA: store-worker escala a partir de zero" "$OK" \
  "$(se_vazio "$SO" "ScaledObject store-worker nao encontrado" "alvo: $SO_ALVO | min: $SO_MIN | trigger: ${SO_TIPO:-?} | pronto: ${SO_PRONTO:-?}")"

APPS=$(k get applications.argoproj.io -A -o jsonpath='{range .items[*]}{.metadata.name}{"|"}{.status.sync.status}{"|"}{.status.health.status}{"|"}{.spec.syncPolicy.automated.prune}{"|"}{.spec.syncPolicy.automated.selfHeal}{"\n"}{end}')
BOA=$(echo "$APPS" | awk -F'|' '$2=="Synced" && $3=="Healthy" && $4=="true" && $5=="true" {print $1}' | head -1)
OK=1; [ -n "$BOA" ] && OK=0
item G2 4 "Argo CD: Application Synced + Healthy com prune e selfHeal" "$OK" \
  "$(echo "${APPS:-nenhuma Application}" | head -3 | tr '\n' ';')"

# ============================================================================= resumo
echo
echo "==================================================================================="
printf " %sPontuacao automatica: %s / %s%s\n" "$NEG" "$PONTOS" "$MAXIMO" "$FIM"
[ -n "$FALHAS" ] && echo " Itens com falha: $FALHAS"
echo
echo " Avaliados pelo professor na demonstracao:"
echo "   M1 (2 pts)  README com passos para criar e destruir o ambiente"
echo "   M2 (2 pts)  Nenhum segredo no repositorio Git (todos os branches)"
echo "   M3 (1 pt)   Relatorio de scan (Trivy) das 3 imagens, sem CRITICAL sem justificativa"
echo "   Desafios ao vivo (15 pts): 3 desafios x 5 pts"
echo "==================================================================================="
