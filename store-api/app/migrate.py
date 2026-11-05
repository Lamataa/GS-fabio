"""Cria o schema e popula o catalogo. Idempotente: pode rodar varias vezes.

Uso no Kubernetes: Job `db-migrate`, mesma imagem da store-api, comando
`python -m app.migrate`.
"""
import sys
import time

from . import config, db

SCHEMA = """
CREATE TABLE IF NOT EXISTS produtos (
    id     SERIAL PRIMARY KEY,
    nome   TEXT UNIQUE NOT NULL,
    preco  NUMERIC(10, 2) NOT NULL
);
CREATE TABLE IF NOT EXISTS pedidos (
    id             SERIAL PRIMARY KEY,
    produto_id     INT NOT NULL REFERENCES produtos(id),
    quantidade     INT NOT NULL,
    valor          NUMERIC(10, 2) NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pendente',
    criado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
    criado_por     TEXT,
    processado_em  TIMESTAMPTZ,
    processado_por TEXT
);
CREATE TABLE IF NOT EXISTS relatorios (
    id            SERIAL PRIMARY KEY,
    gerado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    gerado_por    TEXT,
    total_pedidos INT NOT NULL,
    processados   INT NOT NULL,
    pendentes     INT NOT NULL,
    valor_total   NUMERIC(12, 2) NOT NULL
);
"""

PRODUTOS = [
    ("Teclado mecanico", 349.90),
    ("Mouse sem fio", 129.90),
    ("Monitor 27 polegadas", 1499.00),
    ("Headset", 259.90),
    ("Webcam Full HD", 219.90),
    ("Cadeira ergonomica", 1899.00),
    ("Hub USB-C", 159.90),
    ("SSD 1 TB", 449.90),
]


def aguardar_banco(timeout: int = 90) -> None:
    inicio = time.time()
    while True:
        try:
            with db.conectar() as conn:
                conn.execute("SELECT 1")
            return
        except Exception as exc:  # noqa: BLE001
            if time.time() - inicio > timeout:
                print(f"[migrate] banco indisponivel apos {timeout}s: {exc}", flush=True)
                sys.exit(1)
            print(f"[migrate] aguardando banco em {config.DB_HOST}:{config.DB_PORT}...", flush=True)
            time.sleep(3)


def main() -> None:
    aguardar_banco()
    with db.conectar() as conn:
        conn.execute(SCHEMA)
        for nome, preco in PRODUTOS:
            conn.execute(
                "INSERT INTO produtos (nome, preco) VALUES (%s, %s) ON CONFLICT (nome) DO NOTHING",
                (nome, preco),
            )
        total = conn.execute("SELECT count(*) AS n FROM produtos").fetchone()["n"]
    print(f"[migrate] schema ok, {total} produtos no catalogo", flush=True)


if __name__ == "__main__":
    main()
