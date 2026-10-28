import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VPS = ROOT / "deploy" / "vps"


def read(path):
    return path.read_text(encoding="utf-8")


COMPOSE = read(VPS / "docker-compose.yml")
CADDYFILE = read(VPS / "Caddyfile")
ENV_EXAMPLE = read(VPS / ".env.example")
README = read(VPS / "README.md")
GITIGNORE = read(ROOT / ".gitignore")

SERVICES = ("caddy", "nginx", "langflow", "postgres", "ollama")

ENV_NAMES = (
    "LANGFLOW_SUPERUSER",
    "LANGFLOW_SUPERUSER_PASSWORD",
    "LANGFLOW_SECRET_KEY",
    "POSTGRES_PASSWORD",
    "SUPABASE_DB_URL",
    "RESTIC_REPOSITORY",
    "RESTIC_PASSWORD",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "HEALTHCHECKS_BACKUP_URL",
    "HEALTHCHECKS_RESTORE_URL",
    "LANGFLOW_API_KEY",
    "NGROK_USER",
    "NGROK_PASSWORD",
    "FLOW_ID",
    "MEMORY_ADMIN_FLOW_ID",
    "RESEARCH_FLOW_ID",
    "WRITER_FLOW_ID",
    "GATEWAY_RUN_PER_MINUTE",
)


def service_block(name):
    """The text of one top-level service in the compose file."""
    match = re.search(
        rf"^  {name}:\n(.*?)(?=^  \S|^\S|\Z)", COMPOSE, re.MULTILINE | re.DOTALL
    )
    assert match, f"service {name} not found"
    return match.group(1)


class ComposeTest(unittest.TestCase):
    def test_images_are_pinned(self):
        images = re.findall(r"image:\s*(\S+)", COMPOSE)
        self.assertEqual(len(images), 5)
        for image in images:
            self.assertRegex(image, r":\d+\.\d+")  # no :latest, no bare names
        self.assertIn("image: langflowai/langflow:1.12.4", COMPOSE)
        self.assertIn("image: postgres:16.4", COMPOSE)
        self.assertIn("image: nginx:1.27.3-alpine", COMPOSE)
        self.assertIn("image: caddy:2.8.4", COMPOSE)
        self.assertIn("image: ollama/ollama:0.40.10", COMPOSE)  # the laptop's version

    def test_has_the_five_services(self):
        for name in SERVICES:
            self.assertIn(f"\n  {name}:\n", COMPOSE)

    def test_langflow_runs_one_worker_on_postgres(self):
        self.assertIn('LANGFLOW_WORKERS: "1"', COMPOSE)
        self.assertIn(
            "postgresql://langflow:${POSTGRES_PASSWORD}@postgres:5432/langflow", COMPOSE
        )
        self.assertIn('LANGFLOW_VERTEX_BUILDS_STORAGE_ENABLED: "false"', COMPOSE)
        self.assertIn('LANGFLOW_AUTO_LOGIN: "false"', COMPOSE)
        self.assertIn('LANGFLOW_HOST: "0.0.0.0"', COMPOSE)
        self.assertIn('LANGFLOW_PORT: "7860"', COMPOSE)

    def test_langflow_waits_for_a_healthy_postgres(self):
        block = service_block("langflow")
        self.assertIn("condition: service_healthy", block)
        self.assertIn("pg_isready", service_block("postgres"))

    def test_only_caddy_is_public_and_langflow_is_local(self):
        ports = re.findall(r"-\s*\"((?:127\.0\.0\.1:)?\d+:\d+)\"", COMPOSE)
        self.assertEqual(
            sorted(p for p in ports if not p.startswith("127.0.0.1:")), ["443:443", "80:80"]
        )
        self.assertIn('"127.0.0.1:7860:7860"', COMPOSE)
        self.assertIn('"80:80"', service_block("caddy"))
        self.assertIn('"127.0.0.1:7860:7860"', service_block("langflow"))
        for name in ("nginx", "postgres", "ollama"):
            self.assertNotIn("ports:", service_block(name))  # nginx :8080 stays internal

    def test_ollama_shares_langflows_localhost(self):
        self.assertIn('network_mode: "service:langflow"', COMPOSE)  # calls 127.0.0.1:11434
        self.assertIn('network_mode: "service:langflow"', service_block("ollama"))

    def test_every_service_restarts(self):
        self.assertEqual(COMPOSE.count("restart: unless-stopped"), 5)
        for name in SERVICES:
            self.assertIn("restart: unless-stopped", service_block(name))

    def test_nginx_mounts_the_generated_gateway_files(self):
        block = service_block("nginx")
        self.assertIn("./nginx/ciel.conf:/etc/nginx/conf.d/default.conf:ro", block)
        self.assertIn("./nginx/ciel.htpasswd:/etc/nginx/ciel.htpasswd:ro", block)
        # the config resolves `langflow` once at start-up
        self.assertRegex(block, r"depends_on:\s*\n\s*-\s*langflow")

    def test_named_volumes(self):
        self.assertIn("langflow_home:/app/data", service_block("langflow"))
        for volume in ("langflow_home", "postgres_data", "ollama_models", "caddy_data"):
            self.assertRegex(COMPOSE, rf"(?m)^  {volume}:")

    def test_secrets_come_from_env_not_the_compose_file(self):
        for name in ("LANGFLOW_SUPERUSER_PASSWORD", "LANGFLOW_SECRET_KEY", "POSTGRES_PASSWORD"):
            self.assertIn("${" + name + "}", COMPOSE)


class CaddyfileTest(unittest.TestCase):
    def test_proxies_the_api_host_to_the_internal_nginx(self):
        self.assertRegex(
            CADDYFILE, r"api\.ciel-ai\.web\.id\s*\{\s*reverse_proxy nginx:8080\s*\}"
        )

    def test_does_not_trust_client_forwarded_for(self):
        # nginx rate-limits on X-Forwarded-For; Caddy must overwrite it, not pass it on
        directives = [
            line for line in CADDYFILE.splitlines() if not line.lstrip().startswith("#")
        ]
        self.assertNotIn("trusted_proxies", " ".join(directives))


class EnvExampleTest(unittest.TestCase):
    def test_env_example_has_names_but_no_values(self):
        for line in ENV_EXAMPLE.splitlines():
            if line and not line.startswith("#"):
                name, _, value = line.partition("=")
                self.assertIn(value, ("", "60"))  # GATEWAY_RUN_PER_MINUTE=60 only
        self.assertIn("deploy/vps/.env", GITIGNORE)

    def test_env_example_lists_every_name(self):
        names = {
            line.partition("=")[0]
            for line in ENV_EXAMPLE.splitlines()
            if line and not line.startswith("#")
        }
        self.assertEqual(names, set(ENV_NAMES))

    def test_compose_variables_are_all_in_env_example(self):
        for name in set(re.findall(r"\$\{(\w+)\}", COMPOSE)):
            self.assertIn(name, ENV_EXAMPLE)


class ReadmeTest(unittest.TestCase):
    def test_runbook_covers_the_bring_up(self):
        for text in (
            "ufw allow 22,80,443",
            "python3-requests python3-dotenv",
            "/opt/ciel",
            "python3 tools/render_nginx_gateway.py --env-file deploy/vps/.env",
            "docker compose up -d",
            "docker compose exec nginx nginx -t",
            "docker compose restart nginx",
            "pathlib.Path.home()",
            "/app/data",
            "nomic-embed-text-v2-moe:latest",
            "qwen2.5vl:3b",
            "ollama list",
            "ssh -L 7860:127.0.0.1:7860",
            'curl -u "$NGROK_USER:$NGROK_PASSWORD" https://api.ciel-ai.web.id/health_check',
            "Backups and scheduled jobs",
            "Rollback",
        ):
            self.assertIn(text, README)


class LineEndingsTest(unittest.TestCase):
    def test_deploy_files_use_unix_line_endings(self):
        # they are read on Linux
        for path in (VPS / "docker-compose.yml", VPS / "Caddyfile", VPS / ".env.example"):
            self.assertNotIn(b"\r", path.read_bytes(), path.name)


if __name__ == "__main__":
    unittest.main()
