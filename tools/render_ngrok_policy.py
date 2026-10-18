"""Write the ngrok traffic policy for Ciel's tunnel from .env.

The tunnel forwards to Langflow, which can do far more than the app needs
(its UI, the flow API, archived flows). The policy lets through only what the
app and the watchdog use, with the exact flow IDs:

  1. per-IP rate limit on every path (slows down password guessing and scans)
  2. Basic Auth
  3. allowlist; anything else answers 404
  4. per-IP rate limit on running the flow and uploading images

Settings come from the environment, then the repository's .env:

  NGROK_USER, NGROK_PASSWORD   Basic Auth (the app sends the same pair)
  FLOW_ID                      main flow
  MEMORY_ADMIN_FLOW_ID         Ciel Memory Admin flow ("Data saya")
  NGROK_POLICY_FILE            default %USERPROFILE%\\ngrok-ciel-policy.yml

The file is JSON, which ngrok reads like YAML. Nothing secret is printed.
Restart ngrok afterwards (stop it; the watchdog starts it with this file),
then run tools/check_gateway.py.
"""

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
UUID = re.compile(r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$")
MIN_PASSWORD = 24
MAX_PASSWORD = 128  # ngrok's limit
SESSIONS_PATH = "/api/v1/monitor/messages/sessions"


class PolicyError(ValueError):
    pass


def exact_path(path):
    # path is normalized by ngrok, raw_path is what Langflow receives; both must match.
    return f"(req.url.path == '{path}' && req.url.raw_path == '{path}')"


def id_forms(flow_id):
    # Langflow accepts a flow ID with or without dashes; the app's secret may use either.
    return [flow_id, flow_id.replace("-", "")]


def allowed_requests(flow_id, admin_flow_id):
    """(method, path) pairs the app and the watchdog use."""
    return [
        *(("POST", f"/api/v1/run/{form}") for form in id_forms(flow_id)),
        *(("POST", f"/api/v1/run/{form}") for form in id_forms(admin_flow_id)),
        *(("POST", f"/api/v1/files/upload/{form}") for form in id_forms(flow_id)),
        ("GET", SESSIONS_PATH),
        ("DELETE", SESSIONS_PATH),
        ("GET", "/health_check"),
    ]


def any_of(requests):
    return " || ".join(f"(req.method == '{method}' && {exact_path(path)})" for method, path in requests)


def rate_limit(name, capacity):
    return {
        "type": "rate-limit",
        "config": {
            "name": name,
            "algorithm": "sliding_window",
            "capacity": capacity,
            "rate": "60s",
            "bucket_key": ["conn.client_ip"],
        },
    }


def check_settings(user, password, flow_id, admin_flow_id):
    if not user or not password:
        raise PolicyError("NGROK_USER dan NGROK_PASSWORD wajib diisi.")
    if ":" in user:
        raise PolicyError("NGROK_USER tidak boleh berisi titik dua.")
    if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
        raise PolicyError(
            f"NGROK_PASSWORD harus {MIN_PASSWORD}-{MAX_PASSWORD} karakter. Buat yang baru, misalnya: "
            'python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )
    if "${" in user + password:
        # ngrok evaluates ${...} in credentials as an expression.
        raise PolicyError("NGROK_USER dan NGROK_PASSWORD tidak boleh berisi '${'.")
    for name, value in (("FLOW_ID", flow_id), ("MEMORY_ADMIN_FLOW_ID", admin_flow_id)):
        if not UUID.match(str(value or "")):
            raise PolicyError(f"{name} harus UUID flow Langflow (huruf kecil, boleh tanpa tanda hubung).")


def build_policy(user, password, flow_id, admin_flow_id):
    check_settings(user, password, flow_id, admin_flow_id)
    flow_id, admin_flow_id = str(uuid.UUID(flow_id)), str(uuid.UUID(admin_flow_id))
    allowed = allowed_requests(flow_id, admin_flow_id)
    costly = [r for r in allowed if r[1].startswith(("/api/v1/run/", "/api/v1/files/upload/"))]
    return {
        "on_http_request": [
            {"actions": [rate_limit("ciel-all-per-ip", 120)]},
            {"actions": [{"type": "basic-auth", "config": {"credentials": [f"{user}:{password}"]}}]},
            {
                "expressions": [f"!({any_of(allowed)})"],
                "actions": [{"type": "custom-response", "config": {"status_code": 404, "body": "Not found"}}],
            },
            {"expressions": [any_of(costly)], "actions": [rate_limit("ciel-api-per-ip", 20)]},
        ]
    }


def load_settings(env_file):
    values = {k: v for k, v in dotenv_values(env_file).items() if v} if env_file.is_file() else {}
    values.update({k: v for k, v in os.environ.items() if v})
    return values


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--output", type=Path, help="default: NGROK_POLICY_FILE or ~/ngrok-ciel-policy.yml")
    args = parser.parse_args(argv)

    settings = load_settings(args.env_file)
    output = args.output or Path(settings.get("NGROK_POLICY_FILE") or Path.home() / "ngrok-ciel-policy.yml")

    try:
        policy = build_policy(
            settings.get("NGROK_USER", "").strip(),
            settings.get("NGROK_PASSWORD", "").strip(),
            settings.get("FLOW_ID", "").strip().lower(),
            settings.get("MEMORY_ADMIN_FLOW_ID", "").strip().lower(),
        )
    except PolicyError as error:
        print(f"Policy tidak ditulis: {error}", file=sys.stderr)
        return 1

    output.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
    print(f"Policy ditulis ke {output}. Restart ngrok, lalu jalankan tools/check_gateway.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
