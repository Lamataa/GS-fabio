"""Gera um relatorio consolidado de vendas e grava na tabela `relatorios`.

Uso no Kubernetes: CronJob `store-report`, mesma imagem do store-worker,
comando `python -m worker.relatorio`. Termina com codigo 0 em caso de sucesso.
"""
import sys

from . import config, db


def main() -> None:
    try:
        with db.conectar() as conn:
            r = conn.execute(
                "SELECT count(*) AS total, "
                "count(*) FILTER (WHERE status = 'processado') AS processados, "
                "count(*) FILTER (WHERE status = 'pendente') AS pendentes, "
                "coalesce(sum(valor), 0) AS valor_total FROM pedidos"
            ).fetchone()
            conn.execute(
                "INSERT INTO relatorios (gerado_por, total_pedidos, processados, pendentes, valor_total) "
                "VALUES (%s, %s, %s, %s, %s)",
                (config.POD_NAME, r["total"], r["processados"], r["pendentes"], r["valor_total"]),
            )
    except Exception as exc:  # noqa: BLE001
        print(f"[relatorio] falhou: {exc}", flush=True)
        sys.exit(1)
    print(f"[relatorio] {r['total']} pedidos ({r['processados']} processados, "
          f"{r['pendentes']} pendentes), total R$ {r['valor_total']:.2f}", flush=True)


if __name__ == "__main__":
    main()
