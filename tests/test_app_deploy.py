import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "deploy" / "app"


def read(path):
    return path.read_text(encoding="utf-8")


DOCKERFILE = read(APP / "Dockerfile")
COMPOSE = read(APP / "docker-compose.yml")
CADDYFILE = read(APP / "caddy" / "Caddyfile")
ENV_EXAMPLE = read(APP / ".env.example")
UPDATE = read(APP / "update.sh")
README = read(APP / "README.md")
DOCKERIGNORE = read(ROOT / ".dockerignore")
GITIGNORE = read(ROOT / ".gitignore")
CI = read(ROOT / ".github" / "workflows" / "ci.yml")


def code_lines(text):
    return [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")]


class DockerfileTest(unittest.TestCase):
    def test_image_is_pinned_and_installs_from_the_lockfile(self):
        self.assertRegex(DOCKERFILE, r"FROM python:3\.14\.\d+-slim-bookworm")
        self.assertIn("pip install --no-cache-dir --require-hashes -r requirements.txt", DOCKERFILE)

    def test_app_runs_as_non_root_on_8501(self):
        self.assertRegex(DOCKERFILE, r"\nUSER \w+")
        for flag in ("--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"):
            self.assertIn(flag, DOCKERFILE)

    def test_local_secrets_never_enter_the_image(self):
        # The build context is the repository root, where a developer may
        # have a real .streamlit/secrets.toml.
        ignored = set(code_lines(DOCKERIGNORE))
        self.assertIn(".streamlit/secrets.toml", ignored)
        self.assertIn("deploy/app/secrets.toml", ignored)
        self.assertIn("deploy/app/.env", ignored)
        self.assertIn("deploy/app/secrets.toml", GITIGNORE)
        self.assertIn("deploy/app/.env", GITIGNORE)

    def test_runtime_files_still_reach_the_image(self):
        # config.toml carries the theme and gatherUsageStats = false; the app
        # reads the logo PNGs from assets/brand. Only exact paths are excluded.
        for line in code_lines(DOCKERIGNORE):
            self.assertFalse(line.startswith((".streamlit", "assets")), line)
            if "*" in line:
                self.assertIn(line, ("**/__pycache__", "**/*.pyc"))
            self.assertNotIn(".toml", line.replace("secrets.toml", ""), line)
            self.assertNotIn(".png", line, line)


class ComposeTest(unittest.TestCase):
    def test_images_are_pinned(self):
        self.assertIn("image: caddy:2.8.4", COMPOSE)
        self.assertIn("dockerfile: deploy/app/Dockerfile", COMPOSE)

    def test_only_caddy_is_public(self):
        # Any port mapping, quoted or not, bound to an address or not.
        ports = re.findall(r"^\s*-\s*\"?([\d.:]+:\d+)\"?\s*$", COMPOSE, re.MULTILINE)
        self.assertEqual(sorted(ports), ["443:443", "80:80"])
        self.assertEqual(COMPOSE.count("ports:"), 1)

    def test_caddy_config_is_a_directory_mount(self):
        # git replaces a changed file with a new inode; a single-file bind
        # mount would keep serving the old Caddyfile after a deploy.
        self.assertIn("./caddy:/etc/caddy:ro", COMPOSE)
        self.assertNotIn("Caddyfile:/etc/caddy/Caddyfile", COMPOSE)

    def test_secrets_file_is_mounted_read_only(self):
        self.assertIn("./secrets.toml:/app/.streamlit/secrets.toml:ro", COMPOSE)

    def test_every_service_restarts_and_logs_are_capped(self):
        self.assertEqual(COMPOSE.count("restart: unless-stopped"), 2)
        self.assertEqual(COMPOSE.count("max-size: 10m"), 2)

    def test_app_has_a_healthcheck(self):
        self.assertIn("/_stcore/health", COMPOSE)

    def test_caddy_gets_the_hosts_from_env_and_refuses_none(self):
        # An empty value would turn the Caddyfile's site block into its
        # global options block.
        self.assertIn("CIEL_APP_HOSTS: ${CIEL_APP_HOSTS:?", COMPOSE)


class CaddyfileTest(unittest.TestCase):
    def test_serves_the_configured_hosts(self):
        self.assertIn("{$CIEL_APP_HOSTS} {", CADDYFILE)
        self.assertIn("reverse_proxy app:8501", CADDYFILE)

    def test_long_research_runs_are_not_cut(self):
        # Riset Skripsi keeps the websocket open up to 420 s.
        self.assertNotIn("timeout", "\n".join(code_lines(CADDYFILE)))

    def test_does_not_trust_client_forwarded_for(self):
        self.assertNotIn("trusted_proxies", CADDYFILE)


class UpdateScriptTest(unittest.TestCase):
    def test_strict_and_one_at_a_time(self):
        self.assertIn("set -euo pipefail", UPDATE)
        self.assertIn("flock -n", UPDATE)

    def test_only_fast_forwards_main(self):
        self.assertIn("git merge --ff-only origin/main", UPDATE)

    def test_restarts_only_after_a_successful_build(self):
        build = UPDATE.index("docker compose build app")
        up = UPDATE.index("docker compose up -d")
        self.assertLess(build, up)

    def test_a_failed_build_is_retried(self):
        # The deployed commit is recorded only after the app is up, so a
        # failed build is tried again on the next run instead of being skipped
        # because HEAD already equals origin/main.
        self.assertLess(UPDATE.index("docker compose up -d"), UPDATE.index('> "$DEPLOYED"'))

    def test_a_failing_commit_is_retried_at_most_hourly(self):
        # A broken dependency install must not re-download everything every
        # two minutes next to the live app.
        self.assertIn("RETRY_MINUTES=60", UPDATE)
        self.assertLess(UPDATE.index('echo "$head" > "$ATTEMPTED"'), UPDATE.index("docker compose build app"))
        self.assertLess(UPDATE.index('> "$DEPLOYED"'), UPDATE.index('rm -f "$ATTEMPTED"'))

    def test_old_images_are_pruned_after_a_deploy(self):
        self.assertLess(UPDATE.index('> "$DEPLOYED"'), UPDATE.index("docker image prune -f"))

    def test_survives_rewriting_itself(self):
        # git merge can replace this file while bash is reading it; a body
        # wrapped in a function is parsed completely before it runs.
        lines = code_lines(UPDATE)
        self.assertEqual(lines[-1], 'main "$@"')
        self.assertIn("main() {", UPDATE)


class EnvExampleTest(unittest.TestCase):
    def test_names_only(self):
        for line in code_lines(ENV_EXAMPLE):
            name, _, value = line.partition("=")
            self.assertEqual(value, "", name)
        self.assertIn("CIEL_APP_HOSTS=", ENV_EXAMPLE)


class ReadmeTest(unittest.TestCase):
    def test_runbook_covers_the_switch_and_rollback(self):
        for item in (
            "https://app.ciel-ai.web.id/oauth2callback",
            "https://next.ciel-ai.web.id/oauth2callback",
            "APP_URL",
            "DNS only",
            "Rollback",
            "update.sh",
        ):
            self.assertIn(item, README)

    def test_runbook_never_touches_the_mayar_webhook(self):
        self.assertIn("mayar-notify", README)
        self.assertNotIn("webhooks/update", README)


class CiTest(unittest.TestCase):
    def test_shell_scripts_are_syntax_checked(self):
        self.assertIn("deploy/app/*.sh", CI)


if __name__ == "__main__":
    unittest.main()
