# FIAP Store no Amazon EKS — Global Solution

Cloud Developer II · Kubernetes e Serverless

A aplicação (API, front-end, worker e jobs) foi entregue pronta pelo professor. Este repositório
contém a **plataforma** que roda a FIAP Store no Amazon EKS: cluster, manifestos Kubernetes, rede,
armazenamento, segurança, escalonamento e entrega por GitOps (Argo CD).

> O README original da aplicação (contrato de cada serviço) está em
> [`docs/README-aplicacao.md`](docs/README-aplicacao.md) e o enunciado em
> [`docs/GS-Enunciado-Alunos.md`](docs/GS-Enunciado-Alunos.md).

## Integrantes

| Nome | RM |
|---|---|
| Gabriel Lamata | RM562093 |
| Luiz Gustavo Parpinelli | RM566493 |

---

## Arquitetura

```
Internet (HTTPS)
      |
 [Traefik] LoadBalancer da AWS ............................ namespace traefik
      |
 [Ingress store-ingress]  /api -> store-api | / -> store-front   namespace store-prod
      |                                                     (Pod Security: restricted)
 [store-api] 3-6 Pods (HPA)      [store-front] 2 Pods
      |   \
      |    +--> fila Redis "pedidos" --> [store-worker] 0-5 Pods (KEDA)
      |
 [db-migrate] Job (hook do Argo)    [store-report] CronJob
      v
 ================= NetworkPolicy (nega toda entrada) ================
 [store-db] StatefulSet + EBS      [store-redis]            namespace store-data
                                                            (Pod Security: baseline)
 [node-exporter] DaemonSet em todos os nós ................ namespace monitoring
 [Argo CD] sincroniza a pasta k8s/ deste repositório ...... namespace argocd
```

## Estrutura do repositório

| Caminho | Conteúdo |
|---|---|
| `cluster.yaml` | definição do cluster EKS (eksctl) |
| `argocd-app.yaml` | Application do Argo CD que sincroniza a pasta `k8s/` |
| `k8s/` | **todos** os manifestos da plataforma (sincronizados pelo Argo CD) |
| `avaliacao/trivy/` | relatórios de vulnerabilidade das 3 imagens e justificativas |
| `avaliacao/verifica-gs.sh` | script de correção do professor |
| `store-api/`, `store-worker/`, `store-front/` | código da aplicação (não alterado) |

### Manifestos (`k8s/`)

| Arquivo | O que cria | Itens |
|---|---|---|
| `00-namespaces.yaml` | `store-prod` (restricted), `store-data` (baseline), `monitoring` | C1, F4 |
| `01-storageclass.yaml` | StorageClass `ebs-gp3` (`ebs.csi.aws.com`) | D2 |
| `10-store-db.yaml` | StatefulSet + Service interno do PostgreSQL, volume EBS | D1, C2 |
| `11-store-redis.yaml` | Deployment + Service interno do Redis | D6, C2 |
| `20-configmap.yaml` | ConfigMap `store-api-config` | D3 |
| `21-db-migrate.yaml` | Job `db-migrate` (hook `Sync` do Argo CD) | E1 |
| `30-store-api.yaml` | ServiceAccount, Service e Deployment da API (probes, Downward API, Secret, securityContext, spread por zona, `maxUnavailable: 0`) | B1–B4, B7, D4, E3, F5 |
| `31-store-front.yaml` | Service e Deployment do front (sem token, `emptyDir` em `/tmp`) | F2, F5 |
| `32-store-worker.yaml` | Deployment do worker (sem `replicas`, sem token) | F2, F5 |
| `33-store-report.yaml` | CronJob `store-report` | E2 |
| `40-ingress.yaml` | Ingress `store-ingress` com TLS | C3, C4 |
| `50-hpa-pdb.yaml` | HPA (3–6, CPU 70%) e PDB (`minAvailable: 2`) | B5, B6 |
| `51-keda.yaml` | ScaledObject `store-worker` (Redis, 0–5) | G1 |
| `60-networkpolicy.yaml` | nega toda entrada em `store-data` e libera só API/worker/jobs/KEDA | C5, C6 |
| `61-rbac.yaml` | ClusterRole `get nodes` para a API; Role somente leitura para `fiap:devs` | F1, F3 |
| `62-quota.yaml` | ResourceQuota e LimitRange em `store-prod` | C7 |
| `70-daemonset.yaml` | DaemonSet `node-exporter` em todos os nós | D5 |

---

## Pré-requisitos

- Ferramentas: `aws` CLI v2, `eksctl`, `kubectl`, `helm`, `docker` (com buildx), `trivy`, `git`, `openssl`.
- Acesso ao **AWS Academy Learner Lab** (o cluster e os nós usam a role `LabRole`; não há OIDC/IRSA).
- No **Windows (Git Bash)**: comandos com argumentos que começam com `/` precisam de
  `MSYS_NO_PATHCONV=1` (indicado abaixo onde é necessário).

---

## 1. Credenciais do Learner Lab (toda sessão)

1. *Start Lab* → aguardar o indicador ficar verde → *AWS Details* → *AWS CLI: Show*.
2. Copiar o bloco `[default]` para `~/.aws/credentials` (fora do repositório).
3. Região:
   ```bash
   printf "[default]\nregion = us-east-1\n" > ~/.aws/config
   aws sts get-caller-identity
   ```

## 2. Imagens no ECR (uma vez por conta do lab)

As imagens ficam no ECR da conta entre as sessões; só é preciso refazer se a conta mudar.

```bash
export AWS_REGION=us-east-1
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export REGISTRY=$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

for repo in store-api store-worker store-front; do
  aws ecr create-repository --repository-name $repo --region $AWS_REGION --no-cli-pager
done
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $REGISTRY

docker buildx build --platform linux/amd64 --build-arg APP_VERSION=1.0 -t $REGISTRY/store-api:1.0 --push store-api
docker buildx build --platform linux/amd64 --build-arg APP_VERSION=2.0 -t $REGISTRY/store-api:2.0 --push store-api
docker buildx build --platform linux/amd64 -t $REGISTRY/store-worker:1.0 --push store-worker
docker buildx build --platform linux/amd64 -t $REGISTRY/store-front:1.0 --push store-front
```

Scan de vulnerabilidades (resultado em `avaliacao/trivy/`):
```bash
trivy image $REGISTRY/store-api:1.0    > avaliacao/trivy/store-api.txt
trivy image $REGISTRY/store-worker:1.0 > avaliacao/trivy/store-worker.txt
trivy image $REGISTRY/store-front:1.0  > avaliacao/trivy/store-front.txt
```

> Se a conta do lab mudar, trocar o número da conta em `cluster.yaml` e nos `image:` da pasta `k8s/`.

## 3. Criar o ambiente do zero (toda sessão)

### 3.1 Cluster EKS (~20 min)
```bash
eksctl create cluster -f cluster.yaml
kubectl get nodes -L topology.kubernetes.io/zone      # 4 nós Ready em 3 zonas
```

### 3.2 Componentes de plataforma
```bash
helm repo add traefik https://traefik.github.io/charts
helm repo add kedacore https://kedacore.github.io/charts
helm repo update

helm upgrade --install traefik traefik/traefik -n traefik --create-namespace \
  --set deployment.replicas=2 \
  --set providers.kubernetesIngress.publishedService.enabled=true --wait

helm upgrade --install keda kedacore/keda -n keda --create-namespace --wait

kubectl create namespace argocd
kubectl apply -n argocd --server-side --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```
`publishedService.enabled=true` faz o Traefik publicar o endereço no `status` do Ingress; sem isso
o Argo CD não marca a Application como `Healthy`.

### 3.3 Endereço público da loja
```bash
export HOST=$(kubectl -n traefik get svc traefik -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "https://$HOST"
```

### 3.4 Secrets (fora do Git)

Os segredos **não estão no repositório**. São criados direto no cluster a cada sessão.

**Senha do banco** — o mesmo valor nos dois namespaces (substituir `<SENHA>`; o valor é combinado
entre os integrantes e não é registrado em nenhum arquivo):
```bash
kubectl create namespace store-prod
kubectl create namespace store-data
kubectl create secret generic store-db-credentials -n store-prod --from-literal=password='<SENHA>'
kubectl create secret generic store-db-credentials -n store-data --from-literal=password='<SENHA>'
```

**Certificado TLS** autoassinado com o hostname do balanceador no `subjectAltName` (o `CN` tem limite
de 64 caracteres, por isso usa um nome curto):
```bash
MSYS_NO_PATHCONV=1 openssl req -x509 -nodes -days 30 -newkey rsa:2048 \
  -keyout tls.key -out tls.crt \
  -subj "/CN=fiap-store" -addext "subjectAltName=DNS:$HOST"
kubectl create secret tls store-tls -n store-prod --cert=tls.crt --key=tls.key
rm tls.key tls.crt
```

### 3.5 GitOps com Argo CD
```bash
kubectl apply -f argocd-app.yaml
kubectl get application -n argocd          # fiap-store  Synced  Healthy
```

- **Application do Argo CD:** [`argocd-app.yaml`](argocd-app.yaml) — nome `fiap-store`, namespace
  `argocd`, origem `https://github.com/Lamataa/GS-fabio.git`, pasta `k8s/`, branch `main`,
  `automated.prune` e `automated.selfHeal` ligados, com `retry`.
- **Painel do Argo CD:**
  ```bash
  kubectl -n argocd port-forward svc/argocd-server 8443:443
  # https://localhost:8443  usuário: admin
  kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
  ```

### 3.6 Rollout 1.0 → 2.0 e CronJob (obrigatório no cluster da demonstração)
```bash
# disparar o relatório a partir do CronJob
kubectl create job --from=cronjob/store-report relatorio-manual-1 -n store-prod

# rollout por commit
sed -i 's#store-api:1.0#store-api:2.0#' k8s/30-store-api.yaml
git commit -am "Rollout store-api 1.0 -> 2.0" && git push
kubectl annotate application fiap-store -n argocd argocd.argoproj.io/refresh=normal --overwrite
kubectl get rs -n store-prod -l app=store-api                       # 2 ReplicaSets
```
> Antes de recriar o cluster para a demonstração, voltar o `k8s/30-store-api.yaml` para `1.0`
> (commit), para que o rollout aconteça no cluster novo.

### 3.7 Verificação
```bash
MSYS_NO_PATHCONV=1 bash avaliacao/verifica-gs.sh https://$HOST       # 80/80
```

---

## 4. Destruir todo o ambiente

Na ordem (o Argo CD recriaria tudo se fosse apagado depois):

```bash
# 1. Application do Argo CD
kubectl delete application fiap-store -n argocd

# 2. namespaces da aplicação; esperar os volumes EBS sumirem
kubectl delete namespace store-prod store-data monitoring
kubectl get pv                      # repetir até "No resources found"

# 3. Traefik (remove o Load Balancer da AWS)
helm uninstall traefik -n traefik

# 4. cluster
eksctl delete cluster -f cluster.yaml --disable-nodegroup-eviction
```

5. Conferir no console da AWS (região `us-east-1`): **EC2 → Volumes** e **EC2 → Load Balancers**
   sem recursos do projeto; **CloudFormation** sem stacks `eksctl-fiap-store-*`.

---

## 5. Desafios ao vivo — comandos

| # | Desafio | Comando |
|---|---|---|
| 1 | Self-healing | `kubectl delete -n store-prod $(kubectl get pod -n store-prod -l app=store-api -o name \| head -1)` (apaga um Pod) e `kubectl get pods -n store-prod -l app=store-api -w` |
| 2 | Manutenção de nó | `kubectl get pod store-db-0 -n store-data -o wide` (ver o nó do banco); `kubectl drain <outro-no> --ignore-daemonsets --delete-emptydir-data`; depois `kubectl uncordon <outro-no>` |
| 3 | Rollback por GitOps | trocar a tag em `k8s/30-store-api.yaml`, `git commit` + `git push`; o selo da página mostra a versão |
| 4 | Escala a zero | gerar 50 pedidos no painel; `kubectl get pods -n store-prod -l app=store-worker -w` |
| 5 | Persistência | `kubectl delete pod store-db-0 -n store-data`; os pedidos continuam na página |
| 6 | Pod Security | `kubectl run priv -n store-prod --image=busybox:1.36 --privileged -- sleep 3600` → recusado |
| 7 | RBAC | `kubectl auth can-i list pods -n store-prod --as=dev --as-group=fiap:devs` (yes); `delete pods`, `get secrets`, `create pods --subresource=exec` (no) |
| 8 | Drift | `kubectl delete service store-front -n store-prod` → o Argo CD recria |
| 9 | Rede | `kubectl exec -n store-prod deploy/store-front -- nc -z -w 3 store-db.store-data.svc.cluster.local 5432` (falha) e o mesmo da `store-api` com Python (conecta) |
| 10 | Relatório sob demanda | `kubectl create job --from=cronjob/store-report relatorio-$(date +%s) -n store-prod` |

---

## 6. Segurança

- Nenhum segredo no Git: senha do banco e certificado são criados com `kubectl create secret`.
- `store-prod` com Pod Security `restricted` (enforce); todos os contêineres com `runAsNonRoot`,
  `seccompProfile: RuntimeDefault`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`,
  `capabilities.drop: ["ALL"]`.
- Token da API do Kubernetes montado apenas na `store-api`, cuja ServiceAccount só pode `get nodes`.
- `store-data` sem entrada por padrão; só API, worker, jobs e o operador do KEDA alcançam banco/Redis.
- Scan Trivy das 3 imagens em [`avaliacao/trivy/`](avaliacao/trivy/) com a análise dos `CRITICAL` em
  [`avaliacao/trivy/JUSTIFICATIVA.md`](avaliacao/trivy/JUSTIFICATIVA.md).

## 7. Uso de IA

Declaração exigida pelo enunciado (seção 14):

| Ferramenta | Para quê |
|---|---|
| Claude (Anthropic) | apoio na leitura do enunciado, no planejamento das etapas, na escrita e revisão dos manifestos Kubernetes, do `argocd-app.yaml`, deste README e da análise do Trivy, e na solução de erros do ambiente Windows/Git Bash |

Todos os manifestos foram revisados, aplicados e testados pelo grupo no cluster EKS
(`verifica-gs.sh`: 80/80), e cada integrante é capaz de explicar cada arquivo da pasta `k8s/`.
