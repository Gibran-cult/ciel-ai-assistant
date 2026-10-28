# Ciel Foundation: VPS Backend, Backups, Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Ciel's backend off Ciel's laptop to a VPS, with automatic off-site backups, outage and balance alerts, and quotas that survive app restarts, so Ciel can serve hundreds of users a day for years.

**Architecture:** One Ubuntu VPS runs Docker Compose: Caddy (TLS for `api.ciel-ai.web.id`) → nginx (Basic Auth, exact path allowlist, per-IP rate limit; generated from the same rules as today's ngrok policy) → Langflow 1.12.4 (one worker, Postgres database) with Ollama in Langflow's network namespace so the components' hard-coded `127.0.0.1:11434` keeps working. Nightly restic backups go to Cloudflare R2 and ping Healthchecks.io; GitHub Actions checks the gateway and the DeepSeek balance. The Streamlit app keeps its config names (`NGROK_URL`, `NGROK_USER`, `NGROK_PASSWORD`); only their values change.

**Tech Stack:** Python 3.14 (app, tools, `unittest`), Docker Compose, Caddy, nginx, Langflow 1.12.4, Postgres, Ollama, restic + Cloudflare R2, Supabase (Postgres function over PostgREST), GitHub Actions.

**Spec:** No separate spec. The spec is the foundation audit of 2026-10-27 plus Ciel's decisions, recorded here:

- Software foundation is strong (630 offline tests pass, hashed lockfile, pip-audit, Dependabot, flow contract tests, security audit done). It is not changed except where a task below needs it.
- Weak: (1) the whole backend is one 8 GB laptop behind ngrok's free plan; (2) memories, personal datasets, the Langflow database and Supabase have no automatic off-site backup; (3) sub-flows are not in Git; (4) a backend outage or an empty DeepSeek balance raises no alert; (5) rate limits and Pro quotas live in the Streamlit process and reset on every reboot; (6) CI runs a hand-typed test list, so a new test file can silently never run, and flow v1.12.0's JSON is not validated.
- Ciel's decisions: pay for a VPS (about Rp 100–250 ribu/bulan); target hundreds (100–1000) of active users per day.
- Out of scope: splitting `app.py` (5,066 lines; well covered by tests, refactor when touching areas), streaming answers (unblocked by this plan, separate feature), renaming `NGROK_*` config keys, moving the frontend off Streamlit Community Cloud.

## Global Constraints

- Commit messages and PR bodies have **no** Claude attribution lines (`Co-Authored-By`, "Generated with Claude Code"): Ciel's standing rule.
- UI copy changes (the privacy text in Task 5) wait for Ciel's own browser check and an explicit "commit" before committing.
- Langflow stays on **1.12.4**; image tag `langflowai/langflow:1.12.4`.
- `LANGFLOW_WORKERS=1`. Chroma's `PersistentClient` is not safe across processes; more workers would corrupt long-term memory.
- Langflow's port is bound to `127.0.0.1` only; the Langflow UI is reached by SSH tunnel, never through the gateway.
- Every new offline test module is added to the CI list in `.github/workflows/ci.yml` (Task 1 enforces this).
- Backup retention is exactly `--keep-daily 7 --keep-weekly 4` (deleted user data leaves backups within about 5 weeks). The privacy page states this **before** the first backup runs.
- `RESTIC_PASSWORD` is also saved by Ciel in a password manager outside the VPS. Without it the backups cannot be read.
- Secret values (API keys, passwords, DB URLs) are entered by Ciel, never typed by the agent and never committed. `deploy/vps/.env` is git-ignored; `deploy/vps/.env.example` holds names only.
- The Ollama embedding model on the VPS must have the same model ID (`ollama list`) as on the laptop. A different `nomic-embed-text-v2-moe` build silently breaks memory search on stored vectors.
- Code comments and user-facing strings in the app are in Indonesian, tools' docstrings in English, matching the surrounding files.

## Review Focus

1. **Long Pro requests through the new gateway.** Riset Skripsi waits up to `RESEARCH_TIMEOUT = 420` s; any proxy timeout below that turns a slow but valid run into an error. Expect nginx `proxy_read_timeout` ≥ 600 s (test in Task 3), and no Cloudflare proxy in front (the `api` record is DNS-only, because Cloudflare's proxy cuts responses at 100 s).
2. **All users share one client IP at the gateway.** Every request comes from Streamlit Cloud's egress IP, so a per-IP limit is really a global limit. The ngrok policy's 20 runs/min would throttle a busy hour. Expect the per-IP run limit to be configurable with default 60/min (test in Task 3); per-user limits stay in the app.
3. **Supabase down or slow must not stop chat.** The persistent rate limit adds a network call per message. Expect a 3 s timeout and fallback to the in-process limiter, never an error shown to the user and never "unlimited" (test in Task 2).
4. **A backup nobody has restored is not a backup.** Expect a monthly automatic restore check that opens the restored Chroma DB and both dumps and pings its own Healthchecks.io check (Task 5), and a manual restore check during cutover (Task 8).
5. **Old memories after migration.** Copied Chroma files with a different chromadb version, or a different embedding model, give empty or wrong recall without any error. Expect the cutover to compare per-collection counts and run one recall query for a known memory before switching the app (Task 8).

---

### Task 1: CI runs every offline test and validates every flow JSON

**Files:**
- Create: `tests/test_ci_coverage.py`
- Modify: `.github/workflows/ci.yml` (the "Validate flow JSON" step and the unittest list)

**Interfaces:**
- Consumes: nothing.
- Produces: `LIVE_TESTS` (module-level `frozenset[str]` in `tests/test_ci_coverage.py`): the test modules that need a live backend and are deliberately not in CI: `test_ciel_master`, `test_judge_calibration`, `test_llm_judge`, `test_memory_context_optimization`, `test_memory_engine`, `test_memory_multi_query`, `test_response_quality`.

- [ ] **Step 1: Write the failing tests**

```python
class CiCoverageTest(unittest.TestCase):
    def test_every_offline_test_module_runs_in_ci(self):
        on_disk = {p.stem for p in TESTS_DIR.glob("test_*.py")}
        in_ci = set(re.findall(r"tests\.(test_[a-z0-9_]+)", CI_TEXT))
        self.assertEqual(on_disk - LIVE_TESTS - in_ci, set())

    def test_live_tests_are_not_in_ci(self):
        in_ci = set(re.findall(r"tests\.(test_[a-z0-9_]+)", CI_TEXT))
        self.assertEqual(LIVE_TESTS & in_ci, set())

    def test_every_flow_json_is_validated(self):
        # The step loops over git-tracked flow JSON instead of naming files.
        self.assertIn("git ls-files 'flow/*.json' 'flow/**/*.json'", CI_TEXT)
        self.assertIn("python -m json.tool", CI_TEXT)
```

`TESTS_DIR`, `CI_TEXT` are module constants (`Path(__file__).parent`, the text of `.github/workflows/ci.yml`).

- [ ] **Step 2: Run to verify it fails**

Run: `python -m unittest tests.test_ci_coverage -v`
Expected: FAIL on `test_every_flow_json_is_validated` (the step names files) and on `test_every_offline_test_module_runs_in_ci` with `{'test_ci_coverage'}`.

- [ ] **Step 3: Change `.github/workflows/ci.yml`**

Replace the body of "Validate flow JSON" with a loop: `git ls-files 'flow/*.json' 'flow/**/*.json' | while read -r f; do python -m json.tool "$f" > /dev/null || exit 1; done`. Add `tests.test_ci_coverage` to the unittest list.

- [ ] **Step 4: Run to verify it passes**

Run: `python -m unittest tests.test_ci_coverage -v`
Expected: 3 tests OK. Also run the loop from Step 3 in Git Bash; expected: no output, exit 0.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ci_coverage.py .github/workflows/ci.yml
git commit -m "Make CI fail when a test file or flow JSON is left out"
```

---

### Task 2: Rate limits and Pro quotas survive app restarts

**Files:**
- Modify: `docs/chat_store.sql` (append table + function)
- Modify: `chat_store.py` (new method on `ChatStore`)
- Modify: `app.py:2016-2042` (`check_rate_limit`) and add `shared_rate_limit_full` next to it
- Test: `tests/test_chat_store.py`, `tests/test_rate_limit.py`

**Interfaces:**
- Consumes: `rate_limit_full(store, limits, now) -> str | None` and `rate_limit_state()` (existing, `app.py`), `CHAT_STORE` (existing, `ChatStore | None`).
- Produces:
  - SQL: table `public.rate_limit_hits(key text not null, at double precision not null)` with index on `(key, at)` and on `(at)`, RLS on, no policy. Function `public.ciel_rate_limit_hit(p_limits jsonb, p_now double precision) returns text`, `security definer`, `set search_path = public`. `p_limits` is a JSON **array** of `[key, limit, window_seconds]` (an array, because jsonb objects do not keep key order and the first full key decides the message). Same semantics as `rate_limit_full`: take `pg_advisory_xact_lock(727274)`, delete rows with `at < p_now - 86400`, count hits per key with `at > p_now - window`; if any count ≥ limit return the first such key and insert nothing; else insert one row per key and return null.
  - `ChatStore.rate_limit_hit(self, limits: dict[str, tuple[int, int]], now: float) -> tuple[bool, str | None]`: `(True, None)` allowed, `(True, key)` blocked by `key`, `(False, None)` Supabase unreachable or bad response. POST `f"{self.base}/rpc/ciel_rate_limit_hit"`, `timeout=RATE_LIMIT_TIMEOUT` (module constant `= 3`), logs `chat_store_error action=rate_limit_hit ...` on failure, never raises.
  - `shared_rate_limit_full(limits: dict, now: float) -> str | None` in `app.py`: uses `CHAT_STORE.rate_limit_hit` when `CHAT_STORE` is set and reachable; otherwise the existing in-process `rate_limit_full` under `rate_limit_state()["lock"]`. `check_rate_limit` calls it instead of the in-process path.

- [ ] **Step 1: Write the failing tests**

In `tests/test_chat_store.py` (mock `requests.post` like the existing tests):

```python
def test_rate_limit_hit_sends_limits_in_order(self):
    # post returns 200 with JSON null
    ok, full = store.rate_limit_hit({"user:a:hour": (60, 3600), "all:total:day": (1500, 86400)}, 1000.0)
    self.assertEqual((ok, full), (True, None))
    body = post.call_args.kwargs["json"]
    self.assertEqual(body, {"p_limits": [["user:a:hour", 60, 3600], ["all:total:day", 1500, 86400]], "p_now": 1000.0})
    self.assertTrue(post.call_args.args[0].endswith("/rest/v1/rpc/ciel_rate_limit_hit"))
    self.assertEqual(post.call_args.kwargs["timeout"], 3)

def test_rate_limit_hit_returns_the_full_key(self):
    # post returns 200 with JSON "user:a:hour"; LIMITS = {"user:a:hour": (60, 3600)}
    self.assertEqual(store.rate_limit_hit(LIMITS, 1.0), (True, "user:a:hour"))

def test_rate_limit_hit_reports_unreachable(self):
    # post raises requests.exceptions.Timeout; then a 500; then a 200 with JSON 42
    self.assertEqual(store.rate_limit_hit(LIMITS, 1.0), (False, None))  # all three cases
```

In `tests/test_rate_limit.py`, load `shared_rate_limit_full` with `load_app_function` and set its globals (`CHAT_STORE`, `rate_limit_full`, `rate_limit_state`):

```python
def test_shared_store_decides_when_reachable(self):
    store = Mock(); store.rate_limit_hit.return_value = (True, "user:a:day")
    self.assertEqual(shared(limits, 5.0), "user:a:day")   # in-process store untouched

def test_falls_back_to_process_limits_when_store_is_down(self):
    store.rate_limit_hit.return_value = (False, None)
    # limit 1: first call None, second call returns the key — the fallback still limits
    self.assertIsNone(shared({"k:hour": (1, 3600)}, 5.0))
    self.assertEqual(shared({"k:hour": (1, 3600)}, 6.0), "k:hour")

def test_without_store_uses_process_limits(self):
    # CHAT_STORE = None: same two assertions as above
```

Add one SQL-text test in `tests/test_chat_store.py`: `docs/chat_store.sql` contains `create table if not exists public.rate_limit_hits`, `alter table public.rate_limit_hits enable row level security`, `function public.ciel_rate_limit_hit(`, `pg_advisory_xact_lock`, and `security definer`.

- [ ] **Step 2: Run to verify they fail**

Run: `python -m unittest tests.test_chat_store tests.test_rate_limit -v`
Expected: FAIL with `AttributeError: ... 'rate_limit_hit'` and `StopIteration` (no `shared_rate_limit_full` in `app.py`).

- [ ] **Step 3: Implement the SQL, `ChatStore.rate_limit_hit`, and `shared_rate_limit_full`; switch `check_rate_limit` to it**

A response body that is neither `null` nor a string counts as unreachable.

- [ ] **Step 4: Run to verify they pass**

Run: `python -m unittest tests.test_chat_store tests.test_rate_limit tests.test_ciel_pro -v`
Expected: all OK.

- [ ] **Step 5: Run the full offline suite**

Run (Git Bash): `python -m unittest $(grep -oE 'tests\.test_[a-z0-9_]+' .github/workflows/ci.yml | tr '\n' ' ')`
Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add docs/chat_store.sql chat_store.py app.py tests/test_chat_store.py tests/test_rate_limit.py
git commit -m "Keep rate limits and Pro quotas in Supabase so a reboot does not reset them"
```

- [ ] **Step 7: Ciel runs the new SQL in Supabase** (SQL Editor → paste the appended block → Run), before this commit reaches production. Until then the app falls back to in-process limits, so order does not break anything.

---

### Task 3: nginx gateway config generated from the same rules as the ngrok policy

**Files:**
- Create: `tools/render_nginx_gateway.py`
- Test: `tests/test_nginx_gateway.py`

**Interfaces:**
- Consumes: `allowed_requests`, `check_settings`, `load_settings`, `id_forms`, `PolicyError`, `ROOT` from `tools/render_ngrok_policy.py` (import them; do not copy).
- Produces:
  - `build_nginx_config(user, password, flow_id, admin_flow_id, research_flow_id=None, writer_flow_id=None, run_per_minute=60, all_per_minute=300) -> str`: an nginx `http`-context include (one `server` listening on `8080`). Requirements: `limit_req_zone $http_x_forwarded_for` zones `ciel_all` (`all_per_minute` r/m) and `ciel_api` (`run_per_minute` r/m); server-level `auth_basic` with `auth_basic_user_file /etc/nginx/ciel.htpasswd`, `limit_req zone=ciel_all burst=60 nodelay`, `client_max_body_size 30m`, `proxy_read_timeout 600s`, `proxy_send_timeout 600s`; one `location = <path>` per distinct path in `allowed_requests`, with `limit_except <its methods> { deny all; }` and `proxy_pass http://langflow:7860$uri$is_args$args;` (passing the normalized `$uri`, so Langflow receives exactly the matched path); `/api/v1/run/` and `/api/v1/files/upload/` locations add `limit_req zone=ciel_api burst=20 nodelay`; `location / { return 404; }`.
  - `htpasswd_line(user, password, salt: bytes) -> str`: `f"{user}:{{SSHA}}" + base64(sha1(password + salt) + salt)` (nginx's `{SSHA}` scheme, no extra dependency).
  - CLI `main(argv=None) -> int`: reads `NGROK_USER`, `NGROK_PASSWORD`, flow IDs and optional `GATEWAY_RUN_PER_MINUTE`, `GATEWAY_ALL_PER_MINUTE` via `load_settings`; writes `--conf-out` (default `deploy/vps/nginx/ciel.conf`) and `--htpasswd-out` (default `deploy/vps/nginx/ciel.htpasswd`, salt from `os.urandom(8)`); prints nothing secret; returns 1 on `PolicyError` and writes nothing.

- [ ] **Step 1: Write the failing tests**

```python
def test_every_allowed_path_has_an_exact_location(self):
    conf = build(FLOW, ADMIN)
    for _, path in allowed_requests(FLOW, ADMIN):
        self.assertIn(f"location = {path} {{", conf)
    self.assertIn("location / {\n        return 404;", conf)

def test_sessions_path_allows_get_and_delete_only(self):
    self.assertRegex(build(FLOW, ADMIN), r"location = /api/v1/monitor/messages/sessions \{\s+limit_except GET DELETE")

def test_langflow_receives_the_normalized_path(self):
    conf = build(FLOW, ADMIN)
    self.assertNotIn("$request_uri", conf)
    self.assertEqual(conf.count("proxy_pass http://langflow:7860$uri$is_args$args;"), len({p for _, p in allowed_requests(FLOW, ADMIN)}))

def test_long_research_requests_are_not_cut(self):
    self.assertIn("proxy_read_timeout 600s;", build(FLOW, ADMIN))  # > RESEARCH_TIMEOUT 420

def test_run_limit_defaults_to_60_per_minute_and_is_configurable(self):
    self.assertIn("zone=ciel_api:10m rate=60r/m", build(FLOW, ADMIN))
    self.assertIn("zone=ciel_api:10m rate=90r/m", build(FLOW, ADMIN, run_per_minute=90))

def test_optional_flows_only_when_configured(self):
    self.assertNotIn(RESEARCH, build(FLOW, ADMIN))
    self.assertIn(f"location = /api/v1/run/{RESEARCH} {{", build(FLOW, ADMIN, research_flow_id=RESEARCH))

def test_htpasswd_is_nginx_ssha(self):
    line = htpasswd_line("ciel", "p" * 32, b"12345678")
    user, hashed = line.split(":", 1)
    raw = base64.b64decode(hashed.removeprefix("{SSHA}"))
    self.assertEqual(raw, hashlib.sha1(b"p" * 32 + b"12345678").digest() + b"12345678")

def test_weak_settings_write_nothing(self):
    # main() with NGROK_PASSWORD="short": returns 1, neither output file exists, stdout has no password
```

`build` is `build_nginx_config` with fixed valid credentials; `FLOW`, `ADMIN`, `RESEARCH` are UUID constants.

- [ ] **Step 2: Run to verify they fail**

Run: `python -m unittest tests.test_nginx_gateway -v`
Expected: FAIL with `ModuleNotFoundError: render_nginx_gateway`.

- [ ] **Step 3: Implement `tools/render_nginx_gateway.py`**

Group `allowed_requests` by path to build each `limit_except` method list. Module docstring explains, like `render_ngrok_policy.py`, that the rules are the same and why `$uri` is passed.

- [ ] **Step 4: Run to verify they pass**

Run: `python -m unittest tests.test_nginx_gateway tests.test_gateway_policy -v`
Expected: all OK.

- [ ] **Step 5: Add `tests.test_nginx_gateway` to the CI list, add `deploy/vps/nginx/ciel.htpasswd` and `deploy/vps/nginx/ciel.conf` to `.gitignore`, commit**

```bash
git add tools/render_nginx_gateway.py tests/test_nginx_gateway.py .github/workflows/ci.yml .gitignore
git commit -m "Generate the VPS nginx gateway from the same allowlist as the ngrok policy"
```

---

### Task 4: VPS stack (Docker Compose) and runbook

**Files:**
- Create: `deploy/vps/docker-compose.yml`, `deploy/vps/Caddyfile`, `deploy/vps/.env.example`, `deploy/vps/README.md`
- Modify: `.gitignore` (`deploy/vps/.env`)
- Test: `tests/test_vps_deploy.py`

**Interfaces:**
- Consumes: `deploy/vps/nginx/ciel.conf` and `ciel.htpasswd` written by Task 3's CLI.
- Produces: compose service names `caddy`, `nginx`, `langflow`, `postgres`, `ollama`; volumes `langflow_home` (mounted at Langflow's home, `/app/data`), `postgres_data`, `ollama_models`, `caddy_data`; env names in `.env.example`: `LANGFLOW_SUPERUSER`, `LANGFLOW_SUPERUSER_PASSWORD`, `LANGFLOW_SECRET_KEY`, `POSTGRES_PASSWORD`, `SUPABASE_DB_URL`, `RESTIC_REPOSITORY`, `RESTIC_PASSWORD`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `HEALTHCHECKS_BACKUP_URL`, `HEALTHCHECKS_RESTORE_URL`, `LANGFLOW_API_KEY`, `NGROK_USER`, `NGROK_PASSWORD`, `FLOW_ID`, `MEMORY_ADMIN_FLOW_ID`, `RESEARCH_FLOW_ID`, `WRITER_FLOW_ID`, `GATEWAY_RUN_PER_MINUTE`. Tasks 5 and 8 use these names.

Pinned values: `langflowai/langflow:1.12.4`; `postgres:16.4`; `nginx:1.27.3-alpine`; `caddy:2.8.4`; `ollama/ollama:<the laptop's version>` (Ciel's laptop: `ollama --version`, filled in Step 3). Langflow env: `LANGFLOW_DATABASE_URL=postgresql://langflow:${POSTGRES_PASSWORD}@postgres:5432/langflow`, `LANGFLOW_WORKERS=1`, `LANGFLOW_AUTO_LOGIN=false`, `LANGFLOW_VERTEX_BUILDS_STORAGE_ENABLED=false`, `LANGFLOW_HOST=0.0.0.0`, `LANGFLOW_PORT=7860`. `ollama` uses `network_mode: "service:langflow"`. Only `caddy` publishes public ports (`80`, `443`); `langflow` publishes `127.0.0.1:7860:7860`. Every service has `restart: unless-stopped`. `nginx` mounts `./nginx/ciel.conf:/etc/nginx/conf.d/default.conf:ro` and `./nginx/ciel.htpasswd:/etc/nginx/ciel.htpasswd:ro`. Caddyfile: `api.ciel-ai.web.id { reverse_proxy nginx:8080 }` (Caddy sets `X-Forwarded-For` to the real client IP, which nginx's rate limit keys on).

- [ ] **Step 1: Write the failing tests** (text checks; PyYAML is not a dependency)

```python
def test_images_are_pinned(self):
    for image in re.findall(r"image:\s*(\S+)", COMPOSE):
        self.assertRegex(image, r":\d+\.\d+")            # no :latest, no bare names
    self.assertIn("image: langflowai/langflow:1.12.4", COMPOSE)

def test_langflow_runs_one_worker_on_postgres(self):
    self.assertIn("LANGFLOW_WORKERS: \"1\"", COMPOSE)
    self.assertIn("postgresql://langflow:${POSTGRES_PASSWORD}@postgres:5432/langflow", COMPOSE)
    self.assertIn("LANGFLOW_VERTEX_BUILDS_STORAGE_ENABLED: \"false\"", COMPOSE)

def test_only_caddy_is_public_and_langflow_is_local(self):
    ports = re.findall(r"-\s*\"((?:127\.0\.0\.1:)?\d+:\d+)\"", COMPOSE)
    self.assertEqual(sorted(p for p in ports if not p.startswith("127.0.0.1:")), ["443:443", "80:80"])
    self.assertIn("\"127.0.0.1:7860:7860\"", COMPOSE)

def test_ollama_shares_langflows_localhost(self):
    self.assertIn("network_mode: \"service:langflow\"", COMPOSE)   # components call 127.0.0.1:11434

def test_every_service_restarts(self):
    self.assertEqual(COMPOSE.count("restart: unless-stopped"), 5)

def test_env_example_has_names_but_no_values(self):
    for line in ENV_EXAMPLE.splitlines():
        if line and not line.startswith("#"):
            name, _, value = line.partition("=")
            self.assertIn(value, ("", "60"))                 # GATEWAY_RUN_PER_MINUTE=60 only
    self.assertIn("deploy/vps/.env", GITIGNORE)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m unittest tests.test_vps_deploy -v`
Expected: FAIL with `FileNotFoundError` for `deploy/vps/docker-compose.yml`.

- [ ] **Step 3: Write the compose file, Caddyfile, `.env.example`, and `deploy/vps/README.md`**

The README is the runbook Task 8 follows, in this order: VPS requirements (Ubuntu 24.04, ≥ 4 vCPU, 8 GB RAM, ≥ 80 GB SSD, region Singapore or Jakarta); hardening (`ufw allow 22,80,443`, SSH key only, unattended-upgrades); Docker, restic and `python3-requests python3-dotenv` install (apt); clone to `/opt/ciel`; fill `.env`; `python3 tools/render_nginx_gateway.py --env-file deploy/vps/.env`; `docker compose up -d`; `docker compose exec langflow python -c "import pathlib; print(pathlib.Path.home())"` must print `/app/data` (if not, change the `langflow_home` mount and rerun the tests); pull `nomic-embed-text-v2-moe:latest` and `qwen2.5vl:3b` and compare `ollama list` IDs with the laptop; Langflow UI by `ssh -L 7860:127.0.0.1:7860`; the cron lines from Task 5; rollback to the laptop.

- [ ] **Step 4: Run to verify they pass**

Run: `python -m unittest tests.test_vps_deploy -v`
Expected: all OK. If Docker is available locally, also `docker compose -f deploy/vps/docker-compose.yml --env-file deploy/vps/.env.example config -q`; expected: exit 0.

- [ ] **Step 5: Add `tests.test_vps_deploy` to the CI list and commit**

```bash
git add deploy/vps tests/test_vps_deploy.py .github/workflows/ci.yml .gitignore
git commit -m "Add the VPS Docker Compose stack and its runbook"
```

---

### Task 5: Off-site backups, monthly restore check, and the privacy notice

**Files:**
- Create: `deploy/vps/backup.sh`, `deploy/vps/restore_check.sh`
- Modify: `privacy.py` (one item in the server-history section), `deploy/vps/README.md` (cron lines)
- Test: `tests/test_vps_deploy.py` (backup tests), `tests/test_privacy.py`

**Interfaces:**
- Consumes: Task 4's service and volume names and `.env` names.
- Produces: `backup.sh` and `restore_check.sh`, run from `/opt/ciel/deploy/vps` by root's crontab: backup daily `30 20 * * *` UTC (03:30 WIB), restore check monthly `0 21 1 * *`, retention `0 20 * * *` UTC running `python3 /opt/ciel/tools/prune_chat_history.py --days 30 --base-url http://127.0.0.1:7860`. Every cron line starts with `set -a; . /opt/ciel/deploy/vps/.env; set +a;` so the scripts get their settings (including `LANGFLOW_API_KEY`); output goes to `/var/log/ciel/<script>.log`.

`backup.sh` order (`set -euo pipefail`):
1. Fail (exit 1, no ping) when `df --output=pcent /` is above 80%.
2. `docker compose exec -T postgres pg_dump -U langflow -Fc langflow` → `$WORK/langflow.dump`.
3. `docker run --rm postgres:17.2 pg_dump -Fc "$SUPABASE_DB_URL"` → `$WORK/supabase.dump` (Supabase's free plan has no backups).
4. `docker compose pause langflow`, with `trap 'docker compose unpause langflow' EXIT` set **before** pausing; `restic backup` of the `langflow_home` volume's mountpoint (from `docker volume inspect`) and `$WORK`; unpause.
5. `restic forget --keep-daily 7 --keep-weekly 4 --prune`.
6. `curl -fsS -m 10 --retry 3 "$HEALTHCHECKS_BACKUP_URL"` as the last command.

`restore_check.sh`: `restic restore latest --target "$TMP"`; inside a throwaway `langflowai/langflow:1.12.4` container, open the restored `long_term_memory` with `chromadb.PersistentClient` and print the total count; `pg_restore --list` on both dumps; fail if the count is 0 or either list is empty; ping `HEALTHCHECKS_RESTORE_URL`; delete `$TMP`.

- [ ] **Step 1: Write the failing tests**

```python
def test_backup_pauses_langflow_safely(self):
    trap = BACKUP.index("trap 'docker compose unpause langflow' EXIT")
    self.assertLess(trap, BACKUP.index("docker compose pause langflow"))

def test_backup_keeps_about_five_weeks(self):
    self.assertIn("restic forget --keep-daily 7 --keep-weekly 4 --prune", BACKUP)
    self.assertNotIn("--keep-monthly", BACKUP)

def test_backup_includes_supabase_and_langflow_db(self):
    self.assertIn('pg_dump -Fc "$SUPABASE_DB_URL"', BACKUP)
    self.assertIn("pg_dump -U langflow -Fc langflow", BACKUP)

def test_success_ping_is_last_and_disk_check_is_first(self):
    lines = [l for l in BACKUP.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    self.assertIn("HEALTHCHECKS_BACKUP_URL", lines[-1])
    self.assertLess(BACKUP.index("df --output=pcent /"), BACKUP.index("pg_dump"))

def test_restore_check_fails_on_empty_memory(self):
    self.assertIn("chromadb.PersistentClient", RESTORE)
    self.assertIn("HEALTHCHECKS_RESTORE_URL", RESTORE)

def test_scripts_are_strict(self):
    for text in (BACKUP, RESTORE):
        self.assertIn("set -euo pipefail", text)
```

In `tests/test_privacy.py`: the rendered privacy text contains `cadangan terenkripsi` and `5 minggu`.

- [ ] **Step 2: Run to verify they fail**

Run: `python -m unittest tests.test_vps_deploy tests.test_privacy -v`
Expected: FAIL with `FileNotFoundError` for `backup.sh` and the missing privacy phrase.

- [ ] **Step 3: Write both scripts and the privacy item**

Privacy item (exact copy, in the server-history list): "Cadangan terenkripsi dari server Ciel dibuat setiap malam dan disimpan paling lama 5 minggu. Data yang kamu hapus ikut hilang dari cadangan setelah itu."

- [ ] **Step 4: Run to verify they pass, plus a shell syntax check**

Run: `python -m unittest tests.test_vps_deploy tests.test_privacy -v` and, in Git Bash, `bash -n deploy/vps/backup.sh && bash -n deploy/vps/restore_check.sh`
Expected: all OK, no output from `bash -n`. Add a CI step `bash -n deploy/vps/*.sh` next to the Edge Function tests.

- [ ] **Step 5: Ciel checks the privacy page in the browser** (local preview), then on Ciel's explicit "commit":

```bash
git add deploy/vps privacy.py tests/test_vps_deploy.py tests/test_privacy.py .github/workflows/ci.yml
git commit -m "Back up the VPS to R2 every night and say so on the privacy page"
```

---

### Task 6: Flow migration tool and sub-flows in Git

**Files:**
- Create: `tools/migrate_flows.py`
- Create (output, Task 8): `flow/subflows/Math_Tutor_Agent.json`, `flow/subflows/Knowledge_Retriever.json`
- Test: `tests/test_migrate_flows.py`

**Interfaces:**
- Consumes: Langflow REST: `GET /api/v1/flows/{id}`, `POST /api/v1/flows/` (header `x-api-key`).
- Produces:
  - `run_flow_targets(flow: dict) -> set[str]`: `template.flow_id_selected.value` of every node whose `data.type` is `RunFlow`.
  - `remap_run_flows(flow: dict, id_map: dict[str, str]) -> dict`: a deep copy with those values replaced; raises `KeyError` naming the ID when a target is missing from `id_map`.
  - `importable(flow: dict) -> dict`: drops `id`, `user_id`, `folder_id`, `updated_at`, `webhook`, `endpoint_name`.
  - `migrate(source_url, source_key, target_url, target_key, flow_ids: list[str]) -> dict[str, str]`: exports the given flows and, recursively, their Run Flow targets; imports targets before the flows that call them; returns `{old_id: new_id}`.
  - CLI: `--source-url`, `--target-url`, `--flow-id` (repeatable), `--map-out PATH` (JSON map, no secrets), `--snapshot-dir DIR` (writes each exported Run Flow target as `<name with spaces as _>.json`); keys from `SOURCE_LANGFLOW_API_KEY` and `TARGET_LANGFLOW_API_KEY`.

- [ ] **Step 1: Write the failing tests** (flows as small dicts; `requests` mocked)

```python
def test_finds_run_flow_targets(self):
    self.assertEqual(run_flow_targets(MAIN), {"math-old", "kb-old"})

def test_remap_replaces_targets_and_leaves_input_untouched(self):
    out = remap_run_flows(MAIN, {"math-old": "math-new", "kb-old": "kb-new"})
    self.assertEqual(run_flow_targets(out), {"math-new", "kb-new"})
    self.assertEqual(run_flow_targets(MAIN), {"math-old", "kb-old"})

def test_remap_refuses_unknown_target(self):
    with self.assertRaisesRegex(KeyError, "kb-old"):
        remap_run_flows(MAIN, {"math-old": "math-new"})

def test_sub_flows_are_imported_before_the_flow_that_calls_them(self):
    id_map = migrate("http://src", "k1", "http://dst", "k2", ["main-old"])
    posted = [c.kwargs["json"]["name"] for c in post.call_args_list]
    self.assertLess(posted.index("Math Tutor Agent"), posted.index("Ciel AI Long-Term Memory Master"))
    self.assertEqual(set(id_map), {"main-old", "math-old", "kb-old"})

def test_imported_flows_carry_no_source_ids(self):
    for call in post.call_args_list:
        self.assertFalse({"id", "user_id", "folder_id"} & set(call.kwargs["json"]))
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m unittest tests.test_migrate_flows -v`
Expected: FAIL with `ModuleNotFoundError: migrate_flows`.

- [ ] **Step 3: Implement `tools/migrate_flows.py`**

- [ ] **Step 4: Run to verify they pass**

Run: `python -m unittest tests.test_migrate_flows tests.test_secrets -v`
Expected: all OK.

- [ ] **Step 5: Add `tests.test_migrate_flows` to the CI list and commit**

```bash
git add tools/migrate_flows.py tests/test_migrate_flows.py .github/workflows/ci.yml
git commit -m "Add a tool that copies production flows between Langflow servers"
```

---

### Task 7: Alerts for a down backend and a low DeepSeek balance

**Files:**
- Create: `tools/check_deepseek_balance.py`, `.github/workflows/backend-health.yml`
- Test: `tests/test_backend_health.py`

**Interfaces:**
- Consumes: `tools/check_gateway.py` (existing; reads `NGROK_URL`, `NGROK_USER`, `NGROK_PASSWORD`, `FLOW_ID`, `MEMORY_ADMIN_FLOW_ID` from the environment).
- Produces:
  - `balance_ok(payload: dict, min_usd: float) -> tuple[bool, str]`: payload of `GET https://api.deepseek.com/user/balance`. False when `is_available` is false, or when the `USD` entry's `total_balance` is below `min_usd`; a payload with no `USD` entry is false with a message naming the currencies found. The message never contains the key.
  - CLI `main(argv=None) -> int` with `--min-usd` (default `3.0`), key from `DEEPSEEK_API_KEY`; exit 1 on a low balance, a non-200 status, or a network error.
  - Workflow: `schedule: cron '7,37 * * * *'` plus `workflow_dispatch`; `permissions: contents: read`; pinned action SHAs as in `ci.yml`; Python 3.14; installs `requests python-dotenv`; runs `python tools/check_gateway.py` then `python tools/check_deepseek_balance.py`, env from repository secrets `BACKEND_URL`, `BACKEND_USER`, `BACKEND_PASSWORD`, `FLOW_ID`, `MEMORY_ADMIN_FLOW_ID`, `DEEPSEEK_API_KEY` (mapped to `NGROK_URL`, `NGROK_USER`, `NGROK_PASSWORD` for `check_gateway.py`). `if: ${{ vars.BACKEND_HEALTH_ENABLED == 'true' }}` so it stays quiet until Task 8 switches it on. A failed run is GitHub's email to Ciel.

- [ ] **Step 1: Write the failing tests**

```python
def test_healthy_balance(self):
    self.assertEqual(balance_ok({"is_available": True, "balance_infos": [{"currency": "USD", "total_balance": "7.50"}]}, 3.0)[0], True)

def test_low_balance_fails(self):
    ok, message = balance_ok({"is_available": True, "balance_infos": [{"currency": "USD", "total_balance": "2.99"}]}, 3.0)
    self.assertFalse(ok); self.assertIn("2.99", message)

def test_unavailable_account_fails(self):
    self.assertFalse(balance_ok({"is_available": False, "balance_infos": []}, 3.0)[0])

def test_missing_usd_names_the_currencies(self):
    ok, message = balance_ok({"is_available": True, "balance_infos": [{"currency": "CNY", "total_balance": "50"}]}, 3.0)
    self.assertFalse(ok); self.assertIn("CNY", message)

def test_network_error_exits_1_without_printing_the_key(self):
    # requests.get raises ConnectionError; DEEPSEEK_API_KEY="sk-test-123"; main() == 1; "sk-test-123" not in captured output

def test_workflow_is_gated_pinned_and_read_only(self):
    self.assertIn("vars.BACKEND_HEALTH_ENABLED == 'true'", WORKFLOW)
    self.assertIn("contents: read", WORKFLOW)
    self.assertNotRegex(WORKFLOW, r"uses: [^@]+@v\d")          # SHAs, not tags
    self.assertIn("python tools/check_gateway.py", WORKFLOW)
    self.assertIn("python tools/check_deepseek_balance.py", WORKFLOW)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m unittest tests.test_backend_health -v`
Expected: FAIL with `ModuleNotFoundError: check_deepseek_balance`.

- [ ] **Step 3: Implement the tool and the workflow**

- [ ] **Step 4: Run to verify they pass**

Run: `python -m unittest tests.test_backend_health tests.test_supply_chain -v`
Expected: all OK (`test_supply_chain` also checks workflow pinning).

- [ ] **Step 5: Add `tests.test_backend_health` to the CI list and commit**

```bash
git add tools/check_deepseek_balance.py .github/workflows/backend-health.yml tests/test_backend_health.py .github/workflows/ci.yml
git commit -m "Email Ciel when the backend is down or the DeepSeek balance runs low"
```

---

### Task 8: Cutover from the laptop to the VPS

This task is operations, done together with Ciel, following `deploy/vps/README.md`. Each step names who acts. The agent never types a secret.

**Files:**
- Create: `flow/subflows/Math_Tutor_Agent.json`, `flow/subflows/Knowledge_Retriever.json` (from Task 6's `--snapshot-dir`)
- Modify: `docs/ARCHITECTURE.md` (High-Level Architecture, Public Deployment Safeguards, Langflow Configuration Outside the Repository), `docs/BACKUP_AND_DISASTER_RECOVERY.md` (the "not in Git" table and recovery procedure for the VPS), `docs/PRODUCTION_READINESS_REVIEW.md` (new "Status Update" closing the open risks it lists), `SECURITY.md` (gateway section), `CHANGELOG.md`, `README.md` (backend host section)

**Interfaces:**
- Consumes: everything in Tasks 2–7, merged to `main` and deployed to Streamlit Cloud first (the app change is backward compatible with the laptop backend).

- [ ] **Step 1 (Ciel): Buy the VPS** to the README's requirements, add the agent's SSH public key, and add DNS record `api` (A, and AAAA if the VPS has IPv6) → VPS IP, **DNS only** (grey cloud).
- [ ] **Step 2 (agent over SSH, Ciel fills `.env`): Bring the stack up** per the README. Verify: `docker compose ps` shows 5 services `running`; `curl -s -o /dev/null -w '%{http_code}' https://api.ciel-ai.web.id/health_check` prints `401`; `Path.home()` check prints `/app/data`; `ollama list` IDs match the laptop's.
- [ ] **Step 3 (Ciel, Langflow UI over the SSH tunnel): Log in as the superuser, then create** one API key, global variables `DEEPSEEK_API_KEY` and `EXA_API_KEY`, and the `GEMINI_API_KEY` credential.
- [ ] **Step 4 (agent, on the laptop with an SSH tunnel to the VPS on port 17860): Migrate flows**: `python tools/migrate_flows.py --source-url http://127.0.0.1:7860 --target-url http://127.0.0.1:17860 --flow-id <FLOW_ID> --flow-id <RESEARCH_FLOW_ID> --flow-id <WRITER_FLOW_ID> --flow-id <MEMORY_ADMIN_FLOW_ID> --map-out ~/.ciel_ai/flow_backups/vps_id_map.json --snapshot-dir flow/subflows`. Verify: 6 flows in the map; `python -m unittest tests.test_secrets` passes with the new snapshots.
- [ ] **Step 5 (agent): Copy the knowledge base** for Knowledge Retriever into the path the VPS Langflow reports (`docker compose exec langflow python -c "from langflow.services.deps import get_settings_service as s; print(s().settings.knowledge_bases_dir)"`), and the built-in dataset to `/app/data/.ciel_ai/builtin_datasets/`.
- [ ] **Step 6 (agent): Pre-cutover quality run** against the VPS with temporary local settings (`NGROK_URL=https://api.ciel-ai.web.id`, the VPS password and API key, new flow IDs): `python tests/collect_quality.py`. Expected: response quality 9/9, automated checks 5/5, status healthy, and the must-search / must-not-search routing set unchanged. Stop and report to Ciel on any failure.
- [ ] **Step 7 (Ciel announces, then both): Maintenance window (about 30 minutes).** Disable the "Ciel backend watchdog" task, stop Langflow Desktop and ngrok on the laptop; compare `pip show chromadb` versions on both sides (different → stop and ask Ciel); copy `~/.ciel_ai/long_term_memory` and `~/.ciel_ai/user_datasets` into the `langflow_home` volume under `.ciel_ai/`; `chown -R 1000:0`. Verify: per-collection counts equal on both sides, and a Memory Search for a known memory of Ciel's own account returns it.
- [ ] **Step 8 (Ciel): Switch Streamlit Cloud secrets** `NGROK_URL`, `NGROK_PASSWORD`, `LANGFLOW_API_KEY`, `FLOW_ID`, `RESEARCH_FLOW_ID`, `WRITER_FLOW_ID`, `MEMORY_ADMIN_FLOW_ID`, then reboot the app. Verify: agent runs `python tools/check_gateway.py` with the new values (all PASS); Ciel checks chat, a photo question, a research question, "Data saya", and one Pro feature in the browser.
- [ ] **Step 9 (agent): Turn on the safety nets.** Install the three cron lines; run `backup.sh` once (exit 0, Healthchecks shows a ping, `restic snapshots` lists one); run `restore_check.sh` once (non-zero memory count, ping). Ciel sets the repository secrets from Task 7 and variable `BACKEND_HEALTH_ENABLED=true`, then runs the workflow once by hand (green).
- [ ] **Step 10 (agent): Docs, then commit and PR.** Update the files listed above; the readiness review's new status update states what is closed and what stays open (single VPS, Streamlit Community Cloud limits). Commit the snapshots and docs on a branch and open a PR after Ciel's go-ahead.
- [ ] **Step 11 (Ciel, after 14 days): Retire the laptop backend.** Until then the laptop is the rollback: re-enable the watchdog and switch the Streamlit secrets back (memories written on the VPS meanwhile would not be on the laptop). After 14 days without a rollback, Ciel decides whether to uninstall the watchdog and ngrok.
