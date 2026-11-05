"""Configuracao lida de variaveis de ambiente.

Todas as variaveis sao documentadas no README do repositorio. Nenhum valor
sensivel tem default: sem configuracao, o servico sobe mas o painel acusa.
"""
import os
from pathlib import Path

APP_VERSION = os.getenv("APP_VERSION", "dev")
APP_ENV = os.getenv("APP_ENV", "nao-definido")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "fiapstore")
DB_USER = os.getenv("DB_USER", "fiapstore")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
QUEUE_NAME = os.getenv("QUEUE_NAME", "pedidos")

# Preenchidos pela Downward API no Kubernetes
POD_NAME = os.getenv("POD_NAME", "")
POD_NAMESPACE = os.getenv("POD_NAMESPACE", "")
NODE_NAME = os.getenv("NODE_NAME", "")

# Acesso a API do Kubernetes (sobrescreviveis apenas para testes locais)
K8S_API_URL = os.getenv("K8S_API_URL", "https://kubernetes.default.svc")
K8S_SA_DIR = Path(os.getenv("K8S_SA_DIR", "/var/run/secrets/kubernetes.io/serviceaccount"))


def db_password() -> tuple[str, str]:
    """Retorna (senha, origem). Preferencia: arquivo montado de um Secret."""
    path = os.getenv("DB_PASSWORD_FILE")
    if path:
        try:
            return Path(path).read_text(encoding="utf-8").strip(), "arquivo"
        except OSError:
            return "", "arquivo-ilegivel"
    pwd = os.getenv("DB_PASSWORD")
    if pwd:
        return pwd, "variavel"
    return "", "ausente"
