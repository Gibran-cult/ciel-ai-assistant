# The Streamlit app (app.py) for the app VPS. Built by docker-compose.yml in
# this directory with the repository root as the build context; .dockerignore
# at the root keeps secrets, tests and docs out of the image.
FROM python:3.14.8-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, so a code-only change reuses this layer.
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

# The code stays owned by root: the app only reads it. Secrets arrive at run
# time as a read-only mount at /app/.streamlit/secrets.toml.
COPY . .
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin ciel
USER ciel

EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
