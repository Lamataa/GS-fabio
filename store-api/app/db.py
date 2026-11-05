"""Acesso ao PostgreSQL.

Uma conexao por operacao, de proposito: e simples, e sobrevive sem truques a
reinicios do banco (o que acontece nos desafios de persistencia).
"""
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from . import config


@contextmanager
def conectar():
    senha, _ = config.db_password()
    conn = psycopg.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=senha,
        connect_timeout=3,
        row_factory=dict_row,
    )
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
