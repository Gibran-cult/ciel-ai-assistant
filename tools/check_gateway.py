"""Check the live ngrok gateway against the policy from render_ngrok_policy.py.

Sends about 11 requests through the tunnel (NGROK_URL, NGROK_USER and
NGROK_PASSWORD from the environment, then the repository's .env). It never
sends the Langflow API key, so no flow runs. Prints one PASS/FAIL line per
probe and exits with 1 if any probe fails. Nothing secret is printed.
"""

import argparse
import sys
import uuid
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_ngrok_policy import ROOT, load_settings  # noqa: E402

TIMEOUT = 20
# Langflow refuses a request without an API key with 401 or 403 before it runs
# anything; 404 would mean the gateway blocked a path the app needs.
REACHES_LANGFLOW = (401, 403)


def probes(flow_id, admin_flow_id):
    """(description, method, path, with credentials, accepted status codes)."""
    blocked = (404,)
    return [
        ("tanpa password ditolak", "GET", "/health_check", False, (401,)),
        ("health check", "GET", "/health_check", True, (200,)),
        ("run flow utama sampai ke Langflow", "POST", f"/api/v1/run/{flow_id}?stream=false", True, REACHES_LANGFLOW),
        ("run Memory Admin sampai ke Langflow", "POST", f"/api/v1/run/{admin_flow_id}", True, REACHES_LANGFLOW),
        ("daftar session sampai ke Langflow", "GET", "/api/v1/monitor/messages/sessions", True, REACHES_LANGFLOW),
        ("UI Langflow diblokir", "GET", "/", True, blocked),
        ("API flows diblokir", "GET", "/api/v1/flows/", True, blocked),
        ("API users diblokir", "GET", "/api/v1/users/whoami", True, blocked),
        ("dokumentasi API diblokir", "GET", "/docs", True, blocked),
        ("validasi kode diblokir", "POST", "/api/v1/validate/code", True, blocked),
        ("flow lain diblokir", "POST", f"/api/v1/run/{uuid.uuid4()}", True, blocked),
    ]


def run_probes(base_url, auth, flow_id, admin_flow_id, send=requests.request):
    failures = 0
    for description, method, path, with_auth, accepted in probes(flow_id, admin_flow_id):
        try:
            status = send(
                method,
                base_url + path,
                auth=auth if with_auth else None,
                headers={"ngrok-skip-browser-warning": "1"},
                timeout=TIMEOUT,
                allow_redirects=False,
            ).status_code
        except requests.exceptions.RequestException as error:
            status = type(error).__name__
        ok = status in accepted
        failures += not ok
        expected = "/".join(str(code) for code in accepted)
        print(f"{'PASS' if ok else 'FAIL'}  {method:6} {path.split('?')[0]:45} {status} (harus {expected})  {description}")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args(argv)

    settings = load_settings(args.env_file)
    missing = [k for k in ("NGROK_URL", "NGROK_USER", "NGROK_PASSWORD", "FLOW_ID", "MEMORY_ADMIN_FLOW_ID") if not settings.get(k)]
    if missing:
        print(f"Belum diisi: {', '.join(missing)}", file=sys.stderr)
        return 1

    failures = run_probes(
        settings["NGROK_URL"].rstrip("/"),
        (settings["NGROK_USER"], settings["NGROK_PASSWORD"]),
        settings["FLOW_ID"].strip().lower(),
        settings["MEMORY_ADMIN_FLOW_ID"].strip().lower(),
    )
    print("Gateway OK." if not failures else f"{failures} pemeriksaan gagal.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
