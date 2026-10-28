"""Write the nginx gateway config for Ciel's VPS from .env.

On the VPS, Caddy terminates TLS and forwards to this nginx, which forwards to
Langflow (langflow:7860). It enforces the same rules as the ngrok policy
(tools/render_ngrok_policy.py), generated from the same allowlist so the two
cannot drift apart:

  1. per-IP rate limit on every path
  2. Basic Auth
  3. allowlist: one exact `location = <path>` per allowed path, limited to its
     methods; anything else answers 404
  4. per-IP rate limit on running the flow and uploading images

Differences that come from nginx rather than from the rules:

  - Caddy sets X-Forwarded-For to the real client IP, so the limits key on
    $http_x_forwarded_for.
  - Langflow receives $uri (the normalized path that matched the location),
    never $request_uri, so what Langflow sees is exactly the path the
    allowlist matched (not the raw, possibly encoded or dotted, request line).
  - Langflow's container can get a new IP when it is restarted or recreated.
    The config proxies to `upstream langflow_backend`, whose server has the
    `resolve` flag (nginx 1.27.3 open source; it needs the shared `zone`), and
    declares Docker's DNS (`resolver 127.0.0.11`), so nginx follows the new
    address within 10 s instead of keeping the one it saw at start-up.
  - The gateway's Basic Auth header is cleared (`proxy_set_header
    Authorization ""`): Langflow authenticates with x-api-key and never sees
    the gateway password.
  - nginx keeps only the limit_req lines of the innermost level, so the costly
    locations repeat the per-IP limit on every path.

Settings use the same names as the ngrok policy (NGROK_USER, NGROK_PASSWORD,
FLOW_ID, MEMORY_ADMIN_FLOW_ID, RESEARCH_FLOW_ID, WRITER_FLOW_ID). With
--env-file the file is the source of truth: every name it lists wins over
the environment, also a name left empty, so a shell that still exports old
flow IDs cannot leak them into the config. Without --env-file, the
environment wins over the repository's .env (as for the ngrok policy). Two
optional limits:

  GATEWAY_RUN_PER_MINUTE   per IP, flow runs and uploads (default 60)
  GATEWAY_ALL_PER_MINUTE   per IP, every path (default 300)

Two files are written, both git-ignored:

  deploy/vps/nginx/ciel.conf       an http-context include (mounted as
                                   /etc/nginx/conf.d/default.conf)
  deploy/vps/nginx/ciel.htpasswd   the Basic Auth user, salted SHA-1 ({SSHA})
                                   (mounted as /etc/nginx/ciel.htpasswd)

Nothing secret is printed; the flow IDs used are, so a stale one shows.
"""

import argparse
import base64
import hashlib
import os
import sys
import uuid
from pathlib import Path

from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parent))

from render_ngrok_policy import (  # noqa: E402
    ROOT,
    PolicyError,
    allowed_requests,
    check_settings,
    load_settings,
)

UPSTREAM_NAME = "langflow_backend"
UPSTREAM_SERVER = "langflow:7860"
DOCKER_DNS = "127.0.0.11"
HTPASSWD_PATH = "/etc/nginx/ciel.htpasswd"
READ_TIMEOUT = "600s"  # longer than the app's research timeout (420 s)
COSTLY_PREFIXES = ("/api/v1/run/", "/api/v1/files/upload/")
DEFAULT_RUN_PER_MINUTE = 60
DEFAULT_ALL_PER_MINUTE = 300


def check_rate(name, value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise PolicyError(f"{name} harus bilangan bulat positif.")
    return value


def methods_by_path(requests):
    """{path: [methods]} in first-seen order."""
    grouped = {}
    for method, path in requests:
        methods = grouped.setdefault(path, [])
        if method not in methods:
            methods.append(method)
    return grouped


def location(path, methods):
    lines = [
        f"    location = {path} {{",
        f"        limit_except {' '.join(methods)} {{ deny all; }}",
    ]
    if path.startswith(COSTLY_PREFIXES):
        # a limit_req here replaces the server-level one, so both are listed
        lines += [
            "        limit_req zone=ciel_all burst=60 nodelay;",
            "        limit_req zone=ciel_api burst=20 nodelay;",
        ]
    lines += [
        '        proxy_set_header Authorization "";',
        f"        proxy_pass http://{UPSTREAM_NAME}$uri$is_args$args;",
        "    }",
    ]
    return "\n".join(lines)


def build_nginx_config(
    user,
    password,
    flow_id,
    admin_flow_id,
    research_flow_id=None,
    writer_flow_id=None,
    run_per_minute=DEFAULT_RUN_PER_MINUTE,
    all_per_minute=DEFAULT_ALL_PER_MINUTE,
):
    check_settings(user, password, flow_id, admin_flow_id, research_flow_id, writer_flow_id)
    run_per_minute = check_rate("GATEWAY_RUN_PER_MINUTE", run_per_minute)
    all_per_minute = check_rate("GATEWAY_ALL_PER_MINUTE", all_per_minute)
    flow_id, admin_flow_id = str(uuid.UUID(flow_id)), str(uuid.UUID(admin_flow_id))
    research_flow_id = str(uuid.UUID(research_flow_id)) if research_flow_id else None
    writer_flow_id = str(uuid.UUID(writer_flow_id)) if writer_flow_id else None
    allowed = allowed_requests(flow_id, admin_flow_id, research_flow_id, writer_flow_id)

    locations = [location(path, methods) for path, methods in methods_by_path(allowed).items()]
    return "\n".join(
        [
            "# Generated by tools/render_nginx_gateway.py. Do not edit; do not commit.",
            f"limit_req_zone $http_x_forwarded_for zone=ciel_all:10m rate={all_per_minute}r/m;",
            f"limit_req_zone $http_x_forwarded_for zone=ciel_api:10m rate={run_per_minute}r/m;",
            "",
            f"resolver {DOCKER_DNS} valid=10s ipv6=off;",
            f"upstream {UPSTREAM_NAME} {{ zone {UPSTREAM_NAME} 64k; server {UPSTREAM_SERVER} resolve; }}",
            "",
            "server {",
            "    listen 8080;",
            '    auth_basic "Ciel";',
            f"    auth_basic_user_file {HTPASSWD_PATH};",
            "    limit_req zone=ciel_all burst=60 nodelay;",
            "    limit_req_status 429;",
            "    client_max_body_size 30m;",
            f"    proxy_read_timeout {READ_TIMEOUT};",
            f"    proxy_send_timeout {READ_TIMEOUT};",
            "",
            *(block + "\n" for block in locations),
            "    location / {",
            "        return 404;",
            "    }",
            "}",
            "",
        ]
    )


def htpasswd_line(user, password, salt):
    """nginx's {SSHA} scheme: base64(sha1(password + salt) + salt)."""
    digest = hashlib.sha1(password.encode("utf-8") + salt).digest()
    return f"{user}:{{SSHA}}" + base64.b64encode(digest + salt).decode("ascii")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    # bytes, so Windows does not turn \n into \r\n in files the Linux container reads
    path.write_bytes(text.encode("utf-8"))


FLOW_ID_NAMES = ("FLOW_ID", "MEMORY_ADMIN_FLOW_ID", "RESEARCH_FLOW_ID", "WRITER_FLOW_ID")


def gateway_settings(env_file):
    """Settings for the renderer.

    env_file None: the environment wins over the repository's .env (load_settings).
    An explicit env_file is the source of truth: every name it lists wins over the
    environment, also when it is left empty (an optional flow that is not used).
    """
    if env_file is None:
        return load_settings(ROOT / ".env")
    values = dict(os.environ)
    if env_file.is_file():
        values.update({k: v or "" for k, v in dotenv_values(env_file).items()})
    return {k: v for k, v in values.items() if v}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", type=Path, help="its values win over the environment (default: .env, below it)")
    parser.add_argument("--conf-out", type=Path, default=ROOT / "deploy" / "vps" / "nginx" / "ciel.conf")
    parser.add_argument("--htpasswd-out", type=Path, default=ROOT / "deploy" / "vps" / "nginx" / "ciel.htpasswd")
    args = parser.parse_args(argv)

    settings = gateway_settings(args.env_file)
    user = settings.get("NGROK_USER", "").strip()
    password = settings.get("NGROK_PASSWORD", "").strip()

    try:
        limits = {}
        for key, name in (("GATEWAY_RUN_PER_MINUTE", "run_per_minute"), ("GATEWAY_ALL_PER_MINUTE", "all_per_minute")):
            raw = settings.get(key, "").strip()
            if raw:
                try:
                    limits[name] = int(raw)
                except ValueError:
                    raise PolicyError(f"{key} harus bilangan bulat positif.") from None
        conf = build_nginx_config(
            user,
            password,
            settings.get("FLOW_ID", "").strip().lower(),
            settings.get("MEMORY_ADMIN_FLOW_ID", "").strip().lower(),
            settings.get("RESEARCH_FLOW_ID", "").strip().lower() or None,
            settings.get("WRITER_FLOW_ID", "").strip().lower() or None,
            **limits,
        )
    except PolicyError as error:
        print(f"Config tidak ditulis: {error}", file=sys.stderr)
        return 1

    write_text(args.conf_out, conf)
    write_text(args.htpasswd_out, htpasswd_line(user, password, os.urandom(8)) + "\n")
    print(f"Config ditulis ke {args.conf_out} dan {args.htpasswd_out}.")
    print("Flow ID yang dipakai: " + ", ".join(
        f"{name}={settings.get(name, '').strip().lower() or '-'}" for name in FLOW_ID_NAMES
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
