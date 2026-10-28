# Ciel backend on a VPS

Runbook for running Ciel's backend (Langflow, its Postgres database and Ollama behind
a Caddy + nginx gateway) on one VPS. The Streamlit app is unchanged: only the values of
`NGROK_URL`, `NGROK_USER` and `NGROK_PASSWORD` in its secrets point at the new host.

```
internet -> caddy :443 (TLS) -> nginx :8080 (Basic Auth, allowlist, rate limit) -> langflow :7860
                                                                                  postgres
                                                                                  ollama (shares langflow's network)
```

Only `caddy` publishes public ports (80, 443). `langflow` listens on `127.0.0.1:7860`
of the VPS for the SSH tunnel and the scripts. nginx's port 8080 is internal.

All commands below run as root (or with `sudo`) on the VPS, in `/opt/ciel/deploy/vps`
unless a step says otherwise.

## 1. VPS requirements

- Ubuntu 24.04 LTS
- at least 4 vCPU, 8 GB RAM, 80 GB SSD
- region Singapore or Jakarta (close to the users and to Supabase)
- a public IPv4 address (and IPv6 if offered)
- DNS: record `api` for `ciel-ai.web.id` (A, and AAAA if the VPS has IPv6) pointing at the
  VPS, **DNS only** (grey cloud in Cloudflare). Caddy needs this to get its certificate.

## 2. Harden the host

```bash
apt update && apt upgrade -y
ufw allow 22,80,443/tcp
ufw enable
```

SSH by key only: put your public key in `~/.ssh/authorized_keys`, then in
`/etc/ssh/sshd_config.d/10-ciel.conf` set

```
PasswordAuthentication no
PermitRootLogin prohibit-password
```

and `systemctl reload ssh`. Open a second SSH session to confirm the key still works
before closing the first.

```bash
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

## 3. Install Docker, restic and the script dependencies

```bash
apt install -y docker.io docker-compose-v2 restic python3-requests python3-dotenv git
systemctl enable --now docker
docker compose version
```

`python3-requests python3-dotenv` are for `tools/render_nginx_gateway.py` and the scripts
in `tools/`; restic is for the backups.

## 4. Get the code

```bash
git clone https://github.com/Gibran-cult/ciel-ai-assistant.git /opt/ciel
cd /opt/ciel/deploy/vps
```

(Use the repository's actual URL and a deploy key or token if it is private.)

## 5. Fill in `.env`

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

`.env` is git-ignored. Every name is described in `.env.example`; enter the values
yourself (generate `LANGFLOW_SECRET_KEY` with `openssl rand -hex 32`).

`LANGFLOW_API_KEY` cannot exist yet: leave it empty now and fill it in step 10.

**Save `LANGFLOW_SECRET_KEY` in a password manager outside the VPS**, the same as
`RESTIC_PASSWORD`. Langflow's stored credentials in Postgres are encrypted with it, so a
restore without it cannot read them; the same goes for the backups without `RESTIC_PASSWORD`.

`NGROK_USER`, `NGROK_PASSWORD` and the four flow IDs are the same names the Streamlit app
and the ngrok policy use. The renderer refuses to run without the flow IDs, so start with the
ones from the laptop's `.env`; step 10 checks that the imported flows kept those IDs.

## 6. Generate the gateway config

```bash
cd /opt/ciel
python3 tools/render_nginx_gateway.py --env-file deploy/vps/.env
cd deploy/vps
```

This writes `nginx/ciel.conf` and `nginx/ciel.htpasswd` (both git-ignored). It prints
nothing secret. Rerun it whenever `NGROK_USER`, `NGROK_PASSWORD`, a flow ID or
`GATEWAY_RUN_PER_MINUTE` changes, then `docker compose restart nginx`.

## 7. Start the stack

```bash
docker compose up -d
docker compose ps          # 5 services running
docker compose exec nginx nginx -t
```

`nginx -t` must say the syntax is ok and the test is successful.

Check that Langflow's home directory is where the volume is mounted:

```bash
docker compose exec langflow python -c "import pathlib; print(pathlib.Path.home())"
```

It must print `/app/data`. If it prints something else, change the `langflow_home` mount
target in `docker-compose.yml` to that path, update `tests/test_vps_deploy.py` to match
and rerun it, then `docker compose up -d` again. Otherwise Langflow's files (logs,
uploaded images) would not survive a container being recreated.

nginx resolves `langflow` once, when it starts. After Langflow is **recreated** (an image
upgrade, `docker compose up -d --force-recreate`, a changed environment) its container
address changes and nginx keeps the old one, so run

```bash
docker compose restart nginx
```

A plain `docker compose restart langflow` keeps the address, so nginx keeps working, but
**ollama** shares Langflow's network namespace and stays attached to the old one: restart
it too (Compose does this for `restart langflow` and `up -d`, and the cron job below does it
within a minute whatever restarted Langflow, e.g. an out-of-memory kill):

```bash
docker compose restart langflow ollama
```

After Langflow is recreated, restart both ollama and nginx (`docker compose restart ollama nginx`).

Then the real check, through Caddy, with the gateway's Basic Auth user:

```bash
set -a; . ./.env; set +a
curl -u "$NGROK_USER:$NGROK_PASSWORD" https://api.ciel-ai.web.id/health_check   # 200
curl -s -o /dev/null -w '%{http_code}\n' https://api.ciel-ai.web.id/health_check  # 401
```

The first must answer 200 (Caddy's certificate can take a minute on the first start; see
`docker compose logs caddy`). Without `-u` it must be 401.

## 8. Pull the Ollama models

The embedding model must be the same build as on the laptop: a different
`nomic-embed-text-v2-moe` build gives different vectors and silently breaks memory search
on the stored ones.

```bash
docker compose exec ollama ollama pull nomic-embed-text-v2-moe:latest
docker compose exec ollama ollama pull qwen2.5vl:3b
docker compose exec ollama ollama list
```

On the laptop run `ollama list` and compare the **ID** column for both models. If the
embedding model's ID differs, stop and tell Ciel before importing any data.

## 9. Open the Langflow UI

Langflow is not public. From your own machine:

```bash
ssh -L 7860:127.0.0.1:7860 root@<vps-ip>
```

then open http://127.0.0.1:7860 and sign in with `LANGFLOW_SUPERUSER` and
`LANGFLOW_SUPERUSER_PASSWORD`.

## 10. Restore the flows and create the API key

In the Langflow UI: import the flows (the JSON files under `flow/` in the repository
and the Langflow backup), check that each component still has its model name and keys
(the settings are not in Git), create an API key, and put it in `.env` as
`LANGFLOW_API_KEY`. Compare each imported flow's ID with `FLOW_ID`,
`MEMORY_ADMIN_FLOW_ID`, `RESEARCH_FLOW_ID` and `WRITER_FLOW_ID` in `.env`; if one differs,
fix `.env`, rerun step 6 and `docker compose restart nginx`.

## 11. Backups and scheduled jobs

Placeholder: Task 5 fills in the cron lines for the nightly backup, the monthly restore
check and the chat-history retention here.

## 12. Point the app at the VPS

In Streamlit Cloud's secrets set `NGROK_URL = "https://api.ciel-ai.web.id"` and keep the
same `NGROK_USER` / `NGROK_PASSWORD`. Reboot the app and ask Ciel a question.

## Rollback to the laptop

The laptop backend stays as it is until the VPS has run for 14 days without a problem.
To go back:

1. Re-enable the laptop's watchdog task and ngrok (see the keep-alive notes).
2. In Streamlit Cloud's secrets set `NGROK_URL`, `NGROK_USER` and `NGROK_PASSWORD` back to
   the laptop's values and reboot the app.
3. Memories written on the VPS in the meantime are not on the laptop. Export them first if
   they matter.

The VPS can stay up while you do this; nothing on the laptop depends on it.

## Everyday commands

```bash
cd /opt/ciel/deploy/vps
docker compose ps
docker compose logs --tail 100 langflow
docker compose pull && docker compose up -d && docker compose restart ollama nginx   # only after changing a pinned tag
```

Keep Ollama attached to Langflow. Root's crontab (`crontab -e`) gets this line, which
restarts the ollama container within a minute whenever Langflow cannot reach it on
`127.0.0.1:11434` (`/var/log/ciel` must exist: `mkdir -p /var/log/ciel`):

```
* * * * * cd /opt/ciel/deploy/vps && ./ollama_link_check.sh >> /var/log/ciel/ollama_link_check.log 2>&1
```

Make the script executable once: `chmod +x ollama_link_check.sh`.

Image tags are pinned in `docker-compose.yml`; change one on purpose, in Git, and rerun
`python -m unittest tests.test_vps_deploy`.
