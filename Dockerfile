FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY docker/app-entrypoint.sh /usr/local/bin/spoonfuls-app
RUN chmod 0755 /usr/local/bin/spoonfuls-app

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/spoonfuls-app"]
