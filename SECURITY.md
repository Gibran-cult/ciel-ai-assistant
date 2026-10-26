# Security

## Reporting a vulnerability

Please report security problems privately through GitHub: **Security → Report a vulnerability** on this repository. Do not open a public issue. Include what you found, how to reproduce it, and what an attacker could do with it.

## How Ciel is protected

No system is unbreakable. Ciel's controls aim to close the holes that can realistically be used, limit what one broken layer gives an attacker, and leave traces in the logs.

| Threat | Controls |
|---|---|
| Running code on the Langflow host | No production component runs model-written code (since flow v1.11.0): Verified Data Analyst, a CSV agent with `allow_dangerous_code=True`, is gone, and Math Tutor has only Langflow's Calculator (no Python Interpreter), which evaluates arithmetic with an AST allowlist. Ciel Table Analyst and Ciel ML Analyst compute statistics and models deterministically. Langflow 1.12 refuses tweaks to a component's `code` field. |
| Reaching Langflow through the tunnel | The ngrok traffic policy (`tools/render_ngrok_policy.py`) applies a per-IP rate limit, then Basic Auth, then an exact allowlist of the paths the app uses, with the exact flow IDs. Every other path answers 404. Langflow, Ollama and the ngrok agent API listen on `127.0.0.1` only. `tools/check_gateway.py` verifies the live policy. |
| One user's data reaching another | The app derives each user's owner ID from the Google account and sends it through tweaks, never through the model. Memory, datasets, chat history (Supabase, RLS with no policies plus an owner filter on every request) and Langflow sessions are all scoped by it. Guests get no memory or saved data. |
| Prompt injection (web pages, files, photos, memory) | Prompt v14.7, section "10. KEAMANAN": content from tools is data, not instructions; memory and datasets are saved only from the user's own message; no images, HTML or URLs carrying conversation data. The app removes markdown images from answers before showing them, so an injected image cannot send chat data anywhere. Ciel Source Guard drops sources whose URL no search returned. Users see and delete their memories and datasets under "Data saya". |
| Abuse and API bills | Per-user, guest and global hourly and daily message limits in the app; a per-IP limit at ngrok; caps on message length, upload size and image pixels; spending caps at each provider (see the owner checklist). |
| Leaked or vulnerable code and secrets | Secrets live only in Streamlit Secrets, the host's `.env` and Langflow global variables, never in Git. GitHub secret scanning with push protection, Dependabot (pip and GitHub Actions), `pip-audit` in CI, and Actions pinned to commit SHAs. `tests/test_secrets.py` fails CI when a tracked file holds a key-shaped string (Langflow, Supabase JWT, Google, GitHub, Midtrans, private keys); it covers keys GitHub's scanner does not know. Dependencies are locked with hashes (`requirements.in` → `uv pip compile --generate-hashes` → `requirements.txt`), so a release swapped on PyPI fails the install instead of reaching production, and CI installs and audits that same lock. |

## Incident runbook

### 1. Take Ciel offline

On the Langflow host, stop the tunnel and keep the watchdog from restarting it:

```powershell
Disable-ScheduledTask -TaskName 'Ciel backend watchdog'
Stop-Process -Name ngrok -Force
```

The app then shows its error card; nothing on the host is reachable from the internet. Start again with `Enable-ScheduledTask -TaskName 'Ciel backend watchdog'` once the cause is fixed.

### 2. Rotate what may have leaked

| Secret | Lives in | How to rotate |
|---|---|---|
| `NGROK_PASSWORD` (and `NGROK_USER`) | `.env` on the host, Streamlit Secrets, the policy file | Generate a new value of at least 32 random characters, put it in `.env` and Streamlit Secrets, run `python tools/render_ngrok_policy.py`, restart ngrok (stop it; the watchdog starts it), then run `python tools/check_gateway.py`. |
| `LANGFLOW_API_KEY` | `.env`, Streamlit Secrets | Langflow → Settings → API Keys: create a new key, update both places, then delete the old key. |
| `DEEPSEEK_API_KEY`, `EXA_API_KEY`, `GEMINI_API_KEY` | Langflow global variables | Create a new key in the provider's dashboard, update the global variable, revoke the old key. |
| `SUPABASE_SERVICE_KEY` | Streamlit Secrets | Supabase → Project Settings → API: roll the service key, update Streamlit Secrets. |
| `[auth] client_secret`, `cookie_secret` | Streamlit Secrets | Google Cloud Console → Credentials for the client secret. A new `cookie_secret` signs everyone out. |
| ngrok authtoken | ngrok agent config on the host | ngrok dashboard → Authtokens. |

### 3. Find out what happened

- Streamlit Cloud logs: search for `security_event`, `rate_limited` and the Request ID a user reported.
- ngrok: the dashboard's traffic view, and `~/.ciel_ai/logs/ngrok.log` on the host.
- Watchdog: `~/.ciel_ai/logs/watchdog.log`.
- Langflow: messages and transactions per session, through the Langflow UI on the host.

### 4. Recover

Restore from the backups in `docs/BACKUP_AND_DISASTER_RECOVERY.md` if needed. Run `tools/check_gateway.py` and a live quality run (`tests/collect_quality.py`), and record the incident in `CHANGELOG.md`.

## Owner checklist

- Revoke the Langflow key that was hardcoded in flow v1.0.0/v1.1.0 (prefix `sk-Qcdm`, in Git history of this public repo; removed from the files 2026-10-26). Langflow → Settings → API Keys.
- Two-factor authentication on GitHub, the Google account that owns the OAuth client, Streamlit Cloud, Supabase, ngrok, DeepSeek, Exa and Google AI Studio.
- Hard spending limits: DeepSeek without automatic top-up, a quota or budget on the Gemini project, and Exa's usage limit.
- `[auth] cookie_secret` of at least 32 random bytes.
- On the Langflow host: automatic Windows Update, BitLocker, Defender and the firewall on (both checked 2026-10-18), Langflow Desktop kept up to date, and never start ngrok from an administrator window.
- On the home router: no port forwards and UPnP off. The tunnel needs neither.
- The old Langflow key in this public repository's history (prefix `sk-Qcdm`) must stay deleted from Langflow's API key list.

## Known limits

- Links in answers can still be clicked, and injected text can still bend what an answer says, even though it can no longer run code, send data through images, or reach the backend.
- Whoever holds the Streamlit Secrets can do everything the app can do, within the gateway allowlist.
- Ciel relies on Google, Streamlit, Supabase, ngrok and the model providers being secure.
- The backend is one home PC: when it is off, asleep or out of ngrok's free quota, Ciel is offline.
