# Ciel App off Streamlit Community Cloud Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the Streamlit app (`app.py`) on a rented VPS in Indonesia at `https://app.ciel-ai.web.id`, so selling Ciel Pro no longer breaks Streamlit Community Cloud's personal, non-commercial terms, with a rollback that is one Cloudflare change.

**Architecture:** A small VPS runs Docker Compose with two services: `caddy` (TLS, Let's Encrypt over HTTP-01) and `app` (the repository's `app.py` in a `python:3.14` image, dependencies from the hashed `requirements.txt`). The app keeps calling the backend exactly as today (laptop Langflow behind ngrok); moving the backend is the separate plan `2026-10-27-ciel-foundation-vps.md`, Task 8. A cron job pulls `main` and rebuilds, so "merge = deploy" stays true. Secrets live in one git-ignored TOML file on the VPS, copied verbatim from the Streamlit Cloud secrets editor.

**Tech Stack:** Docker Compose, Caddy 2.8.4, Python 3.14, Streamlit (version from `requirements.txt`), Cloudflare DNS, Google OAuth (`st.login`), Mayar, Supabase Edge Functions.

**Spec:** No separate spec. The spec is the vendor review in `docs/LEGAL.md` §3 (PR #80: Streamlit Community Cloud Terms of Use, Content Addendum item 4, personal and non-commercial use only; section 10, suspension without notice), Ciel's approval of a paid VPS on 2026-10-27, and the facts below, re-checked against `main` at `e65060a` on 2026-11-01.

### Facts re-checked against `main`

- `get_config()` (`app.py:1488`) reads `st.secrets` first, then environment variables. A `.streamlit/secrets.toml` inside the container is enough; no code change.
- Payments: `PAYMENT_PROVIDER` is `mayar` in production. The Mayar webhook goes to the Supabase Edge Function `mayar-notify` (`docs/PRO.md`), **not** to the app, so it does not change. The only app-side URL is the per-order return URL `redirectUrl = finish_url(APP_URL or st.context.url)` = `<APP_URL>/?page=pricing`, stored in each Mayar payment request when it is created. A Mayar payment page lives 24 hours (`MAYAR_EXPIRY_MINUTES`, PR #76).
- Google login: `[auth] redirect_uri` is one value, today `https://ciel-ai-assistant-hywsyrnfpyhxc5e9pjgaho.streamlit.app/oauth2callback`. The `st.login` cookie is per domain, so every user signs in once more on the new domain. Chat history, projects, profiles, consents and Pro status are in Supabase and are unaffected.
- Consent gate (`consents` table) and settings (`profiles` table) are keyed by the Google account, not by the host: no data moves.
- `app.ciel-ai.web.id` today is a proxied Cloudflare record plus a 302 Redirect Rule to the `streamlit.app` URL, keeping path and query (`2026-10-27-ciel-domain-and-search.md`). The landing page already links only to `app.ciel-ai.web.id`.
- `privacy.SUBPROCESSORS` names "Streamlit Community Cloud ... Amerika Serikat". PR #80 (open) rewrites `docs/LEGAL.md` §3 and bumps `terms.LEGAL_VERSION` to `2026-11-01.2`. Task 4 builds on PR #80 after it merges.
- `.github/workflows/keep-awake.yml` wakes the Cloud app every 4 hours via the repository variable `STREAMLIT_APP_URL`.
- The repository is public: the VPS clones it over HTTPS with no deploy key.
- The lockfile pins `streamlit==1.66.1`; Community Cloud has been running 1.65 (PR #79). The VPS runs exactly the lockfile, so the UI must be checked in the browser on the VPS before cutover.

**Approved by Ciel on 2026-11-01:** Option A (Biznet Gio NEO Lite MS 4.2), no `LEGAL_VERSION` bump, executed natively in one session with a whole-branch review at the end.

### Host choice and cost (decision for Ciel)

Prices from biznetgio.com/product/neo-lite, read 2026-11-01; promo length is not stated, so budget the normal price. Data center in Indonesia, unmetered bandwidth.

| Option | Plan | Price / month | Notes |
|---|---|---|---|
| **A (recommended)** | Biznet Gio NEO Lite **MS 4.2** (2 vCPU, 4 GB RAM, 60 GB SSD), app only | **Rp139.000** | Inside the 2026-10-27 budget (Rp100–250 ribu). Streamlit is one process; 4 GB plus 2 GB swap holds tens of concurrent sessions. Resize to MS 4.4 (Rp179.000) if CPU stays above 70%. The backend VPS stays a separate purchase later, so a Langflow/Ollama memory spike can never take the app down. |
| B | Biznet Gio NEO Lite **LL 16.8** (8 vCPU, 16 GB), app + backend on one host | Rp459.000 promo, Rp839.000 normal | One bill, but over budget now and couples the app to the riskier backend cutover. |
| C | Hetzner Singapore | from about €55–93 for 16 GB after the 2026 price rises | Not worth it at this size; data abroad. |

Option A keeps all app traffic and logs in Indonesia, which also shortens the privacy page's list of foreign recipients. Note for the backend plan: NEO Lite disks are 60 GB, below that plan's 80 GB requirement; revisit when executing it.

### Other decisions for Ciel

1. **Re-consent:** recommended **no** `LEGAL_VERSION` bump for the hosting change (PR #80 already asks everyone again; data moves to Indonesia, not to a new foreign party). Only `PRIVACY_UPDATED` changes. Bump if Ciel prefers to be strict.
2. **Real purchase after cutover:** recommended **no** paid test. Staging creates a Mayar payment request without paying and reads back its `redirectUrl`; settlement does not depend on the host.

## Global Constraints

- No Claude attribution lines in commits or PRs (Ciel's standing rule).
- UI copy changes (Task 4) wait for Ciel's own browser check and an explicit "commit".
- Production DNS, Streamlit Cloud secrets, VPS secrets, Google OAuth settings and Mayar settings change only after Ciel's explicit go-ahead **at that step**. The agent never types or reads a secret value; it may print key **names** and the two public values `APP_URL` and `redirect_uri`.
- `app` record in Cloudflare is **DNS only** (grey cloud), TTL 60 s until retirement (Task 6), then Auto.
- The Streamlit Cloud app stays deployed and untouched for **7 days** after cutover (rollback target, and return target for Mayar orders created before cutover), then is deleted.
- Mayar webhook registration is not touched.
- Image tags are pinned (`caddy:2.8.4`, `python:3.14.<patch>-slim-bookworm`, a tag at least two weeks old); dependencies install with `--require-hashes`.
- Every new offline test module is added to the CI list in `.github/workflows/ci.yml` (`tests/test_ci_coverage.py` enforces it).
- Tests run with `py -3.10 -m unittest discover -s tests` locally; CI runs Python 3.14.

## Review Focus

1. **Secrets baked into the image.** A developer's local `.streamlit/secrets.toml` must never be copied into the image: `.dockerignore` excludes it (test in Task 1).
2. **Long Riset Skripsi runs (up to 420 s) over the websocket.** No proxy timeout may cut them: Caddy has no `timeouts` block and the record is DNS-only, not Cloudflare-proxied (test in Task 1; Task 3 runs one research question on staging).
3. **Google login on the new host.** A redirect URI that is not registered in the OAuth client gives `redirect_uri_mismatch` and locks out every Pro buyer: both new URIs are registered before the secrets change (Task 2), and login is checked on staging and right after the switch (Tasks 3, 5).
4. **Mayar orders started on the old host.** Their return URL is the `streamlit.app` address, valid for 24 hours: the Cloud app stays up 7 days (Task 6), and settlement goes through `mayar-notify` regardless.
5. **A bad merge or failed build.** `update.sh` only restarts the app after a successful build and logs the result; a failed build leaves the running container untouched (test in Task 1).

---

### Task 1: App container stack and runbook (agent, no production change)

**Files:**
- Create: `deploy/app/Dockerfile`, `deploy/app/docker-compose.yml`, `deploy/app/Caddyfile`, `deploy/app/.env.example`, `deploy/app/update.sh`, `deploy/app/README.md`, `.dockerignore`
- Modify: `.gitignore`, `.github/workflows/ci.yml` (add `tests.test_app_deploy`; the `bash -n deploy/vps/*.sh` step becomes `bash -n deploy/vps/*.sh deploy/app/*.sh`)
- Test: `tests/test_app_deploy.py`

**Interfaces:**
- Produces: compose services `caddy` and `app`; volume `caddy_data`; compose build context `../..` with `dockerfile: deploy/app/Dockerfile`; app listens on `0.0.0.0:8501` inside the network only; secrets file `deploy/app/secrets.toml` (git-ignored) mounted read-only at `/app/.streamlit/secrets.toml`; `.env` name `CIEL_APP_HOSTS` (comma-separated host list, read by the Caddyfile as `{$CIEL_APP_HOSTS}`); `update.sh` run by root's cron every 2 minutes from `/opt/ciel/deploy/app`. Tasks 2, 5 and 6 use these names.

- [ ] **Step 1: Write the failing tests** (text checks, like `tests/test_vps_deploy.py`)

```python
def test_image_is_pinned_and_installs_from_the_lockfile(self):
    self.assertRegex(DOCKERFILE, r"FROM python:3\.14\.\d+-slim-bookworm")
    self.assertIn("pip install --no-cache-dir --require-hashes -r requirements.txt", DOCKERFILE)

def test_app_runs_as_non_root_on_8501(self):
    self.assertRegex(DOCKERFILE, r"\nUSER \w+")
    for flag in ("--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"):
        self.assertIn(flag, DOCKERFILE)

def test_local_secrets_never_enter_the_image(self):
    self.assertIn(".streamlit/secrets.toml", DOCKERIGNORE)
    self.assertIn("deploy/app/secrets.toml", DOCKERIGNORE)
    self.assertIn("deploy/app/secrets.toml", GITIGNORE)
    self.assertIn("deploy/app/.env", GITIGNORE)

def test_only_caddy_is_public(self):
    ports = re.findall(r"-\s*\"(\d+:\d+)\"", COMPOSE)
    self.assertEqual(sorted(ports), ["443:443", "80:80"])
    self.assertIn("./secrets.toml:/app/.streamlit/secrets.toml:ro", COMPOSE)
    self.assertEqual(COMPOSE.count("restart: unless-stopped"), 2)
    self.assertIn("max-size", COMPOSE)                          # docker logs cannot fill the disk

def test_app_has_a_healthcheck(self):
    self.assertIn("/_stcore/health", COMPOSE)

def test_caddy_serves_the_configured_hosts_without_timeouts(self):
    self.assertIn("{$CIEL_APP_HOSTS} {", CADDYFILE)
    self.assertIn("reverse_proxy app:8501", CADDYFILE)
    self.assertNotIn("timeouts", CADDYFILE)                     # Riset runs up to 420 s
    self.assertNotIn("trusted_proxies", CADDYFILE)
    self.assertIn("image: caddy:2.8.4", COMPOSE)

def test_update_restarts_only_after_a_successful_build(self):
    self.assertIn("set -euo pipefail", UPDATE)
    self.assertIn("flock", UPDATE)
    self.assertIn("git merge --ff-only origin/main", UPDATE)
    self.assertLess(UPDATE.index("docker compose build app"), UPDATE.index("docker compose up -d app"))

def test_env_example_has_names_only(self):
    self.assertIn("CIEL_APP_HOSTS=", ENV_EXAMPLE)
```

- [ ] **Step 2: Run to verify they fail**

Run: `py -3.10 -m unittest tests.test_app_deploy -v`
Expected: FAIL with `FileNotFoundError` for `deploy/app/Dockerfile`.

- [ ] **Step 3: Write the files**

Dockerfile: copy `requirements.txt` first and install (layer cache), then copy the repository; create user `ciel` (uid 10001); `CMD ["streamlit", "run", "app.py", ...flags]`. Pick the newest `python:3.14.N-slim-bookworm` tag on Docker Hub that is at least two weeks old. `.dockerignore`: `.git`, `.claude`, `.streamlit/secrets.toml`, `deploy/app/secrets.toml`, `deploy/app/.env`, `tests`, `docs`, `landing`, `flow`, `**/__pycache__`. Compose healthcheck uses `python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=5)"` (no curl in slim). Logging `json-file`, `max-size: 10m`, `max-file: "5"` on both services. `update.sh`: `flock -n /run/ciel-app-update.lock`, `git fetch origin main`, exit 0 when `HEAD` equals `origin/main`, else merge, build, `up -d app`, and print the new commit; any failure exits non-zero before `up`. The README is the runbook for Tasks 2, 5 and 6, in their order, plus "Everyday commands" (`docker compose logs --tail 200 app`, a manual `./update.sh`).

- [ ] **Step 4: Run to verify they pass**

Run: `py -3.10 -m unittest tests.test_app_deploy tests.test_ci_coverage tests.test_vps_deploy -v` and, in Git Bash, `bash -n deploy/app/update.sh`.
Expected: all OK, no output from `bash -n`. If Docker is available locally: `docker compose -f deploy/app/docker-compose.yml --env-file deploy/app/.env.example config -q` exits 0, and `docker build -f deploy/app/Dockerfile .` succeeds.

- [ ] **Step 5: Commit**

```bash
git add deploy/app .dockerignore .gitignore .github/workflows/ci.yml tests/test_app_deploy.py
git commit -m "Add a Docker stack that runs the Streamlit app on our own VPS"
```

---

### Task 2: Buy the VPS and bring up a staging host (Ciel + agent)

Each step names who acts. Stop at every **Go-ahead** until Ciel says yes in chat.

- [ ] **Step 1 (Ciel):** Buy the plan chosen above (Option A: NEO Lite MS 4.2, Ubuntu 24.04). Add the agent's SSH public key. Note the public IPv4.
- [ ] **Step 2 (agent over SSH):** Harden exactly as `deploy/vps/README.md` §2 (UTC clock, `ufw allow 22,80,443/tcp`, key-only SSH, unattended-upgrades), add a 2 GB swap file, install `docker.io docker-compose-v2 git`, clone the repository to `/opt/ciel`.
- [ ] **Step 3 (Go-ahead, Ciel in Cloudflare):** Create `next` → VPS IPv4, A record, **DNS only**, TTL 1 min. Nothing else in the zone changes.
- [ ] **Step 4 (Go-ahead, Ciel in Google Cloud Console):** In the OAuth client used by `[auth]`, add authorized redirect URIs `https://next.ciel-ai.web.id/oauth2callback` and `https://app.ciel-ai.web.id/oauth2callback`. Keep the `streamlit.app` one. If the consent screen asks for `ciel-ai.web.id` as an authorized domain, add it (the domain is already verified in Search Console); if Google asks for re-verification of the published app, stop and tell the agent.
- [ ] **Step 5 (Ciel on the VPS):** `cp .env.example .env` with `CIEL_APP_HOSTS=next.ciel-ai.web.id`. Create `secrets.toml` by pasting the whole Streamlit Cloud secrets editor content; then change only `APP_URL = "https://next.ciel-ai.web.id"` (a top-level key, above `[auth]`) and `[auth] redirect_uri = "https://next.ciel-ai.web.id/oauth2callback"`. `chown 10001 secrets.toml && chmod 600 secrets.toml`. Save the original Cloud secrets in the password manager.
- [ ] **Step 6 (agent):** `docker compose up -d --build`. Verify:
  - `docker compose ps`: both services running, `app` healthy.
  - Key names only: `docker compose exec app python -c "import tomllib; d=tomllib.load(open('/app/.streamlit/secrets.toml','rb')); print(sorted(k for k in d if k!='auth'), sorted(d.get('auth',{})), d.get('APP_URL'), d.get('auth',{}).get('redirect_uri'))"` lists the same names as `docs/PRO.md` and `.streamlit/secrets.toml.example` use, and the two `next` URLs.
  - `curl -sI https://next.ciel-ai.web.id/` returns 200 with a valid certificate.
- [ ] **Step 7 (agent):** Install root's cron line `*/2 * * * * cd /opt/ciel/deploy/app && ./update.sh >> /var/log/ciel/app_update.log 2>&1` (`mkdir -p /var/log/ciel` first).

### Task 3: Check staging in the browser (Ciel, agent watches logs)

- [ ] **Step 1 (Ciel, own browser, light and dark):** On `https://next.ciel-ai.web.id`: consent gate, Google login, a chat question, a photo question, a research question (Riset Skripsi, must finish without a timeout), "Data saya", Pengaturan, Pricing, Privasi and Ketentuan pages. Compare the look with the Cloud app (Streamlit 1.66.1 vs 1.65).
- [ ] **Step 2 (Ciel):** On Pricing, press buy and stop at the Mayar page without paying. **Agent:** give Ciel a one-liner that reads `MAYAR_API_KEY` from Ciel's local `.streamlit/secrets.toml`, calls `GET https://api.mayar.id/hl/v2/payments/<provider_ref>` (the path `mayar-notify` uses; `provider_ref` from the newest `pro_orders` row) and prints only `redirectUrl`. Expected: `https://next.ciel-ai.web.id/?page=pricing`. Ciel leaves the request to expire (24 h).
- [ ] **Step 3 (agent):** `docker compose logs app` shows no tracebacks; `docker stats --no-stream` shows the app under 1.5 GB.

Any failure: stop, report, fix on a branch; staging is not public, so nothing is at risk.

### Task 4: Privacy page, legal register and docs name the new host (agent; UI copy)

Start after PR #80 is merged into `main`.

**Files:**
- Modify: `privacy.py` (`SUBPROCESSORS`, `PRIVACY_UPDATED`), `docs/LEGAL.md` (§3 Streamlit row, new Biznet Gio row), `.streamlit/secrets.toml.example` (`APP_URL` example), `docs/PRO.md` (where secrets live), `README.md` (app host section), `docs/ARCHITECTURE.md`, `docs/BACKUP_AND_DISASTER_RECOVERY.md` (secrets now in the VPS file and the password manager), `tools/wake_streamlit.py` (docstring), `CHANGELOG.md`
- Test: `tests/test_privacy.py`, `tests/test_legal_docs.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_app_host_is_named_in_indonesia(self):        # tests/test_privacy.py
    text = " ".join(dict(privacy.privacy_sections(30, True, True))["Pihak ketiga yang menerima datamu"])
    self.assertIn("<strong>Biznet Gio</strong> (Indonesia)", text)
    self.assertNotIn("Streamlit Community Cloud", text)

def test_register_records_the_move(self):             # tests/test_legal_docs.py
    text = (ROOT / "docs" / "LEGAL.md").read_text(encoding="utf-8")
    self.assertIn("Biznet Gio", text)
    self.assertIn("2026-11-01-ciel-app-off-community-cloud.md", text)
```

- [ ] **Step 2: Run to verify they fail**

Run: `py -3.10 -m unittest tests.test_privacy tests.test_legal_docs -v`
Expected: FAIL on both new tests.

- [ ] **Step 3: Implement**

`SUBPROCESSORS` row `("Streamlit Community Cloud", "menjalankan tampilan aplikasi", "Amerika Serikat")` becomes `("Biznet Gio", "server yang menjalankan aplikasi Ciel", "Indonesia")`. `PRIVACY_UPDATED` = the cutover date. `LEGAL_VERSION` changes only if Ciel chose the bump above. LEGAL §3: the Streamlit row's action becomes "[ ] Pindah ke VPS Biznet Gio (rencana `docs/superpowers/plans/2026-11-01-ciel-app-off-community-cloud.md`); app Community Cloud dihapus 7 hari setelah pindah"; add a Biznet Gio row "[ ] Baca dan simpan tautan ketentuan layanan dan kebijakan privasi Biznet Gio; data center di Indonesia".

- [ ] **Step 4: Run the full offline suite**

Run: `py -3.10 -m unittest discover -s tests`
Expected: `OK` (live tests skip without a backend).

- [ ] **Step 5 (Ciel):** Check the Privasi page on staging after `./update.sh` picks up the branch (or locally), then on Ciel's explicit "commit":

```bash
git add privacy.py docs .streamlit/secrets.toml.example README.md tools/wake_streamlit.py CHANGELOG.md tests/test_privacy.py tests/test_legal_docs.py
git commit -m "Name the Indonesian VPS that now runs the app on the privacy page"
```

Merge it on cutover day, right before Task 5 Step 3.

### Task 5: Cutover (Ciel + agent, about 20 minutes, low-traffic hour)

- [ ] **Step 1 (agent):** Ciel reads out (screenshot) the current `app` DNS record and the Redirect Rule in Cloudflare; the agent writes them into the notes as the rollback values.
- [ ] **Step 2 (Go-ahead, Ciel on the VPS):** In `secrets.toml` set `APP_URL = "https://app.ciel-ai.web.id"` and `redirect_uri = "https://app.ciel-ai.web.id/oauth2callback"`; in `.env` set `CIEL_APP_HOSTS=app.ciel-ai.web.id, next.ciel-ai.web.id`. Agent: `docker compose up -d && docker compose restart app` (recreates `caddy` with the new hosts; the restart makes the app read the edited secrets file, which Compose does not notice on its own).
- [ ] **Step 3 (Go-ahead, Ciel in Cloudflare):** Merge Task 4. Disable (do not delete) the `app` Redirect Rule; change the `app` record to A → VPS IPv4, **DNS only**, TTL 1 min.
- [ ] **Step 4 (agent):** `docker compose restart caddy` so the certificate is requested at once; wait for `certificate obtained successfully` for `app.ciel-ai.web.id` in `docker compose logs caddy`. Then `curl -sI https://app.ciel-ai.web.id/` is 200 from the VPS (no `location:` to `streamlit.app`), and `dig +short app.ciel-ai.web.id @1.1.1.1` prints the VPS IP.
- [ ] **Step 5 (Ciel, own browser):** Sign in with Google on `app.ciel-ai.web.id`, ask one question, open Pricing (Pro status shows correctly for Ciel's own account), Privasi shows Biznet Gio.
- [ ] **Step 6 (agent):** Watch `docker compose logs -f app` for 15 minutes for login or payment errors; for the first order created after the switch, Ciel runs the Task 3 one-liner; `redirectUrl` must be on `app.ciel-ai.web.id`.

### Task 6: Rollback window, then retire Community Cloud

**Rollback (any time in the 7 days, Ciel's go-ahead):** In Cloudflare set the `app` record back to the values saved in Task 5 Step 1 (proxied) and re-enable the Redirect Rule. Traffic returns to the untouched Cloud app within a minute or two. Orders created on the VPS return to `app.ciel-ai.web.id/?page=pricing`, which the restored rule forwards with its query to the Cloud app, and settlement still runs through `mayar-notify`. Users sign in once more. The VPS can stay up meanwhile.

- [ ] **Step 1 (during the window):** Leave `STREAMLIT_APP_URL` on the `streamlit.app` URL so the rollback target stays awake.
- [ ] **Step 2 (Go-ahead, day 7, Ciel):** Delete the app on share.streamlit.io; in the OAuth client remove the `streamlit.app` redirect URI; delete the Redirect Rule; set the `app` record TTL to Auto. Set `STREAMLIT_APP_URL` to `https://app.ciel-ai.web.id` (the 4-hourly run becomes an uptime check) or delete the variable. Decide whether `next` stays as a staging host (keep its DNS record and `CIEL_APP_HOSTS` entry) or goes.
- [ ] **Step 3 (agent):** In `docs/LEGAL.md` §3 tick the Streamlit row with the deletion date; `CHANGELOG.md` entry; commit and open a PR.
