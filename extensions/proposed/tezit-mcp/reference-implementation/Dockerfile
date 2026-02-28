FROM python:3.12-slim AS base

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir . \
    && addgroup --system tez && adduser --system --ingroup tez tez \
    && mkdir -p /data/bundles /data/keys /data/db \
    && chown -R tez:tez /data

USER tez

VOLUME /data

EXPOSE 8100

CMD ["uvicorn", "tez.server:app", "--host", "127.0.0.1", "--port", "8100"]
