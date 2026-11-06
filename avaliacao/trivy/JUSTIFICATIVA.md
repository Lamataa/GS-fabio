# Análise das vulnerabilidades CRITICAL (Trivy)

Scan realizado em 05/11/2026 com Trivy 0.70.0 sobre as imagens publicadas no ECR.

| Imagem | CRITICAL | Relatório |
|---|---:|---|
| `store-api:1.0` | 0 | [`store-api.txt`](store-api.txt) |
| `store-worker:1.0` | 0 | [`store-worker.txt`](store-worker.txt) |
| `store-front:1.0` | 4 | [`store-front.txt`](store-front.txt) |

Os 4 `CRITICAL` da `store-front` estão todos em pacotes da **imagem base**
`nginxinc/nginx-unprivileged:1.28-alpine` (definida no `Dockerfile` entregue pelo professor), não no
código da aplicação.

## Análise por vulnerabilidade

| Pacote | CVE | Versão instalada → corrigida | Análise |
|---|---|---|---|
| `libcrypto3` | CVE-2026-31789 | 3.5.5-r0 → 3.5.6-r0 | Estouro de buffer no OpenSSL que, segundo a descrição, afeta **apenas sistemas de 32 bits**. Os nós do cluster são `t3.medium` **x86_64 (64 bits)** e a imagem é `linux/amd64`. **Não aplicável** ao ambiente. |
| `libssl3` | CVE-2026-31789 | 3.5.5-r0 → 3.5.6-r0 | Mesma CVE do item acima (biblioteca irmã do OpenSSL). **Não aplicável** pelo mesmo motivo. |
| `brotli-libs` | CVE-2026-111497 | 1.2.0-r0 → 1.2.1-r0 | Escrita fora dos limites no **decodificador** Brotli. O contêiner serve apenas arquivos estáticos (HTML/CSS/JS) e não descompacta conteúdo Brotli enviado por clientes. Risco considerado **baixo**; mitigado pelos controles abaixo. |
| `nginx` | CVE-2026-42945 | 1.28.2-r1 → 1.28.3-r1 | Vulnerabilidade no próprio nginx, já corrigida na 1.28.3. É a mais relevante das quatro. Risco **aceito temporariamente** com os controles abaixo, até a publicação da imagem base atualizada (ver "Correção"). |

## Controles que reduzem o impacto (já aplicados no cluster)

- Contêiner roda como **não-root** (UID 101), com `runAsNonRoot: true` e Pod Security `restricted`.
- `readOnlyRootFilesystem: true` (só `/tmp` é gravável, via `emptyDir`).
- `allowPrivilegeEscalation: false` e `capabilities.drop: ["ALL"]`; `seccompProfile: RuntimeDefault`.
- **Sem token** da API do Kubernetes (`automountServiceAccountToken: false`): um invasor no
  contêiner não consegue falar com o cluster.
- **NetworkPolicy**: o `store-front` não alcança o banco nem o Redis (verificado pelo item C6).
- Exposição apenas via Ingress/Traefik com TLS; limites de CPU e memória definidos.

## Correção

A correção definitiva é reconstruir a imagem do front sobre uma base com os pacotes corrigidos
(nginx ≥ 1.28.3-r1, OpenSSL ≥ 3.5.6-r0, brotli ≥ 1.2.1-r0), publicá-la com uma tag nova
(ex.: `store-front:1.1`), atualizar `k8s/31-store-front.yaml` por commit e repetir o scan:

```bash
docker buildx build --platform linux/amd64 --pull -t $REGISTRY/store-front:1.1 --push store-front
trivy image $REGISTRY/store-front:1.1 > avaliacao/trivy/store-front.txt
```

O `--pull` força o download da versão mais recente da imagem base `1.28-alpine`. Enquanto a imagem
base publicada não trouxer as versões corrigidas, os riscos acima permanecem aceitos com os
controles descritos.
