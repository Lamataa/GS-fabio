"""FIAP Store - store-worker.

Consome IDs de pedido da lista Redis `pedidos` e marca cada um como
processado. Foi feito para escalar a partir de ZERO com o KEDA: quando a
fila esvazia, todas as replicas podem ser removidas.

Ao receber SIGTERM, termina o pedido em andamento e sai (graceful shutdown).
"""
import signal
import sys
import time

import redis

from . import config, db

rodando = True


def parar(signum, _frame):
    global rodando
    print(f"[worker] sinal {signum} recebido: terminando o pedido atual e saindo", flush=True)
    rodando = False


def processar(fila: redis.Redis, pedido_id: int) -> None:
    time.sleep(config.PROCESS_SECONDS)
    try:
        with db.conectar() as conn:
            conn.execute(
                "UPDATE pedidos SET status = 'processado', processado_em = now(), processado_por = %s "
                "WHERE id = %s",
                (config.POD_NAME, pedido_id),
            )
    except Exception as exc:  # noqa: BLE001
        # Devolve o pedido para a fila para nao perde-lo
        fila.rpush(config.QUEUE_NAME, pedido_id)
        print(f"[worker] falha ao gravar pedido {pedido_id}, devolvido a fila: {exc}", flush=True)
        time.sleep(2)
        return
    print(f"[worker] {config.POD_NAME} processou o pedido {pedido_id}", flush=True)


def main() -> None:
    signal.signal(signal.SIGTERM, parar)
    signal.signal(signal.SIGINT, parar)
    fila = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT,
                       socket_timeout=10, socket_connect_timeout=3)
    print(f"[worker] {config.POD_NAME} consumindo '{config.QUEUE_NAME}' em "
          f"{config.REDIS_HOST}:{config.REDIS_PORT}", flush=True)
    while rodando:
        try:
            item = fila.brpop([config.QUEUE_NAME], timeout=2)
        except redis.RedisError as exc:
            print(f"[worker] fila inacessivel: {exc}", flush=True)
            time.sleep(3)
            continue
        if item:
            processar(fila, int(item[1]))
    print("[worker] encerrado", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main()
