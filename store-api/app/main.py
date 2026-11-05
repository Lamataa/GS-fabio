"""FIAP Store - store-api.

Rotas de sonda ficam na raiz (/health, /ready, /metrics); rotas de negocio
ficam sob /api, que e o prefixo que o Ingress encaminha para este servico.
"""
import random
import time
from decimal import Decimal

import redis
from fastapi import FastAPI, HTTPException, Query, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from pydantic import BaseModel, Field

from . import config, db, plataforma

app = FastAPI(title="FIAP Store API", version=config.APP_VERSION)

PEDIDOS_CRIADOS = Counter("fiapstore_pedidos_criados_total", "Pedidos criados pela API")


def _fila() -> redis.Redis:
    return redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT,
                       socket_timeout=2, socket_connect_timeout=2)


def _num(valor):
    return float(valor) if isinstance(valor, Decimal) else valor


# ------------------------------------------------------------------ sondas

@app.get("/health")
def health():
    """Liveness: o processo esta vivo. Nao consulta dependencias, de proposito."""
    return {"status": "ok", "versao": config.APP_VERSION}


@app.get("/ready")
def ready(response: Response):
    """Readiness: so recebe trafego se conseguir falar com o banco."""
    try:
        with db.conectar() as conn:
            conn.execute("SELECT 1")
    except Exception:  # noqa: BLE001
        response.status_code = 503
        return {"status": "sem-banco"}
    return {"status": "pronto"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ------------------------------------------------------------------ negocio

@app.get("/api/produtos")
def listar_produtos():
    with db.conectar() as conn:
        linhas = conn.execute("SELECT id, nome, preco FROM produtos ORDER BY id").fetchall()
    return [{**l, "preco": _num(l["preco"])} for l in linhas]


class NovoPedido(BaseModel):
    produto_id: int
    quantidade: int = Field(default=1, ge=1, le=20)


def _criar_pedidos(itens: list[tuple[int, int]]) -> list[int]:
    ids = []
    with db.conectar() as conn:
        for produto_id, quantidade in itens:
            prod = conn.execute("SELECT preco FROM produtos WHERE id = %s", (produto_id,)).fetchone()
            if not prod:
                raise HTTPException(status_code=404, detail=f"produto {produto_id} inexistente")
            linha = conn.execute(
                "INSERT INTO pedidos (produto_id, quantidade, valor, criado_por) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (produto_id, quantidade, prod["preco"] * quantidade, config.POD_NAME or "local"),
            ).fetchone()
            ids.append(linha["id"])
    try:
        fila = _fila()
        for pid in ids:
            fila.lpush(config.QUEUE_NAME, pid)
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail=f"pedido gravado, mas a fila esta fora: {exc}") from exc
    PEDIDOS_CRIADOS.inc(len(ids))
    return ids


@app.post("/api/pedidos", status_code=201)
def criar_pedido(pedido: NovoPedido):
    ids = _criar_pedidos([(pedido.produto_id, pedido.quantidade)])
    return {"id": ids[0], "status": "pendente"}


@app.post("/api/pedidos/lote", status_code=201)
def criar_lote(quantidade: int = Query(default=50, ge=1, le=500)):
    """Gera pedidos aleatorios. Usado para demonstrar o worker escalando a partir de zero."""
    with db.conectar() as conn:
        ids_prod = [r["id"] for r in conn.execute("SELECT id FROM produtos").fetchall()]
    if not ids_prod:
        raise HTTPException(status_code=409, detail="catalogo vazio: rode o Job db-migrate")
    ids = _criar_pedidos([(random.choice(ids_prod), random.randint(1, 3)) for _ in range(quantidade)])
    return {"criados": len(ids), "primeiro": ids[0], "ultimo": ids[-1]}


@app.get("/api/pedidos")
def listar_pedidos(limite: int = Query(default=20, ge=1, le=200)):
    with db.conectar() as conn:
        linhas = conn.execute(
            "SELECT p.id, pr.nome AS produto, p.quantidade, p.valor, p.status, "
            "p.criado_em, p.criado_por, p.processado_em, p.processado_por "
            "FROM pedidos p JOIN produtos pr ON pr.id = p.produto_id "
            "ORDER BY p.id DESC LIMIT %s",
            (limite,),
        ).fetchall()
        resumo = conn.execute(
            "SELECT count(*) FILTER (WHERE status = 'pendente') AS pendentes, "
            "count(*) FILTER (WHERE status = 'processado') AS processados FROM pedidos"
        ).fetchone()
    return {"resumo": resumo, "pedidos": [{**l, "valor": _num(l["valor"])} for l in linhas]}


@app.get("/api/relatorios")
def listar_relatorios(limite: int = Query(default=5, ge=1, le=50)):
    with db.conectar() as conn:
        linhas = conn.execute(
            "SELECT * FROM relatorios ORDER BY gerado_em DESC LIMIT %s", (limite,)
        ).fetchall()
    return [{**l, "valor_total": _num(l["valor_total"])} for l in linhas]


@app.get("/api/plataforma")
def diagnostico_plataforma():
    return plataforma.diagnostico()


@app.get("/api/carga")
def gerar_carga(ms: int = Query(default=200, ge=1, le=2000)):
    """Queima CPU por `ms` milissegundos. Serve para provocar o HPA."""
    fim = time.perf_counter() + ms / 1000
    n = 0
    while time.perf_counter() < fim:
        n += 1
    return {"pod": config.POD_NAME, "iteracoes": n}
