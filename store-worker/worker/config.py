import os
from pathlib import Path

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "fiapstore")
DB_USER = os.getenv("DB_USER", "fiapstore")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
QUEUE_NAME = os.getenv("QUEUE_NAME", "pedidos")

# Tempo simulado de processamento de cada pedido, em segundos
PROCESS_SECONDS = float(os.getenv("PROCESS_SECONDS", "2"))

POD_NAME = os.getenv("POD_NAME") or os.uname().nodename


def db_password() -> str:
    path = os.getenv("DB_PASSWORD_FILE")
    if path:
        return Path(path).read_text(encoding="utf-8").strip()
    return os.getenv("DB_PASSWORD", "")
