# FIAP Store — aplicação da Global Solution

Cloud Developer II · Kubernetes e Serverless

Este repositório contém a **aplicação pronta** da FIAP Store. O código já funciona: o trabalho do
grupo **não é programar**, é construir a **plataforma** que roda este sistema no Amazon EKS —
cluster, manifestos, rede, armazenamento, segurança, escalonamento e entrega por GitOps.

> Leia o enunciado da Global Solution antes de começar. Ele traz os nomes obrigatórios dos recursos,
> o checklist de avaliação e o guia de criação do cluster no AWS Academy Learner Lab.

---

## Arquitetura

```
                    Internet (HTTPS)
                          |
                    [ Ingress ]  -------------------------- namespace store-prod
                     /        \
              /api/...          /
                 |               |
           [ store-api ]   [ store-front ]
             |      |
   grava pedido   enfileira o ID
             |      |
             |      v
             |  [ Redis: lista "pedidos" ] <----- KEDA observa o tamanho da fila
             |      |
             |      v
             |  [ store-worker ]  0..N replicas (escala a zero)
             |      |
             v      v
        [ PostgreSQL store-db ] --------------------------- namespace store-data
             ^
             |
   [ db-migrate (Job) ]   [ store-report (CronJob) ]
```

| Componente | Imagem | O que faz |
|---|---|---|
| `store-front` | construída a partir de `store-front/` | página da loja + **painel da plataforma** |
| `store-api` | construída a partir de `store-api/` | catálogo, pedidos, autodiagnóstico |
| `db-migrate` | **mesma imagem** da `store-api`, outro comando | cria as tabelas e popula o catálogo |
| `store-worker` | construída a partir de `store-worker/` | consome a fila e processa pedidos |
| `store-report` | **mesma imagem** do `store-worker`, outro comando | gera o relatório consolidado de vendas |
| `store-db` | `postgres:16-alpine` (oficial) | banco de dados |
| `store-redis` | `redis:7.4-alpine` (oficial) | fila de pedidos |

São **três imagens** para construir. Postgres e Redis usam imagens oficiais.

---

## Contrato de cada serviço com a plataforma

Esta seção diz **o que cada contêiner espera do Kubernetes**. É a especificação que os manifestos
de vocês precisam atender.

### store-api

| Item | Valor |
|---|---|
| Porta | `8000` |
| Comando padrão | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| Liveness | `GET /health` — responde 200 enquanto o processo está vivo |
| Readiness | `GET /ready` — responde 503 se não conseguir falar com o banco |
| Métricas | `GET /metrics` (formato Prometheus) |
| Usuário | UID `10001` (não-root) |
| Sistema de arquivos | funciona com `readOnlyRootFilesystem: true` sem volume extra |

Variáveis de ambiente:

| Variável | Obrigatória | Origem esperada no Kubernetes |
|---|---|---|
| `DB_HOST` | sim | ConfigMap — ex.: `store-db.store-data.svc.cluster.local` |
| `DB_PORT` | não (5432) | ConfigMap |
| `DB_NAME` | não (`fiapstore`) | ConfigMap |
| `DB_USER` | não (`fiapstore`) | ConfigMap |
| `DB_PASSWORD_FILE` **ou** `DB_PASSWORD` | sim | **Secret**: montado como arquivo (preferível) ou via `secretKeyRef` |
| `REDIS_HOST` | sim | ConfigMap — ex.: `store-redis.store-data.svc.cluster.local` |
| `REDIS_PORT` | não (6379) | ConfigMap |
| `QUEUE_NAME` | não (`pedidos`) | ConfigMap |
| `APP_ENV` | não | ConfigMap — ex.: `producao` |
| `POD_NAME` | sim | **Downward API** → `metadata.name` |
| `POD_NAMESPACE` | sim | **Downward API** → `metadata.namespace` |
| `NODE_NAME` | sim | **Downward API** → `spec.nodeName` |
| `APP_VERSION` | — | **gravada na imagem** no build (`--build-arg APP_VERSION=...`) |

Permissões na API do Kubernetes: para mostrar em qual **zona de disponibilidade** está rodando, a
`store-api` lê o objeto `Node` em que foi agendada. Isso exige uma ServiceAccount própria com
permissão de `get` em `nodes` — um recurso **de cluster**, não de namespace. Pense em qual par de
objetos RBAC resolve isso. E só isso: o painel acusa se a ServiceAccount conseguir ler Secrets.

### db-migrate

| Item | Valor |
|---|---|
| Imagem | a mesma da `store-api` |
| Comando | `python -m app.migrate` |
| Comportamento | aguarda o banco por até 90 s, cria as tabelas e o catálogo; termina com código 0. É idempotente: pode rodar várias vezes |
| Variáveis | as de banco da `store-api` |

### store-worker

| Item | Valor |
|---|---|
| Comando padrão | `python -m worker.main` |
| Porta | nenhuma (não recebe tráfego) |
| Comportamento | consome IDs da lista Redis `pedidos` e marca cada pedido como processado |
| Encerramento | ao receber SIGTERM, termina o pedido em andamento e sai com código 0 |
| Usuário | UID `10001` |
| Variáveis | as de banco e de Redis da `store-api`, mais `POD_NAME` (Downward API) e `PROCESS_SECONDS` (opcional, padrão 2 s por pedido) |
| Permissões na API do Kubernetes | **nenhuma** |

O worker foi feito para **escalar a partir de zero** pelo tamanho da fila (KEDA, scaler `redis`,
lista `pedidos`).

### store-report

| Item | Valor |
|---|---|
| Imagem | a mesma do `store-worker` |
| Comando | `python -m worker.relatorio` |
| Comportamento | grava uma linha na tabela `relatorios` e termina com código 0 |

### store-front

| Item | Valor |
|---|---|
| Porta | `8080` |
| Usuário | UID `101` (não-root) |
| Health | `GET /healthz` |
| Chamadas | a página chama `/api/...` no **mesmo host** — quem encaminha `/api` para a `store-api` é o Ingress |
| Sistema de arquivos | com `readOnlyRootFilesystem: true`, monte um `emptyDir` em `/tmp` (o nginx grava pid e temporários ali) |
| Permissões na API do Kubernetes | **nenhuma** |

---

## O painel da plataforma

A página inicial da loja tem um **Painel da plataforma**: um autodiagnóstico feito de dentro do
cluster. Ele chama `/api/plataforma` várias vezes e mostra, em verde, vermelho e amarelo:

- quantas réplicas da `store-api` responderam e em quantas zonas de disponibilidade;
- se a página está em HTTPS;
- se a Downward API, o RBAC, o Secret, o banco, a fila, o worker e o CronJob estão funcionando;
- a postura de segurança **real** do processo: UID, sistema de arquivos somente leitura,
  capabilities, escalação de privilégio, seccomp e limites de CPU e memória.

Usem o painel para se autoavaliar durante o desenvolvimento. **A nota não vem do painel**: na
demonstração, cada item é conferido com `kubectl`.

---

## Rodando localmente (antes de ir para o cluster)

Requer Docker com o plugin Compose.

```bash
cd local
docker compose up --build
# abra http://localhost:8080
```

Gerar um relatório (no cluster, quem faz isso é o CronJob):

```bash
docker compose --profile manual run --rm relatorio
```

No ambiente local o painel mostra vários itens em vermelho — Downward API, RBAC, segurança e
limites só existem no Kubernetes. Isso é esperado.

---

## Build das imagens para o EKS

> **Atenção (Mac com Apple Silicon):** os nós do EKS do laboratório são `x86_64`. Uma imagem
> construída num Mac M1/M2/M3 sem `--platform` sai `arm64` e o Pod termina com
> `exec format error`. **Sempre** construa com `--platform linux/amd64`.

```bash
export AWS_REGION=us-east-1
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export REGISTRY=$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# 1. repositórios no ECR (uma vez)
for repo in store-api store-worker store-front; do
  aws ecr create-repository --repository-name $repo --region $AWS_REGION
done

# 2. login no ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $REGISTRY

# 3. build e push — store-api em DUAS versões
docker buildx build --platform linux/amd64 --build-arg APP_VERSION=1.0 -t $REGISTRY/store-api:1.0 --push store-api
docker buildx build --platform linux/amd64 --build-arg APP_VERSION=2.0 -t $REGISTRY/store-api:2.0 --push store-api
docker buildx build --platform linux/amd64 -t $REGISTRY/store-worker:1.0 --push store-worker
docker buildx build --platform linux/amd64 -t $REGISTRY/store-front:1.0 --push store-front
```

A versão `2.0` da `store-api` é idêntica à `1.0` — muda só o número gravado na imagem, que aparece
no topo da página. Serve para demonstrar rolling update e rollback: durante a troca, o selo mostra
as duas versões convivendo.

---

## Referência rápida da API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | liveness |
| GET | `/ready` | readiness (verifica o banco) |
| GET | `/metrics` | métricas Prometheus |
| GET | `/api/produtos` | catálogo |
| POST | `/api/pedidos` | cria um pedido: `{"produto_id": 1, "quantidade": 2}` |
| POST | `/api/pedidos/lote?quantidade=50` | cria pedidos aleatórios (para ver o worker escalar) |
| GET | `/api/pedidos?limite=20` | últimos pedidos e resumo |
| GET | `/api/relatorios` | últimos relatórios do CronJob |
| GET | `/api/plataforma` | autodiagnóstico da plataforma |
| GET | `/api/carga?ms=200` | consome CPU por `ms` milissegundos (para provocar o HPA) |

Gerar carga para o HPA, de dentro do cluster. O Pod de carga roda no namespace `default` porque o
`store-prod`, com Pod Security `restricted`, recusaria um `busybox` sem `securityContext`:

```bash
kubectl run carga -n default --rm -it --restart=Never --image=busybox:1.36 -- \
  sh -c 'while true; do wget -q -O- "http://store-api.store-prod/api/carga?ms=300" >/dev/null; done'
```

---

## Estrutura do repositório

```
fiap-store/
  store-api/        código, requirements e Dockerfile da API (inclui o db-migrate)
  store-worker/     código, requirements e Dockerfile do worker (inclui o store-report)
  store-front/      página, script do painel e Dockerfile do nginx
  local/            docker-compose para rodar na máquina
  avaliacao/        verifica-gs.sh — o script usado na demonstração
  k8s/              <- CRIADO POR VOCÊS: todos os manifestos da plataforma
```

Os manifestos ficam em `k8s/`. É essa pasta que o Argo CD vai sincronizar com o cluster.
