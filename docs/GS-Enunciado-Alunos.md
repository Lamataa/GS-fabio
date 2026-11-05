  # Global Solution — FIAP Store no Amazon EKS

  **Cloud Developer II · Kubernetes e Serverless · Trabalho final**

  ---

  ## 1. O trabalho em uma frase

  **A aplicação está pronta; vocês constroem a plataforma.** O professor entrega o código da FIAP Store
  (API, front-end, worker e jobs). O grupo cria o cluster EKS, escreve todos os manifestos Kubernetes,
  coloca o sistema no ar com segurança, escalonamento e entrega por GitOps — e demonstra tudo
  funcionando, ao vivo.

  | Item | Definição |
  |---|---|
  | Grupos | 2 ou 3 integrantes |
  | Prazo | 1 a 2 semanas, conforme definido pelo professor (ver cronograma na seção 12) |
  | Ambiente | AWS Academy Learner Lab — um cluster EKS por grupo |
  | Entrega | repositório público no GitHub com a tag `gs-final` |
  | Avaliação | demonstração ao vivo de 20 minutos, com todos os integrantes |
  | Nota | 100 pontos: 80 verificados por script, 5 conferidos pelo professor, 15 em desafios ao vivo |

  ---

  ## 2. O cenário

  A FIAP Store vai entrar em produção na semana da Black Friday. O time de desenvolvimento entregou a
  aplicação; falta a plataforma. A diretoria fez cinco exigências:

  1. **Não pode cair.** Um nó, um Pod ou uma zona de disponibilidade com problema não tiram a loja do ar.
  2. **Tem que aguentar o pico** — e não pode custar caro fora dele. O processamento de pedidos
    precisa escalar sozinho com a demanda e **desligar por completo** quando não houver fila.
  3. **Segurança não é opcional.** Nada roda como root, a senha do banco não aparece em lugar nenhum
    do Git, cada componente só acessa o que precisa e o banco não é alcançável pelo front-end.
  4. **Desenvolvedores olham, não mexem.** O time de dev precisa ver Pods e logs em produção, sem
    poder alterar nada nem ler segredos.
  5. **Tudo no Git.** O estado do cluster é o que está no repositório. Mudança manual é desfeita
    automaticamente.

  ---

  ## 3. O que vocês recebem

  O repositório **`fiap-store`** (o professor informa o link do template no GitHub):

  | Pasta | Conteúdo |
  |---|---|
  | `store-api/` | API em Python/FastAPI. A mesma imagem roda o Job de migração do banco |
  | `store-worker/` | Processador de pedidos. A mesma imagem roda o CronJob de relatório |
  | `store-front/` | Página da loja com o **Painel da plataforma** |
  | `local/` | `docker-compose` para rodar tudo na sua máquina |
  | `avaliacao/verifica-gs.sh` | O script de correção. **Rodem quantas vezes quiserem** |

  **Leiam o `README.md` do repositório inteiro antes de escrever o primeiro manifesto.** A seção
  "Contrato de cada serviço com a plataforma" diz exatamente o que cada contêiner espera do
  Kubernetes: portas, sondas, variáveis, usuário, permissões.

  O código **não pode ser alterado**, com uma exceção: corrigir um bug, desde que o commit explique
  o motivo. Toda a nota está na plataforma.

  ---

  ## 4. Arquitetura alvo

  ```
    Internet (HTTPS)
          |
    [Traefik]  LoadBalancer da AWS                          namespace traefik
          |
    [Ingress store-ingress]  ------------------------------- namespace store-prod
      |  /api                          |  /                   Pod Security: restricted
      v                                v
    [store-api]  3 a 6 Pods (HPA)    [store-front]  2 Pods
      |   |
      |   +--> fila Redis "pedidos" ----> [store-worker] 0 a 5 Pods (KEDA)
      |                                         |
      |   [db-migrate] Job    [store-report] CronJob
      v                                         v
    ===================== NetworkPolicy ======================= namespace store-data
    [store-db] StatefulSet + volume EBS       [store-redis]      Pod Security: baseline

    [DaemonSet de métricas ou logs em todos os nós]           namespace à escolha
    [Argo CD] sincroniza a pasta k8s/ do repositório           namespace argocd
  ```

  ---

  ## 5. Nomes obrigatórios

  O script de correção procura os recursos **por nome**. Recurso com outro nome não é encontrado e o
  item vale zero.

  | Recurso | Nome | Namespace |
  |---|---|---|
  | Namespaces | `store-prod` e `store-data` | — |
  | Deployments | `store-api`, `store-front`, `store-worker` | `store-prod` |
  | Services | `store-api`, `store-front` | `store-prod` |
  | StatefulSet e Service | `store-db` | `store-data` |
  | Deployment e Service | `store-redis` | `store-data` |
  | Job | `db-migrate` | `store-prod` |
  | CronJob | `store-report` | `store-prod` |
  | Ingress | `store-ingress` | `store-prod` |
  | HPA | `store-api` | `store-prod` |
  | ConfigMap | `store-api-config` | `store-prod` |
  | Secret da senha do banco | `store-db-credentials` (chave `password`) | `store-prod` e `store-data` |
  | ScaledObject (KEDA) | `store-worker` | `store-prod` |
  | Grupo dos desenvolvedores no RBAC | `fiap:devs` | — |
  | Label em todos os Pods | `app: <nome do componente>` | — |

  ---

  ## 6. Requisitos e pontuação

  Cada linha é um item **binário**: cumpriu, ganha os pontos; não cumpriu, zero. Os itens marcados
  com **script** são conferidos por `avaliacao/verifica-gs.sh` durante a demonstração.

  ### A. Cluster e imagens — cap. 2 e 6 (10 pts)

  | ID | Requisito | Pts | Como é verificado |
  |---|---|---:|---|
  | A1 | Cluster EKS com 3 ou mais nós prontos em 2 ou mais zonas de disponibilidade | 3 | script |
  | A2 | `store-api`, `store-worker` e `store-front` rodando com imagens do **Amazon ECR** do grupo | 3 | script |
  | A3 | Nenhuma imagem com tag `latest` ou sem tag, em nenhum dos dois namespaces | 2 | script |
  | M1 | README do grupo com os passos para **criar** e para **destruir** todo o ambiente | 2 | professor |

  ### B. Workloads e alta disponibilidade — cap. 3 e 4 (16 pts)

  | ID | Requisito | Pts | Como é verificado |
  |---|---|---:|---|
  | B1 | `store-api` com 3 ou mais réplicas prontas | 2 | script |
  | B2 | `store-api` com readiness em `/ready` e liveness em `/health` | 2 | script |
  | B3 | `requests` e `limits` de CPU e memória nos Deployments `store-api`, `store-worker` e `store-front` | 2 | script |
  | B4 | Réplicas da `store-api` espalhadas em 2 ou mais zonas | 3 | script |
  | B5 | HPA da `store-api` com mínimo 3 e métrica de CPU sendo lida (não `<unknown>`) | 3 | script |
  | B6 | PodDisruptionBudget para a `store-api` (`minAvailable` ≥ 2 ou `maxUnavailable` = 1) | 2 | script |
  | B7 | Rolling update com `maxUnavailable: 0` e histórico com 2 ou mais revisões — o rollout 1.0 → 2.0 precisa ter acontecido **no cluster da demonstração** | 2 | script |

  ### C. Rede e namespaces — cap. 5 (14 pts)

  | ID | Requisito | Pts | Como é verificado |
  |---|---|---:|---|
  | C1 | Namespaces `store-prod` e `store-data` | 1 | script |
  | C2 | Banco e Redis com Services **internos** apenas (nada de NodePort ou LoadBalancer em `store-data`) | 2 | script |
  | C3 | Ingress `store-ingress`: `/api` → `store-api` e `/` → `store-front` | 3 | script |
  | C4 | TLS no Ingress (Secret do tipo `kubernetes.io/tls`) e a loja respondendo em HTTPS | 2 | script |
  | C5 | NetworkPolicy que **nega toda entrada** em `store-data` | 2 | script |
  | C6 | NetworkPolicy **efetiva**: o `store-front` não alcança o banco; a `store-api` alcança | 2 | script |
  | C7 | ResourceQuota e LimitRange em `store-prod` | 2 | script |

  ### D. Dados, configuração e daemons — cap. 7 (12 pts)

  | ID | Requisito | Pts | Como é verificado |
  |---|---|---:|---|
  | D1 | StatefulSet `store-db` pronto, com PVC `Bound` | 3 | script |
  | D2 | Volume do banco provisionado pelo driver **EBS CSI** (`ebs.csi.aws.com`) | 1 | script |
  | D3 | ConfigMap `store-api-config` usado pela `store-api` | 2 | script |
  | D4 | Downward API: nome do Pod, namespace e nome do nó na `store-api` | 2 | script |
  | D5 | DaemonSet **criado pelo grupo** com um Pod pronto em cada nó (fora do `kube-system`) | 3 | script |
  | D6 | `store-redis` pronto | 1 | script |

  ### E. Jobs e Secrets — cap. 8 (10 pts)

  | ID | Requisito | Pts | Como é verificado |
  |---|---|---:|---|
  | E1 | Job `db-migrate` concluído com sucesso e **existente** no momento da correção | 2 | script |
  | E2 | CronJob `store-report` com pelo menos uma execução bem-sucedida (agendada ou disparada a partir do CronJob) | 3 | script |
  | E3 | Senha do banco consumida do Secret `store-db-credentials` pela `store-api` | 3 | script |
  | M2 | Nenhum segredo em nenhum commit de nenhum branch do repositório | 2 | professor |

  ### F. RBAC e segurança — cap. 9 e 10 (15 pts)

  | ID | Requisito | Pts | Como é verificado |
  |---|---|---:|---|
  | F1 | `store-api` com ServiceAccount própria, que **lê** `nodes` e **não lê** Secrets | 3 | script |
  | F2 | Token da API do Kubernetes **não montado** no `store-front` e no `store-worker` | 2 | script |
  | F3 | Grupo `fiap:devs` em `store-prod`: lista Pods e lê logs; **não** apaga Pods, **não** lê Secrets, **não** faz `exec` | 3 | script |
  | F4 | Pod Security Admission `restricted` em modo `enforce` no `store-prod` | 3 | script |
  | F5 | `securityContext` completo nos três Deployments: `runAsNonRoot`, `seccompProfile: RuntimeDefault`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, `capabilities.drop: ["ALL"]` | 3 | script |
  | M3 | Relatório de scan de vulnerabilidades (Trivy) das 3 imagens no repositório, sem `CRITICAL` sem justificativa | 1 | professor |

  ### G. Serverless e GitOps — cap. 8 e 11 (8 pts)

  | ID | Requisito | Pts | Como é verificado |
  |---|---|---:|---|
  | G1 | `store-worker` escalado pelo **KEDA** a partir de **zero** réplicas (ScaledObject pronto, mínimo 0) | 4 | script |
  | G2 | Argo CD com uma Application `Synced` e `Healthy`, com `prune` e `selfHeal` ligados | 4 | script |

  ### H. Desafios ao vivo (15 pts)

  Na demonstração, o professor sorteia **3 desafios** da lista da seção 7. Cada integrante conduz
  pelo menos um. Cada desafio vale 5 pontos: **3 pela execução** (o sistema se comporta como deveria)
  e **2 pela explicação** (quem conduziu explica o que aconteceu e por quê).

  | Bloco | Pontos |
  |---|---:|
  | Automáticos (script) | 80 |
  | Manuais (M1, M2, M3) | 5 |
  | Desafios ao vivo | 15 |
  | **Total** | **100** |

  ---

  ## 7. Banco de desafios ao vivo

  Preparem-se para todos. O professor escolhe três na hora.

  | # | Desafio | O que precisa acontecer |
  |---|---|---|
  | 1 | **Self-healing:** apagar um Pod da `store-api` | um novo Pod sobe sozinho; a loja não sai do ar |
  | 2 | **Manutenção de nó:** drenar um nó que **não** hospede o `store-db-0` | os Pods migram, o PDB é respeitado, a loja segue no ar; depois `uncordon` |
  | 3 | **Rollback por GitOps:** colocar a 2.0 no ar e voltar para a 1.0 | a mudança é feita **por commit**; o selo do topo da página mostra a troca |
  | 4 | **Escala a zero:** gerar 50 pedidos no painel | o `store-worker` sai de 0, sobe até vários Pods, processa a fila e volta a 0 |
  | 5 | **Persistência:** apagar o Pod `store-db-0` | o banco volta com os mesmos dados; os pedidos continuam lá |
  | 6 | **Pod Security:** tentar criar um Pod privilegiado em `store-prod` | a API recusa, citando o Pod Security |
  | 7 | **RBAC:** testar o grupo `fiap:devs` com `kubectl auth can-i --as` | lê Pods e logs; não apaga, não lê Secrets, não faz exec |
  | 8 | **Drift:** alterar algo do cluster na mão (`kubectl delete service store-front`) | o Argo CD recria sozinho em segundos |
  | 9 | **Rede:** do `store-front`, tentar abrir conexão com o banco | a conexão não acontece; da `store-api`, acontece |
  | 10 | **Relatório sob demanda:** disparar o CronJob agora | um Job é criado a partir do CronJob e o relatório aparece na página |

  ---

  ## 8. Guia do AWS Academy Learner Lab

  ### 8.1 Restrições do laboratório que mudam o projeto

  | Restrição | Consequência |
  |---|---|
  | Não é permitido criar roles IAM nem provedor OIDC | cluster e nós usam a role **`LabRole`** já existente; **não há IRSA** |
  | Crédito limitado (confira o valor no seu lab) | **sem NAT Gateway**; nós em subnets públicas; destruir o cluster ao fim de cada sessão |
  | A sessão expira (o cronômetro aparece no lab) | credenciais mudam a cada sessão: atualize `~/.aws/credentials` sempre que iniciar o lab |

  ### 8.2 Criando o cluster

  Iniciem o lab (*Start Lab*), abram *AWS Details* e copiem as credenciais para `~/.aws/credentials`.
  Usem o `eksctl` em sua versão mais recente e este arquivo, trocando `<ACCOUNT_ID>`:

  ```yaml
  # cluster.yaml
  apiVersion: eksctl.io/v1alpha5
  kind: ClusterConfig
  metadata:
    name: fiap-store
    region: us-east-1
    version: "1.35"            # versão em suporte padrão: versões antigas custam 6x mais
  iam:
    withOIDC: false
    serviceRoleARN: arn:aws:iam::<ACCOUNT_ID>:role/LabRole
  availabilityZones: ["us-east-1a", "us-east-1b", "us-east-1c"]
  vpc:
    nat:
      gateway: Disable
  addons:
    - name: vpc-cni
      configurationValues: '{"enableNetworkPolicy": "true"}'   # sem isto, NetworkPolicy é ignorada
    - name: coredns
    - name: kube-proxy
    - name: aws-ebs-csi-driver
    - name: metrics-server
  managedNodeGroups:
    - name: ng-principal
      instanceType: t3.medium   # máximo de 17 Pods por nó: este projeto precisa de 4 nós
      minSize: 4
      desiredCapacity: 4
      maxSize: 5
      privateNetworking: false
      volumeSize: 20
      iam:
        instanceRoleARN: arn:aws:iam::<ACCOUNT_ID>:role/LabRole
  ```

  ```bash
  eksctl create cluster -f cluster.yaml          # 15 a 20 minutos
  kubectl get nodes -L topology.kubernetes.io/zone
  ```

  ### 8.3 Componentes de plataforma (já liberados — não são o foco da avaliação)

  ```bash
  helm repo add traefik https://traefik.github.io/charts
  helm repo add kedacore https://kedacore.github.io/charts
  helm repo update
  helm upgrade --install traefik traefik/traefik -n traefik --create-namespace \
    --set deployment.replicas=2 --wait
  helm upgrade --install keda kedacore/keda -n keda --create-namespace --wait
  kubectl create namespace argocd
  kubectl apply -n argocd --server-side --force-conflicts \
    -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
  ```

  > **Por que Traefik?** O `ingress-nginx` foi aposentado pelo projeto Kubernetes em março de 2026 e
  > não recebe mais correções de segurança. O Traefik atende objetos `Ingress` padrão: usem
  > `ingressClassName: traefik`.

  Endereço público da loja: `kubectl -n traefik get svc traefik`. Acessem por **https://**.

  ### 8.4 Custo e destruição

  O ambiente deste trabalho custa **cerca de US$ 0,30 por hora** (control plane, 4 nós `t3.medium`,
  balanceador e volume). Ligado por um dia inteiro, passa de US$ 7. **Destruam o cluster ao fim de
  cada sessão de trabalho** — com GitOps, recriar a aplicação leva poucos minutos.

  Ordem de destruição (o README de vocês precisa ter isto — item M1):

  1. apagar a Application do Argo CD (senão ele recria tudo);
  2. apagar os namespaces `store-prod` e `store-data` e esperar `kubectl get pv` ficar vazio (o PVC
    apagado remove o volume EBS, em segundo plano);
  3. `helm uninstall traefik -n traefik` (remove o balanceador);
  4. `eksctl delete cluster -f cluster.yaml --disable-nodegroup-eviction`;
  5. conferir que não sobrou volume nem balanceador no console.

  ---

  ## 9. Armadilhas conhecidas

  Leiam antes de travar.

  | Sintoma | Causa provável |
  |---|---|
  | Pod com `exec format error` | imagem `arm64` construída num Mac M1/M2/M3: use `--platform linux/amd64` |
  | `store-db-0` em `CrashLoopBackOff` com "directory not empty" | a raiz do volume EBS tem `lost+found`: use `PGDATA` num subdiretório |
  | PVC eternamente `Pending` | não há StorageClass padrão no EKS recente: crie uma com `provisioner: ebs.csi.aws.com` |
  | Drenar o nó do `store-db-0` deixa o banco `Pending` | volume EBS existe em **uma** zona só; o Pod só pode voltar para um nó daquela zona |
  | NetworkPolicy aplicada e nada é bloqueado | o VPC CNI precisa de `enableNetworkPolicy: "true"` (já está no `cluster.yaml`) |
  | Worker nunca sobe com a fila cheia | o operador do KEDA (namespace `keda`) também precisa alcançar o Redis: inclua na NetworkPolicy |
  | Argo CD e HPA (ou KEDA) brigando pelo número de réplicas | não declare `replicas` nos Deployments escalados por HPA/KEDA |
  | Argo CD falha ao sincronizar o Job `db-migrate` | Job é imutável: use-o como hook do Argo (`argocd.argoproj.io/hook: Sync`) |
  | Pod recusado com `violates PodSecurity "restricted"` | falta algum campo de `securityContext` — a mensagem lista exatamente qual |
  | `store-front` em `CrashLoopBackOff` com `readOnlyRootFilesystem` | o nginx precisa de um `emptyDir` em `/tmp` |
  | Pods `Pending` com "Too many pods" | cada `t3.medium` aceita no máximo 17 Pods: o cluster precisa de 4 nós |
  | Navegador mostra o certificado "TRAEFIK DEFAULT CERT" | o Traefik escolhe o certificado pelo nome pedido (SNI): gere o certificado com o hostname do balanceador em `subjectAltName` |
  | Primeira sincronização do Argo CD para no meio e o `db-migrate` não roda | HPA e ScaledObject aparecem degradados nos primeiros segundos: use `syncPolicy.retry` e `sync-wave` |
  | Banco recusa a senha depois de recriar o Secret | o Postgres só lê a senha na criação do banco: não troque a senha de um banco já inicializado |
  | `kubectl` responde `Unauthorized` de repente | a sessão do lab expirou: atualize as credenciais e rode `aws eks update-kubeconfig --name fiap-store` |
  | Painel mostra "Zona: 403" | a ServiceAccount da `store-api` não pode ler `nodes` — recurso de cluster |

  ---

  ## 10. O que entregar

  Repositório **público** no GitHub, derivado do template, com a tag **`gs-final`**, contendo:

  - todo o código recebido (sem alterações, salvo correção justificada);
  - a pasta **`k8s/`** com **todos** os manifestos — é ela que o Argo CD sincroniza;
  - o arquivo do cluster (`cluster.yaml`) e os comandos de instalação usados;
  - **`README.md` do grupo** com: integrantes e RM; como criar o ambiente do zero; como criar os
    Secrets (sem os valores); como destruir tudo; o link do Argo CD Application;
  - **`avaliacao/trivy/`** com o relatório de scan das 3 imagens e, para cada `CRITICAL`, uma
    justificativa ou a correção aplicada.

  **Segredos não vão para o Git.** Senha do banco e certificado TLS são criados direto no cluster
  (`kubectl create secret ...`) e o README explica como, sem mostrar os valores. Usar Sealed Secrets
  ou External Secrets é permitido.

  ---

  ## 11. A demonstração (20 minutos)

  | Tempo | O que acontece |
  |---|---|
  | 2 min | Abrir a loja em HTTPS e o Painel da plataforma |
  | 5 min | Rodar `./avaliacao/verifica-gs.sh https://<endereço>` na tela, sem cortes |
  | 9 min | Três desafios ao vivo sorteados pelo professor (seção 7) |
  | 4 min | Perguntas do professor sobre as decisões do grupo |

  Regras:

  - O cluster precisa estar **no ar no horário da demonstração**. Criem com antecedência — o
    `eksctl` leva 20 minutos e o lab pode estar lento.
  - Todos os integrantes presentes. Quem não conduzir nenhum desafio nem responder pergunta não
    recebe os pontos da seção H.
  - O **Painel da plataforma** ajuda vocês a se autoavaliarem, mas **não vale nota**. A nota vem do
    script e dos desafios.
  - Se o laboratório da AWS estiver fora do ar no dia, a demonstração é remarcada — não aceita vídeo.

  ---

  ## 12. Cronograma

  O prazo é curto, e por isso o plano depende de duas regras.

  **1. Dividam o trabalho no primeiro dia.** Um integrante sozinho não termina a tempo. Sugestão:

  | Papel | Responsável por | Itens do checklist |
  |---|---|---|
  | **Plataforma** | imagens no ECR, cluster, Traefik, KEDA, Argo CD, README de criação e destruição | A1–A3, G2, M1 |
  | **Aplicação** | `store-data` e `store-prod`: Deployments, Services, Ingress, Secrets, Job, CronJob, HPA, PDB | B1–B7, C1–C4, D1–D4, D6, E1–E3, M2 |
  | **Segurança** | NetworkPolicy, RBAC, Pod Security, `securityContext`, quota, DaemonSet, KEDA, scan Trivy | C5–C7, D5, F1–F5, G1, M3 |

  Em grupos de 2, quem cuida da **Plataforma** também assume a **Segurança**.

  **2. Escrevam os manifestos no minikube e levem ao EKS só o que já funciona.** O cluster leva 20
  minutos para subir e a sessão do Learner Lab expira. Quase tudo pode ser desenvolvido na máquina:

  ```bash
  minikube start --nodes 2 --cni calico --cpus 2 --memory 4g    # calico: para a NetworkPolicy funcionar
  docker build -t store-api:1.0 store-api && docker build -t store-worker:1.0 store-worker \
    && docker build -t store-front:1.0 store-front                 # build local, SEM --platform
  minikube image load store-api:1.0 store-worker:1.0 store-front:1.0
  ```

  Só exigem o EKS: os itens A1 e A2 (cluster e ECR), D2 (volume EBS), B4 (zonas) e o balanceador do
  Traefik. No minikube, usem a StorageClass `standard` e `imagePullPolicy: Never`. Ao migrar para o
  EKS, mudam só a StorageClass e o endereço das imagens.

  ### 12.1 Prazo de 2 semanas

  | Quando | Meta | Sinal de que está no caminho |
  |---|---|---|
  | Dias 1 e 2 | ler o README do repositório; rodar com `docker compose`; imagens no ECR; **criar e destruir o cluster uma vez** | painel em `localhost:8080`; `kubectl get nodes` mostrou 4 nós |
  | Dias 3 a 5 | no minikube: `store-data` (Secret, Postgres, Redis) e `store-prod` (ConfigMap, Deployments, Services, Ingress, Job, CronJob) | a loja abre e mostra o catálogo |
  | Dias 6 e 7 | no minikube: HPA, PDB, KEDA, NetworkPolicy, RBAC, Pod Security, `securityContext`, quota, DaemonSet | painel quase todo verde |
  | Dia 8 | no EKS: Argo CD sincronizando a pasta `k8s/`; TLS; rollout 1.0 → 2.0 por commit; scan Trivy | `verifica-gs.sh` acima de 70 |
  | Dia 9 | **ensaio geral:** destruir tudo, recriar seguindo só o README (cronometrem), corrigir até 80/80, ensaiar os 10 desafios | `verifica-gs.sh` com 80/80 |
  | Dia 10 | demonstração | cluster criado **de manhã**, rollout 1.0 → 2.0 refeito nele, script rodado antes de entrar |

  ### 12.2 Prazo de 1 semana

  Mesmas metas, sem folga: cada dia que escorrega sai do ensaio.

  | Quando | Plataforma | Aplicação | Segurança |
  |---|---|---|---|
  | Dia 1 | imagens no ECR; cluster criado e destruído uma vez | rodar com `docker compose`; `store-data` no minikube | ler o README; Pod Security e `securityContext` no minikube |
  | Dia 2 | Traefik, KEDA e Argo CD num cluster de teste; estrutura da pasta `k8s/` | `store-prod`: Deployments, Services, Ingress, Job, CronJob | NetworkPolicy, RBAC, quota, DaemonSet |
  | Dia 3 | **tudo no EKS pelo Argo CD** | HPA, PDB, espalhamento por zona | KEDA; scan Trivy |
  | Dia 4 | README de criação e destruição; rollout 1.0 → 2.0 por commit | corrigir o que o `verifica-gs.sh` acusar | corrigir o que o `verifica-gs.sh` acusar |
  | Dia 5 | **todos:** ensaiar os 10 desafios e a demonstração | | |
  | Dia da demonstração | cluster criado de manhã; rollout refeito; script rodado antes de entrar | | |

  > **Dica:** rodem o `verifica-gs.sh` todo dia a partir do momento em que houver um cluster EKS. Ele
  > diz exatamente o que falta e em qual item.

  ---

  ## 13. Pontos extras (até +5, sem ultrapassar 100)

  | Extra | Pts |
  |---|---:|
  | `store-data` também em Pod Security `restricted` (Postgres e Redis rodando como não-root) | +2 |
  | Pipeline de CI (GitHub Actions) que constrói, escaneia e publica as imagens no ECR | +2 |
  | Manifestos organizados com Kustomize ou Helm | +1 |
  | Prometheus e Grafana com um dashboard da FIAP Store | +1 |
  | Certificado TLS emitido pelo cert-manager | +1 |

  ---

  ## 14. Regras gerais

  - **Uso de IA:** permitido e **declarado** no README (quais ferramentas, para quê). Na
    demonstração, qualquer integrante precisa explicar qualquer manifesto do repositório. Não saber
    explicar o próprio YAML zera o desafio em curso.
  - **Plágio:** manifestos idênticos entre grupos, salvo trechos triviais, zeram ambos os grupos.
  - **Atraso:** a tag `gs-final` precisa existir até a data limite. Commits depois dela não são
    considerados.
