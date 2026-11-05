import psycopg
from psycopg.rows import dict_row

from . import config


def conectar():
    return psycopg.connect(
        host=config.DB_HOST, port=config.DB_PORT, dbname=config.DB_NAME,
        user=config.DB_USER, password=config.db_password(),
        connect_timeout=3, row_factory=dict_row,
    )
