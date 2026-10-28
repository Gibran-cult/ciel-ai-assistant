# Ciel backend on a VPS

Runbook for running Ciel's backend (Langflow, its Postgres database and Ollama behind
a Caddy + nginx gateway) on one VPS. The Streamlit app's code is unchanged; its secrets
switch to the new host, the VPS Langflow API key and the new flow IDs (step 12).

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
- a public IPv4 address
- DNS: record `api` for `ciel-ai.web.id`, an **A record only** (no AAAA, even if the VPS
  has IPv6), pointing at the VPS, **DNS only** (grey cloud in Cloudflare). Caddy needs this
  to get its certificate. No AAAA because Docker's userland proxy would hand IPv6 clients
  to Caddy from one internal address, so they would all share one rate-limit key.

## 2. Harden the host

```bash
apt update && apt upgrade -y
timedatectl set-timezone UTC
ufw allow 22,80,443/tcp
ufw enable
```

The clock is set to UTC because every cron time in this runbook is UTC.

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
yourself. Generate `POSTGRES_PASSWORD`, `LANGFLOW_SECRET_KEY`, `NGROK_PASSWORD` and
`RESTIC_PASSWORD` with

```bash
openssl rand -hex 32
```

(one run per value; hex never needs quoting). Keep `$ @ # : / %` out of every value you
choose (passwords, user names): the same file is read by Docker Compose and sourced by the
shell, and Langflow puts `POSTGRES_PASSWORD` into a connection URL. A value that cannot avoid
such characters, like the Supabase pooler URL in step 11, goes in single quotes:
`SUPABASE_DB_URL='postgresql://...'`.

`LANGFLOW_API_KEY` cannot exist yet: leave it empty now and fill it in step 10.

**Save `LANGFLOW_SECRET_KEY` in a password manager outside the VPS**, the same as
`RESTIC_PASSWORD`. Langflow's stored credentials in Postgres are encrypted with it, so a
restore without it cannot read them; the same goes for the backups without `RESTIC_PASSWORD`.

`NGROK_USER`, `NGROK_PASSWORD` and the four flow IDs are the same names the Streamlit app
and the ngrok policy use. The renderer refuses to run without the flow IDs, but the VPS
flows only get theirs in step 10: the migration creates every flow with a new ID. Until
then put the laptop's flow IDs in as placeholders; step 10 replaces them.

## 6. Generate the gateway config

```bash
cd /opt/ciel
python3 tools/render_nginx_gateway.py --env-file deploy/vps/.env
cd deploy/vps
```

This writes `nginx/ciel.conf` and `nginx/ciel.htpasswd` (both git-ignored) and prints the
flow IDs it used (nothing secret). `.env` is the source of truth for the renderer: with
`--env-file` its names win over anything exported in the shell (for example by an earlier
`set -a; . ./.env`), so edit `.env`, never an exported variable. Rerun it whenever
`NGROK_USER`, `NGROK_PASSWORD`, a flow ID or `GATEWAY_RUN_PER_MINUTE` changes, then
`docker compose restart nginx`.

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

Then the real check, through Caddy, with the gateway's Basic Auth user:

```bash
set -a; . ./.env; set +a
curl -u "$NGROK_USER:$NGROK_PASSWORD" https://api.ciel-ai.web.id/health_check   # 200
curl -s -o /dev/null -w '%{http_code}\n' https://api.ciel-ai.web.id/health_check  # 401
```

The first must answer 200 (Caddy's certificate can take a minute on the first start; see
`docker compose logs caddy`). Without `-u` it must be 401.

### When Langflow restarts

Langflow's container can come back with a different address after any restart or
recreation (`docker compose restart langflow`, an image upgrade,
`docker compose up -d --force-recreate`, a changed environment, an out-of-memory kill).
nginx follows it on its own: the generated upstream has the `resolve` flag and asks Docker's
DNS again every 10 seconds, so nginx does not need a restart.

**ollama** is different: it shares Langflow's network namespace and stays attached to the old
one. Restart it together with Langflow:

```bash
docker compose restart langflow ollama
```

Compose also does this for `restart langflow` and `up -d`, and the cron job under "Everyday
commands" does it within a minute whatever restarted Langflow.

Check it once on the VPS, after the stack is up:

```bash
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' "$(docker compose ps -q langflow)"
docker compose restart langflow
# wait until Langflow is up again (about a minute; docker compose logs -f langflow)
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' "$(docker compose ps -q langflow)"
curl -s -o /dev/null -w '%{http_code}\n' -u "$NGROK_USER:$NGROK_PASSWORD" https://api.ciel-ai.web.id/health_check   # 200
```

Note both addresses. Whether or not they differ, the last command must print 200 without
nginx being restarted. If it does not, run `docker compose logs nginx` and stop here.

## 8. Pull the Ollama models

The embedding model must be the same build as on the laptop: a different
`nomic-embed-text-v2-moe` build gives different vectors and silently breaks memory search
on the stored ones.

On the laptop run `ollama list` and copy the **ID** of `nomic-embed-text-v2-moe:latest`
into `.env` on the VPS as `OLLAMA_EMBED_MODEL_ID`. Then on the VPS:

```bash
docker compose exec ollama ollama pull nomic-embed-text-v2-moe:latest
docker compose exec ollama ollama pull qwen2.5vl:3b
docker compose exec ollama ollama list
set -a; . ./.env; set +a
echo "laptop: $OLLAMA_EMBED_MODEL_ID"
docker compose exec -T ollama ollama list | awk '$1 == "nomic-embed-text-v2-moe:latest" {print "vps:    " $2}'
```

The two IDs must be identical; compare `qwen2.5vl:3b` with the laptop's `ollama list` too.
If the embedding model's ID differs, stop and tell Ciel before importing any data. Repeat
this check after any restore or rebuild of the VPS: the models are not in the backups, and
a fresh pull of `:latest` can be a newer build.

## 9. Open the Langflow UI

Langflow is not public. From your own machine:

```bash
ssh -L 7860:127.0.0.1:7860 root@<vps-ip>
```

then open http://127.0.0.1:7860 and sign in with `LANGFLOW_SUPERUSER` and
`LANGFLOW_SUPERUSER_PASSWORD`.

## 10. Migrate the flows and create the API key

1. In the VPS Langflow UI (step 9): create an API key and put it in `.env` as
   `LANGFLOW_API_KEY`. Create the global variables `DEEPSEEK_API_KEY` and `EXA_API_KEY`
   and the `GEMINI_API_KEY` credential (the settings are not in Git).
2. On the **laptop**, with the laptop's Langflow running, open a tunnel to the VPS
   Langflow on another local port (7860 is the laptop's own Langflow):

   ```bash
   ssh -L 17860:127.0.0.1:7860 root@<vps-ip>
   ```

3. On the laptop, in the repository, set `SOURCE_LANGFLOW_API_KEY` (a key of the laptop's
   Langflow) and `TARGET_LANGFLOW_API_KEY` (the VPS key from 1) in the environment or the
   laptop's `.env`, then copy the four flows and the sub-flows they call. The `--flow-id`
   values are the laptop's `FLOW_ID`, `RESEARCH_FLOW_ID`, `WRITER_FLOW_ID` and
   `MEMORY_ADMIN_FLOW_ID`:

   ```bash
   mkdir -p ~/.ciel_ai/flow_backups
   python tools/migrate_flows.py --source-url http://127.0.0.1:7860 --target-url http://127.0.0.1:17860 \
     --flow-id <FLOW_ID> --flow-id <RESEARCH_FLOW_ID> --flow-id <WRITER_FLOW_ID> --flow-id <MEMORY_ADMIN_FLOW_ID> \
     --map-out ~/.ciel_ai/flow_backups/vps_id_map.json --snapshot-dir flow/subflows
   ```

   It creates every flow with a **new** ID and points the main flow's Run Flow nodes at the
   new sub-flow IDs (importing through the UI would not). It prints `Imported <old> -> <new>`
   per flow; the map should hold 6 flows. If it stops halfway it lists the flows it already
   created: delete those on the VPS before running it again.
4. On the VPS, put the new IDs of the four flows (the map's values for the laptop IDs) into
   `.env` as `FLOW_ID`, `RESEARCH_FLOW_ID`, `WRITER_FLOW_ID` and `MEMORY_ADMIN_FLOW_ID`.
   Re-render the gateway and restart nginx:

   ```bash
   cd /opt/ciel
   python3 tools/render_nginx_gateway.py --env-file deploy/vps/.env
   cd deploy/vps
   docker compose restart nginx
   ```

   The flow IDs the renderer prints must be the new ones from the map.
5. In the VPS Langflow UI, open each migrated flow and check that every component still has
   its model name and keys.

## 11. Backups and scheduled jobs

Everything the VPS cannot rebuild goes off-site every night: Langflow's Postgres, Langflow's
home volume (the long-term memory) and Supabase (its free plan has no backups). restic
encrypts it and sends it to a Cloudflare R2 bucket; about five weeks are kept.

**Precondition.** The production privacy page must already show the backup notice
(privacy.py change merged and deployed). Check it in the live app before the first
`./backup.sh` and before installing the backup cron line.

One-time setup:

1. Cloudflare R2: create a bucket and an API token with read and write on that bucket only.
   In `.env` set `RESTIC_REPOSITORY` to `s3:https://<account-id>.r2.cloudflarestorage.com/<bucket>`
   (the account ID is on the R2 overview page), `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
   to the token's key pair, and `RESTIC_PASSWORD` to a new value from `openssl rand -hex 32`.
   Keep `RESTIC_PASSWORD` in the password manager (step 5): without it the backups cannot be opened.
2. `SUPABASE_DB_URL` is the Supabase **Session pooler** connection string (Project settings,
   Database, Connection string), in single quotes (step 5). Not the direct one: that host is
   IPv6-only on the free plan and Docker has no IPv6 by default.
3. Healthchecks.io: create two checks and put their ping URLs in `.env` as
   `HEALTHCHECKS_BACKUP_URL` and `HEALTHCHECKS_RESTORE_URL`. The backup check runs daily
   (period 1 day, grace 2 hours). The restore check runs monthly (period 1 month, grace 3 days).
   Set both to email Ciel when a ping is missing. The scripts ping only after they succeed.
4. Initialise the repository once, then make the scripts executable and the log directory:

```bash
set -a; . ./.env; set +a
restic init
chmod +x backup.sh restore_check.sh ollama_link_check.sh
mkdir -p /var/log/ciel
```

5. Run everything once by hand, in a shell that has sourced `.env` first (the scripts read
   their settings from the environment):

```bash
set -a; . ./.env; set +a
docker run --rm --network host postgres:17.2 pg_dump -Fc "$SUPABASE_DB_URL" > /dev/null
./backup.sh
./restore_check.sh
```

   The `pg_dump` line checks the Supabase connection on its own. If it fails with permission
   errors on schemas Supabase owns, add `--schema=public` to the Supabase `pg_dump` line in
   `backup.sh` (in Git) and try again. Then check that both pings arrive (the restore check
   needs a snapshot to exist). The backup refuses to start when `/` is more than 80% full or
   when another backup is still running; the restore check refuses to start without twice the
   latest snapshot's size free in `/var/tmp`.

Root's crontab (`crontab -e`), times in UTC (03:30 WIB for the backup). Each line sources
`.env` first so the scripts get their settings, `LANGFLOW_API_KEY` included:

```
30 20 * * * set -a; . /opt/ciel/deploy/vps/.env; set +a; cd /opt/ciel/deploy/vps && ./backup.sh >> /var/log/ciel/backup.log 2>&1
0 21 1 * * set -a; . /opt/ciel/deploy/vps/.env; set +a; cd /opt/ciel/deploy/vps && ./restore_check.sh >> /var/log/ciel/restore_check.log 2>&1
0 20 * * * set -a; . /opt/ciel/deploy/vps/.env; set +a; python3 /opt/ciel/tools/prune_chat_history.py --days 30 --base-url http://127.0.0.1:7860 >> /var/log/ciel/prune_chat_history.log 2>&1
```

The third line is the chat-history retention (30 days) the privacy page promises.

## 12. Point the app at the VPS

Before switching, save the current Streamlit Cloud secrets (the laptop's values) in the
password manager: the rollback needs them.

In Streamlit Cloud's secrets set:

| Secret | New value |
| --- | --- |
| `NGROK_URL` | `https://api.ciel-ai.web.id` |
| `NGROK_PASSWORD` | `NGROK_PASSWORD` from the VPS `.env` |
| `NGROK_USER` | `NGROK_USER` from the VPS `.env`, only if it changed |
| `LANGFLOW_API_KEY` | the VPS key from step 10 |
| `FLOW_ID` | the new ID from step 10 |
| `RESEARCH_FLOW_ID` | the new ID from step 10 |
| `WRITER_FLOW_ID` | the new ID from step 10 |
| `MEMORY_ADMIN_FLOW_ID` | the new ID from step 10 |

Reboot the app and ask Ciel a question; also try a photo question, a research question,
"Data saya" and one Pro feature.

### Alerts

The workflow `.github/workflows/backend-health.yml` probes the gateway and the DeepSeek
balance twice an hour and fails (GitHub emails the owner) when either is wrong. In the
repository's Settings, Secrets and variables, Actions:

1. Secrets: `BACKEND_URL` (`https://api.ciel-ai.web.id`), `BACKEND_USER` and
   `BACKEND_PASSWORD` (the VPS `NGROK_USER` and `NGROK_PASSWORD`), `FLOW_ID` and
   `MEMORY_ADMIN_FLOW_ID` (the new IDs from step 10), `DEEPSEEK_API_KEY`.
2. Then the variable `BACKEND_HEALTH_ENABLED` = `true`.
3. Then run the workflow once by hand (Actions, Backend health, Run workflow); it must be green.

GitHub disables scheduled workflows after 60 days without activity in the repository. If
the alerts stop, re-enable the workflow in the Actions tab.

## Rollback to the laptop

The laptop backend stays as it is until the VPS has run for 14 days without a problem.
Its watchdog stays disabled and Langflow Desktop stopped in the meantime. To go back:

1. Memories (long-term memory and personal datasets) written on the VPS after the cutover
   are not on the laptop; chat history is in Supabase and stays where it is. To keep them, copy
   them back first, while Langflow Desktop is still stopped (Chroma must not be open). On
   the VPS (this stops the VPS backend for a moment):

   ```bash
   cd /opt/ciel/deploy/vps
   docker compose stop langflow
   volume=$(docker volume ls -q --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME:-vps}" --filter label=com.docker.compose.volume=langflow_home)
   tar -C "$(docker volume inspect --format '{{ .Mountpoint }}' "$volume")/.ciel_ai" -czf /root/ciel_ai_from_vps.tgz long_term_memory user_datasets
   docker compose restart langflow ollama
   ```

   On the laptop (PowerShell), keep the laptop's old copies until the rollback is checked:

   ```powershell
   scp root@<vps-ip>:/root/ciel_ai_from_vps.tgz $HOME\
   Rename-Item $HOME\.ciel_ai\long_term_memory long_term_memory.before-rollback
   Rename-Item $HOME\.ciel_ai\user_datasets user_datasets.before-rollback
   tar -xzf $HOME\ciel_ai_from_vps.tgz -C $HOME\.ciel_ai
   ```

2. On the laptop, re-enable the watchdog and let it start Langflow Desktop and ngrok (from a
   normal PowerShell window in the repository, not as administrator):

   ```powershell
   Enable-ScheduledTask -TaskName 'Ciel backend watchdog'
   powershell -ExecutionPolicy Bypass -File tools\ciel_watchdog.ps1
   python tools\check_gateway.py
   ```

   `check_gateway.py` reads the laptop's `.env` and must print only PASS lines.
3. In Streamlit Cloud's secrets set the same list as in step 12 back to the laptop's values
   saved there: `NGROK_URL`, `NGROK_PASSWORD` (and `NGROK_USER` if it changed),
   `LANGFLOW_API_KEY`, `FLOW_ID`, `RESEARCH_FLOW_ID`, `WRITER_FLOW_ID` and
   `MEMORY_ADMIN_FLOW_ID`. Reboot the app and ask Ciel about a recent memory.
4. Alerts: set the repository variable `BACKEND_HEALTH_ENABLED` to `false`, or point the
   `BACKEND_*`, `FLOW_ID` and `MEMORY_ADMIN_FLOW_ID` secrets at the laptop's values.
5. Delete the memory archive on both machines (`rm /root/ciel_ai_from_vps.tgz` on the VPS,
   `Remove-Item $HOME\ciel_ai_from_vps.tgz` on the laptop): it holds personal data unencrypted.

The VPS can stay up while you do this; nothing on the laptop depends on it.

## Everyday commands

```bash
cd /opt/ciel/deploy/vps
docker compose ps
docker compose logs --tail 100 langflow
docker compose pull && docker compose up -d && docker compose restart ollama   # only after changing a pinned tag
```

Keep Ollama attached to Langflow. Root's crontab (`crontab -e`) gets this line, which
restarts the ollama container within a minute whenever Langflow cannot reach it on
`127.0.0.1:11434` (`/var/log/ciel` must exist: `mkdir -p /var/log/ciel`). It does nothing
while Langflow is not running (paused for the backup, stopped or restarting):

```
* * * * * cd /opt/ciel/deploy/vps && ./ollama_link_check.sh >> /var/log/ciel/ollama_link_check.log 2>&1
```

Make the script executable once: `chmod +x ollama_link_check.sh`.

Image tags are pinned in `docker-compose.yml`; change one on purpose, in Git, and rerun
`python -m unittest tests.test_vps_deploy`.
