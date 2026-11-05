# Nginx que roda como usuario nao-root (UID 101) e escuta na porta 8080.
# Com readOnlyRootFilesystem no Kubernetes, monte um emptyDir em /tmp:
# e onde este nginx grava pid e arquivos temporarios.
FROM nginxinc/nginx-unprivileged:1.28-alpine
COPY html/ /usr/share/nginx/html/
EXPOSE 8080
