# Ciel Agent API. Built from the repository root (docker-compose.yml sets
# context ../..). Only the service lock and the modules the service imports
# go into the image. Python patch tag matches the CI and test venv (3.14.7);
# check the tag exists on the first build and bump it here with the lock.
FROM python:3.14.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN useradd --system --uid 10001 --no-create-home ciel && mkdir /data && chown ciel /data

WORKDIR /app

COPY requirements-agent.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements-agent.txt

COPY agent_api ./agent_api
COPY guard ./guard
COPY chat_store.py ./
COPY account_settings.py ./
COPY account_ids.py ./
COPY agent_consent.py ./

USER ciel

# One worker: running tasks and their sockets live in this process.
# Port 8000 is reached only by Caddy, so its X-Forwarded-For is trusted.
# WebSocket frames above 256 KB are refused before they are buffered.
CMD ["uvicorn", "agent_api.main:production_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*", "--ws-max-size", "262144"]
