"""Autodiagnostico da plataforma, visto de DENTRO do container.

Cada verificacao devolve um status:
  ok     -> requisito atendido
  falha  -> requisito nao atendido
  aviso  -> ainda nao da para afirmar (ex.: nenhum pedido processado ainda)

O painel do store-front desenha estes itens em verde, vermelho e amarelo.
Ele e uma ferramenta de AUTOAVALIACAO; a correcao oficial usa kubectl.
"""
import os
from pathlib import Path

import httpx
import redis

from . import config, db


def _item(id_, titulo, capitulo, status, detalhe):
    return {"id": id_, "titulo": titulo, "capitulo": capitulo, "status": status, "detalhe": detalhe}


# ---------------------------------------------------------------- API do Kubernetes

def _k8s_get(caminho: str):
    """GET autenticado com o token da ServiceAccount. Retorna (status_http | None, json | motivo)."""
    try:
        token = (config.K8S_SA_DIR / "token").read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None, "sem token: automountServiceAccountToken desligado ou ServiceAccount ausente"
    except OSError as exc:
        return None, f"token da ServiceAccount ilegivel: {exc.strerror}"
    ca = config.K8S_SA_DIR / "ca.crt"
    try:
        verify = str(ca) if ca.is_file() else True
    except OSError:
        verify = True
    try:
        resp = httpx.get(
            f"{config.K8S_API_URL}{caminho}",
            headers={"Authorization": f"Bearer {token}"},
            verify=verify,
            timeout=3,
        )
    except httpx.HTTPError as exc:
        return None, f"API do Kubernetes inacessivel: {exc.__class__.__name__}"
    try:
        corpo = resp.json()
    except ValueError:
        corpo = {}
    return resp.status_code, corpo


def zona_do_no() -> tuple[str, dict]:
    if not config.NODE_NAME:
        return "", _item("zona", "Zona de disponibilidade do no", "9 - RBAC", "falha",
                         "NODE_NAME vazio: exponha spec.nodeName via Downward API")
    status, corpo = _k8s_get(f"/api/v1/nodes/{config.NODE_NAME}")
    if status == 200:
        labels = corpo.get("metadata", {}).get("labels", {})
        zona = labels.get("topology.kubernetes.io/zone", "")
        if zona:
            return zona, _item("zona", "Zona de disponibilidade do no", "9 - RBAC", "ok",
                               f"no {config.NODE_NAME} na zona {zona}")
        return "", _item("zona", "Zona de disponibilidade do no", "9 - RBAC", "aviso",
                         "no lido, mas sem o label topology.kubernetes.io/zone (cluster local?)")
    if status == 403:
        return "", _item("zona", "Zona de disponibilidade do no", "9 - RBAC", "falha",
                         "403: a ServiceAccount nao pode ler 'nodes'. Falta ClusterRole + ClusterRoleBinding")
    if status is None:
        return "", _item("zona", "Zona de disponibilidade do no", "9 - RBAC", "falha", corpo)
    return "", _item("zona", "Zona de disponibilidade do no", "9 - RBAC", "falha", f"HTTP {status}")


def menor_privilegio() -> dict:
    """O certo aqui e NAO conseguir: a store-api nao tem motivo para ler Secrets."""
    ns = config.POD_NAMESPACE or "default"
    status, corpo = _k8s_get(f"/api/v1/namespaces/{ns}/secrets")
    if status == 403:
        return _item("menor-privilegio", "Menor privilegio: nao le Secrets", "9 - RBAC", "ok",
                     "403 ao listar Secrets, como deve ser")
    if status == 200:
        return _item("menor-privilegio", "Menor privilegio: nao le Secrets", "9 - RBAC", "falha",
                     "a ServiceAccount CONSEGUE listar Secrets: permissao excessiva")
    if status is None:
        return _item("menor-privilegio", "Menor privilegio: nao le Secrets", "9 - RBAC", "aviso", corpo)
    return _item("menor-privilegio", "Menor privilegio: nao le Secrets", "9 - RBAC", "aviso", f"HTTP {status}")


# ---------------------------------------------------------------- dados

def identidade() -> dict:
    faltando = [n for n, v in (("POD_NAME", config.POD_NAME), ("POD_NAMESPACE", config.POD_NAMESPACE),
                               ("NODE_NAME", config.NODE_NAME)) if not v]
    if faltando:
        return _item("identidade", "Identidade via Downward API", "7 - Volumes", "falha",
                     "variaveis ausentes: " + ", ".join(faltando))
    return _item("identidade", "Identidade via Downward API", "7 - Volumes", "ok",
                 f"{config.POD_NAMESPACE}/{config.POD_NAME} no no {config.NODE_NAME}")


def segredo() -> dict:
    _, origem = config.db_password()
    if origem == "arquivo":
        return _item("segredo", "Senha do banco vinda de Secret", "8 - Secrets", "ok",
                     "lida de arquivo (Secret montado como volume)")
    if origem == "variavel":
        return _item("segredo", "Senha do banco vinda de Secret", "8 - Secrets", "ok",
                     "lida de variavel de ambiente (confira se vem de secretKeyRef)")
    if origem == "arquivo-ilegivel":
        return _item("segredo", "Senha do banco vinda de Secret", "8 - Secrets", "falha",
                     "DB_PASSWORD_FILE aponta para um arquivo que nao existe")
    return _item("segredo", "Senha do banco vinda de Secret", "8 - Secrets", "falha",
                 "nenhuma senha configurada (DB_PASSWORD_FILE ou DB_PASSWORD)")


def banco_e_processamento() -> list[dict]:
    itens = []
    try:
        with db.conectar() as conn:
            n_prod = conn.execute("SELECT count(*) AS n FROM produtos").fetchone()["n"]
            ultimo = conn.execute(
                "SELECT processado_por, round(extract(epoch FROM now() - processado_em)) AS ha "
                "FROM pedidos WHERE status = 'processado' ORDER BY processado_em DESC LIMIT 1"
            ).fetchone()
            rel = conn.execute(
                "SELECT gerado_por, gerado_em, total_pedidos, "
                "round(extract(epoch FROM now() - gerado_em)) AS ha "
                "FROM relatorios ORDER BY gerado_em DESC LIMIT 1"
            ).fetchone()
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).splitlines()[0][:160]
        itens.append(_item("banco", "Banco de dados e catalogo", "7 - StatefulSet", "falha", msg))
        if "does not exist" in msg:
            itens[-1]["detalhe"] += " (o Job db-migrate rodou?)"
        itens.append(_item("worker", "Worker processando pedidos", "8 / Serverless", "aviso", "sem banco"))
        itens.append(_item("relatorio", "Relatorio do CronJob", "8 - CronJob", "aviso", "sem banco"))
        return itens

    if n_prod > 0:
        itens.append(_item("banco", "Banco de dados e catalogo", "7 - StatefulSet", "ok",
                           f"conectado a {config.DB_HOST}; {n_prod} produtos (migracao executada)"))
    else:
        itens.append(_item("banco", "Banco de dados e catalogo", "7 - StatefulSet", "falha",
                           "conectado, mas catalogo vazio: rode o Job db-migrate"))

    if ultimo:
        itens.append(_item("worker", "Worker processando pedidos", "8 / Serverless", "ok",
                           f"ultimo pedido processado por {ultimo['processado_por']} ha {int(ultimo['ha'])}s"))
    else:
        itens.append(_item("worker", "Worker processando pedidos", "8 / Serverless", "aviso",
                           "nenhum pedido processado ainda: gere pedidos no painel"))

    if rel:
        itens.append(_item("relatorio", "Relatorio do CronJob", "8 - CronJob", "ok",
                           f"gerado por {rel['gerado_por']} ha {int(rel['ha'])}s "
                           f"({rel['total_pedidos']} pedidos)"))
    else:
        itens.append(_item("relatorio", "Relatorio do CronJob", "8 - CronJob", "aviso",
                           "nenhum relatorio ainda: aguarde o agendamento ou crie um Job a partir do CronJob"))
    return itens


def fila() -> dict:
    try:
        r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT,
                        socket_timeout=2, socket_connect_timeout=2)
        r.ping()
        tamanho = r.llen(config.QUEUE_NAME)
    except redis.RedisError as exc:
        return _item("fila", "Fila de pedidos (Redis)", "8 / Serverless", "falha",
                     f"{config.REDIS_HOST}:{config.REDIS_PORT} inacessivel: {exc.__class__.__name__}")
    return _item("fila", "Fila de pedidos (Redis)", "8 / Serverless", "ok",
                 f"conectado; {tamanho} pedido(s) aguardando na fila '{config.QUEUE_NAME}'")


# ---------------------------------------------------------------- seguranca em runtime

def _proc_status() -> dict:
    campos = {}
    try:
        for linha in Path("/proc/self/status").read_text().splitlines():
            if ":" in linha:
                chave, valor = linha.split(":", 1)
                campos[chave.strip()] = valor.strip()
    except OSError:
        pass
    return campos


def seguranca() -> list[dict]:
    st = _proc_status()
    itens = []

    uid = os.getuid()
    itens.append(_item("nao-root", "Processo nao roda como root", "10 - Seguranca",
                       "ok" if uid != 0 else "falha", f"UID {uid}"))

    try:
        ro = bool(os.statvfs("/").f_flag & os.ST_RDONLY)
    except OSError:
        ro = False
    itens.append(_item("fs-somente-leitura", "Sistema de arquivos raiz somente leitura", "10 - Seguranca",
                       "ok" if ro else "falha",
                       "readOnlyRootFilesystem ativo" if ro else "a raiz '/' aceita escrita"))

    cap = st.get("CapEff")
    if cap is None:
        itens.append(_item("capabilities", "Capabilities removidas (drop ALL)", "10 - Seguranca", "aviso",
                           "/proc indisponivel"))
    else:
        zerado = int(cap, 16) == 0
        itens.append(_item("capabilities", "Capabilities removidas (drop ALL)", "10 - Seguranca",
                           "ok" if zerado else "falha", f"CapEff={cap}"))

    nnp = st.get("NoNewPrivs")
    itens.append(_item("escalacao", "Sem escalacao de privilegio", "10 - Seguranca",
                       "ok" if nnp == "1" else "falha",
                       "allowPrivilegeEscalation: false" if nnp == "1" else f"NoNewPrivs={nnp}"))

    sec = st.get("Seccomp")
    itens.append(_item("seccomp", "Perfil seccomp aplicado", "10 - Seguranca",
                       "ok" if sec == "2" else "falha",
                       "seccomp em modo filtro (RuntimeDefault)" if sec == "2" else f"Seccomp={sec}"))
    return itens


def _ler(caminho: str) -> str:
    try:
        return Path(caminho).read_text().strip()
    except OSError:
        return ""


def limites() -> dict:
    mem = _ler("/sys/fs/cgroup/memory.max")
    cpu = _ler("/sys/fs/cgroup/cpu.max")
    if not mem and not cpu:  # cgroup v1
        mem_v1 = _ler("/sys/fs/cgroup/memory/memory.limit_in_bytes")
        quota = _ler("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
        mem = "max" if not mem_v1 or int(mem_v1) > 2**60 else mem_v1
        cpu = "max" if not quota or quota == "-1" else f"{quota} 100000"
    mem_ok = bool(mem) and mem != "max"
    cpu_ok = bool(cpu) and not cpu.startswith("max")
    partes = []
    if mem_ok:
        partes.append(f"memoria {int(mem) // (1024 * 1024)}Mi")
    if cpu_ok:
        quota, periodo = cpu.split()
        partes.append(f"CPU {int(int(quota) * 1000 / int(periodo))}m")
    if mem_ok and cpu_ok:
        return _item("limites", "Limites de CPU e memoria", "4 / 10", "ok", ", ".join(partes))
    faltam = [n for n, ok in (("memoria", mem_ok), ("CPU", cpu_ok)) if not ok]
    return _item("limites", "Limites de CPU e memoria", "4 / 10", "falha",
                 "sem limite de " + " e ".join(faltam))


# ---------------------------------------------------------------- agregador

def _seguro(funcao, id_, titulo):
    """Um erro inesperado em uma verificacao nao pode derrubar o painel inteiro."""
    try:
        return funcao()
    except Exception as exc:  # noqa: BLE001
        return _item(id_, titulo, "-", "aviso", f"erro na verificacao: {exc.__class__.__name__}: {exc}")


def diagnostico() -> dict:
    zona, item_zona = "", None
    try:
        zona, item_zona = zona_do_no()
    except Exception as exc:  # noqa: BLE001
        item_zona = _item("zona", "Zona de disponibilidade do no", "9 - RBAC", "aviso",
                          f"erro na verificacao: {exc}")
    verificacoes = [
        _seguro(identidade, "identidade", "Identidade via Downward API"),
        item_zona,
        _seguro(menor_privilegio, "menor-privilegio", "Menor privilegio: nao le Secrets"),
        _seguro(segredo, "segredo", "Senha do banco vinda de Secret"),
    ]
    verificacoes += banco_e_processamento()
    verificacoes.append(_seguro(fila, "fila", "Fila de pedidos (Redis)"))
    try:
        verificacoes += seguranca()
    except Exception as exc:  # noqa: BLE001
        verificacoes.append(_item("seguranca", "Seguranca em runtime", "10 - Seguranca", "aviso",
                                  f"erro na verificacao: {exc}"))
    verificacoes.append(_seguro(limites, "limites", "Limites de CPU e memoria"))
    return {
        "servico": "store-api",
        "versao": config.APP_VERSION,
        "ambiente": config.APP_ENV,
        "pod": config.POD_NAME or os.uname().nodename,
        "namespace": config.POD_NAMESPACE,
        "no": config.NODE_NAME,
        "zona": zona,
        "verificacoes": verificacoes,
    }
