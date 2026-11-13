# образ для любой контейнерной платформы: Northflank, Cloud Run, Back4app, Railway
FROM python:3.13-slim

# сайт не требует зависимостей: только стандартная библиотека
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8000

COPY server.py content.py seo_pages.py ops.py requirements.txt ./
COPY templates ./templates
COPY static ./static

# data/ — единственная папка, которая должна переживать перезапуск:
# к ней платформа подключает постоянный диск (volume)
RUN mkdir -p /app/data /app/backups
VOLUME ["/app/data", "/app/backups"]

EXPOSE 8000

# порт берётся из PORT, который выдаёт платформа
CMD ["python", "server.py"]
