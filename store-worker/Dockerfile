# ---------- estagio 1: dependencias ----------
FROM python:3.12-slim AS build
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- estagio 2: imagem final ----------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY --from=build /install /usr/local
WORKDIR /app
COPY worker ./worker

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin fiap
USER 10001

# Padrao: consumidor da fila. O CronJob troca o comando para:
#   python -m worker.relatorio
CMD ["python", "-m", "worker.main"]
