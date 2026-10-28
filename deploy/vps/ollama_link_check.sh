#!/usr/bin/env bash
# Ollama lives in Langflow's network namespace (network_mode: "service:langflow").
# When the langflow container restarts, ollama stays attached to the old, dead
# namespace and Langflow's 127.0.0.1:11434 goes nowhere: memory search and image
# reading break without any error on the surface.
#
# This probes Ollama from inside Langflow and restarts the ollama container when
# the probe fails. Run from /opt/ciel/deploy/vps, every minute (see README.md).
# Prints one line (UTC) only when it had to restart, so the log stays short.
set -euo pipefail

# Only a running Langflow can be probed. While it is paused (the nightly backup),
# stopped, restarting or not created yet, the probe would fail and restart Ollama
# every minute for nothing: do nothing until it runs again.
langflow=$(docker compose ps -a -q langflow)
if [ -z "$langflow" ] || [ "$(docker inspect -f '{{.State.Status}}' "$langflow")" != running ]; then
  exit 0
fi

if ! docker compose exec -T langflow python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:11434/api/version', timeout=5)" \
  >/dev/null 2>&1; then
  docker compose restart ollama >/dev/null
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) ollama was unreachable from langflow on 127.0.0.1:11434: restarted ollama"
fi
