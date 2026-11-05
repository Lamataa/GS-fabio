# ---------- estagio 1: dependencias ----------
FROM python:3.12-slim AS build
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- estagio 2: imagem final ----------
FROM python:3.12-slim

# A versao e gravada na imagem no momento do build:
#   docker buildx build --build-arg APP_VERSION=2.0 ...
ARG APP_VERSION=1.0
ENV APP_VERSION=${APP_VERSION} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=build /install /usr/local
WORKDIR /app
COPY app ./app

# Usuario nao-root com UID numerico (exigido por runAsNonRoot no Kubernetes)
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin fiap
USER 10001

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
