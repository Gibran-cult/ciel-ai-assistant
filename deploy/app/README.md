# Ciel app on its own VPS

Runbook for running the Streamlit app (`app.py`) on a VPS instead of Streamlit
Community Cloud, whose terms allow personal, non-commercial use only
(`docs/LEGAL.md` §3). The plan behind it, with the decisions and who does what, is
`docs/superpowers/plans/2026-11-01-ciel-app-off-community-cloud.md`.

```
internet -> caddy :443 (TLS) -> app :8501 (streamlit)
```

Only `caddy` publishes ports (80, 443). The backend is not on this VPS: the app reaches
Langflow at `NGROK_URL` from its secrets, as before. Moving the backend is
`deploy/vps/README.md`.

All commands run as root on the VPS, in `/opt/ciel/deploy/app` unless a step says
otherwise. Steps marked **Go-ahead** change something users or payments depend on: do
them only after Ciel says yes for that step.

## 1. VPS

Biznet Gio NEO Lite MS 4.2 (2 vCPU, 4 GB RAM, 60 GB SSD, data center in Indonesia),
Ubuntu 24.04 LTS, a public IPv4 address, the operator's SSH public key.

## 2. Harden the host

The same as `deploy/vps/README.md` §2: UTC clock, `ufw allow 22,80,443/tcp`, key-only
SSH, unattended-upgrades. Then a swap file, so a memory spike slows the app instead of
killing it:

```bash
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

## 3. Install Docker and get the code

```bash
apt install -y docker.io docker-compose-v2 git
systemctl enable --now docker
git clone https://github.com/Gibran-cult/ciel-ai-assistant.git /opt/ciel
cd /opt/ciel/deploy/app
```

## 4. Staging DNS (Go-ahead)

In Cloudflare, add `next` → the VPS IPv4: an A record, **DNS only** (grey cloud), TTL
1 min. Caddy needs it to get its certificate. Nothing else in the zone changes.

## 5. Secrets (Ciel)

Google Cloud Console (**Go-ahead**), in the OAuth client the app's `[auth]` block uses:
add the authorized redirect URIs `https://next.ciel-ai.web.id/oauth2callback` and
`https://app.ciel-ai.web.id/oauth2callback`. Keep the `streamlit.app` one until the Cloud
app is deleted (step 10).

On the VPS:

```bash
cp .env.example .env          # CIEL_APP_HOSTS=next.ciel-ai.web.id
nano .env
nano secrets.toml
chown 10001 secrets.toml && chmod 600 secrets.toml
```

Paste the whole content of the Streamlit Cloud secrets editor into `secrets.toml`, then
change only these two values:

```toml
APP_URL = "https://next.ciel-ai.web.id"                      # top-level, above [auth]

[auth]
redirect_uri = "https://next.ciel-ai.web.id/oauth2callback"
```

Save the original Cloud secrets in the password manager first. `PAYMENT_PROVIDER`,
the Mayar keys and everything else stay as they are. The Mayar webhook goes to the
Supabase function `mayar-notify`, not to the app, so it does not change; `APP_URL` is
only the page buyers return to after paying (`<APP_URL>/?page=pricing`).

`secrets.toml` and `.env` are git-ignored, and `.dockerignore` keeps both out of the
image. `chown 10001` lets the app's user (uid 10001 in the image) read the file.

## 6. Start and check

```bash
docker compose up -d --build
docker compose ps             # caddy running, app running (healthy)
```

Key names only, plus the two public URLs (never print the file itself):

```bash
docker compose exec app python -c "import tomllib; d=tomllib.load(open('/app/.streamlit/secrets.toml','rb')); print(sorted(k for k in d if k!='auth'), sorted(d.get('auth',{})), d.get('APP_URL'), d.get('auth',{}).get('redirect_uri'))"
curl -sI https://next.ciel-ai.web.id/ | head -1   # HTTP/2 200
```

The certificate can take a minute on the first start (`docker compose logs caddy`).

Then Ciel checks staging in the browser, light and dark: consent gate, Google login,
chat, a photo question, a research question (must finish, up to 7 minutes), Data saya,
Pengaturan, Pricing, Privasi, Ketentuan. On Pricing, start a purchase and stop at the
Mayar page without paying; the payment request's `redirectUrl` must be
`https://next.ciel-ai.web.id/?page=pricing`.

## 7. Deploy on every merge

Root's crontab (`crontab -e`, after `mkdir -p /var/log/ciel`):

```
*/2 * * * * cd /opt/ciel/deploy/app && ./update.sh >> /var/log/ciel/app_update.log 2>&1
```

`update.sh` fast-forwards to `origin/main`, builds the image, and restarts the app only
when the build succeeded. A failed build leaves the running app as it was and is retried
on the next run; `tail /var/log/ciel/app_update.log` shows why. A restart drops open
sessions for a few seconds; the browser reconnects on its own.

## 8. Switch `app.ciel-ai.web.id` (Go-ahead, about 20 minutes)

Pick a quiet hour. Before anything, save the current `app` record and the `app` Redirect
Rule in Cloudflare (screenshot): rollback restores exactly these.

1. Merge the privacy change that names the VPS host (plan, Task 4).
2. In `secrets.toml` set `APP_URL = "https://app.ciel-ai.web.id"` and
   `redirect_uri = "https://app.ciel-ai.web.id/oauth2callback"`; in `.env` set
   `CIEL_APP_HOSTS=app.ciel-ai.web.id, next.ciel-ai.web.id`. Then
   `docker compose up -d && docker compose restart app` (the first recreates Caddy with the
   new hosts; the second makes the app read the edited `secrets.toml`).
3. Cloudflare: **disable** (do not delete) the `app` Redirect Rule; change the `app`
   record to an A record → the VPS IPv4, **DNS only**, TTL 1 min.
4. `docker compose restart caddy`, then wait for `certificate obtained successfully` for
   `app.ciel-ai.web.id` in `docker compose logs caddy`.
5. Check: `dig +short app.ciel-ai.web.id @1.1.1.1` prints the VPS IP;
   `curl -sI https://app.ciel-ai.web.id/` is 200 with no `location:` header. Ciel signs
   in with Google, asks one question, opens Pricing and Privasi.

Everyone signs in once more: the login cookie belongs to the old domain.

## 9. Rollback

Within 7 days of the switch the Streamlit Cloud app is still deployed and untouched. In
Cloudflare, set the `app` record back to the values saved in step 8 and re-enable the
Redirect Rule. Users are back on the Cloud app within a minute or two. Orders started on
the VPS return to `app.ciel-ai.web.id/?page=pricing`, which the rule forwards with its
query to the Cloud app; payments settle through `mayar-notify` either way. The VPS can
stay up.

Keep the repository variable `STREAMLIT_APP_URL` on the `streamlit.app` URL during these
7 days, so the keep-awake workflow keeps the rollback target awake.

## 10. Retire Community Cloud (Go-ahead, day 7)

- Delete the app on share.streamlit.io.
- Remove the `streamlit.app` redirect URI from the OAuth client.
- Delete the `app` Redirect Rule; set the `app` record's TTL to Auto.
- Set `STREAMLIT_APP_URL` to `https://app.ciel-ai.web.id` (the workflow becomes a
  4-hourly uptime check) or delete it.
- Decide whether `next` stays as a staging host. If not, remove it from
  `CIEL_APP_HOSTS`, `docker compose up -d`, and delete its DNS record.

## Everyday commands

```bash
cd /opt/ciel/deploy/app
docker compose ps
docker compose logs --tail 200 app
./update.sh                          # deploy main now instead of waiting for cron
docker stats --no-stream             # the app should stay well under 4 GB
```

After editing `.env`: `docker compose up -d` (it recreates what changed). After editing
`secrets.toml`: `docker compose restart app`; Compose does not notice a changed file
behind a bind mount. Image tags are pinned in `Dockerfile` and `docker-compose.yml`; change one on
purpose, in Git, and rerun `python -m unittest tests.test_app_deploy`.
