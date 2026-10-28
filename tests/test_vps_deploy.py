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
LINK_CHECK = read(VPS / "ollama_link_check.sh")
README = read(VPS / "README.md")
BACKUP = read(VPS / "backup.sh")
RESTORE = read(VPS / "restore_check.sh")
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
    "OLLAMA_EMBED_MODEL_ID",
)

# Every Streamlit secret that changes between the laptop and the VPS backend
SWITCHED_SECRETS = (
    "NGROK_URL",
    "NGROK_PASSWORD",
    "NGROK_USER",
    "LANGFLOW_API_KEY",
    "FLOW_ID",
    "RESEARCH_FLOW_ID",
    "WRITER_FLOW_ID",
    "MEMORY_ADMIN_FLOW_ID",
)


def readme_section(heading):
    """README text from `heading` (a line start such as "## 10.") to the next heading
    of the same or a higher level."""
    depth = len(heading.split(" ", 1)[0])
    lines = README[README.index("\n" + heading) + 1 :].split("\n")
    in_fence = False
    for number, line in enumerate(lines[1:], start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence  # "# comment" lines in code blocks are not headings
        elif not in_fence and re.match(rf"#{{1,{depth}}} ", line):
            return "\n".join(lines[:number])
    return "\n".join(lines)


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
        # TCP, not the socket: during first init the temporary server listens on the socket only
        self.assertIn(
            '["CMD", "pg_isready", "-h", "127.0.0.1", "-U", "langflow", "-d", "langflow"]',
            service_block("postgres"),
        )

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

    def test_ollama_restarts_when_langflow_restarts(self):
        # it lives in langflow's network namespace, which a langflow restart replaces
        self.assertRegex(
            service_block("ollama"),
            r"depends_on:\n\s+langflow:\n\s+condition: service_started\n\s+restart: true",
        )

    def test_every_service_restarts(self):
        self.assertEqual(COMPOSE.count("restart: unless-stopped"), 5)
        for name in SERVICES:
            self.assertIn("restart: unless-stopped", service_block(name))

    def test_nginx_mounts_the_generated_gateway_files(self):
        block = service_block("nginx")
        self.assertIn("./nginx/ciel.conf:/etc/nginx/conf.d/default.conf:ro", block)
        self.assertIn("./nginx/ciel.htpasswd:/etc/nginx/ciel.htpasswd:ro", block)
        # nginx starts after langflow (it re-resolves the address later, see the renderer)
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


class RunbookTest(unittest.TestCase):
    def test_api_record_is_ipv4_only_and_the_clock_is_utc(self):
        # Docker's userland proxy would merge IPv6 clients into one rate-limit key
        requirements = readme_section("## 1.")
        self.assertIn("A record only", requirements)
        self.assertIn("no AAAA", requirements)
        self.assertIn("timedatectl set-timezone UTC", readme_section("## 2."))  # cron times are UTC

    def test_secrets_are_generated_without_special_characters(self):
        step = readme_section("## 5.")
        self.assertIn("openssl rand -hex 32", step)
        for name in ("POSTGRES_PASSWORD", "LANGFLOW_SECRET_KEY", "NGROK_PASSWORD", "RESTIC_PASSWORD"):
            self.assertIn(name, step)
        self.assertIn("$ @ # : / %", step)
        self.assertIn("SUPABASE_DB_URL='", step)  # values that need them are single-quoted
        self.assertNotIn("kept those IDs", README)  # the migration creates new IDs

    def test_env_file_is_the_renderers_source_of_truth(self):
        self.assertIn("source of truth", readme_section("## 6."))

    def test_nginx_follows_langflows_address_and_the_vps_check_proves_it(self):
        self.assertNotIn("keeps the address", README)
        self.assertNotIn("resolves `langflow` once", README)
        check = readme_section("### When Langflow restarts")
        self.assertIn("`resolve`", check)
        inspect = "docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}'"
        self.assertEqual(check.count(inspect), 2)  # before and after
        restart = check.index("docker compose restart langflow\n")
        self.assertLess(check.index(inspect), restart)
        self.assertLess(restart, check.rindex(inspect))
        health = check.index("https://api.ciel-ai.web.id/health_check   # 200")
        self.assertLess(check.rindex(inspect), health)

    def test_embedding_model_id_is_recorded_and_compared(self):
        step = readme_section("## 8.")
        self.assertIn("OLLAMA_EMBED_MODEL_ID", step)
        self.assertIn('$1 == "nomic-embed-text-v2-moe:latest"', step)
        self.assertIn("after any restore", step)

    def test_flows_are_migrated_with_the_tool_and_the_gateway_re_rendered(self):
        step = readme_section("## 10.")
        tunnel = step.index("ssh -L 17860:127.0.0.1:7860")
        migrate = step.index("python tools/migrate_flows.py")
        self.assertLess(tunnel, migrate)
        self.assertIn("--source-url http://127.0.0.1:7860 --target-url http://127.0.0.1:17860", step)
        for name in ("FLOW_ID", "RESEARCH_FLOW_ID", "WRITER_FLOW_ID", "MEMORY_ADMIN_FLOW_ID"):
            self.assertIn(f"--flow-id <{name}>", step)
        for text in ("--map-out", "--snapshot-dir flow/subflows", "SOURCE_LANGFLOW_API_KEY", "TARGET_LANGFLOW_API_KEY"):
            self.assertIn(text, step)
        render = step.index("python3 tools/render_nginx_gateway.py --env-file deploy/vps/.env")
        self.assertLess(migrate, render)
        self.assertLess(render, step.index("docker compose restart nginx"))
        self.assertNotIn("import the flows", step)

    def test_cutover_and_rollback_switch_every_secret(self):
        cutover = readme_section("## 12.")
        cutover = cutover[: cutover.index("### Alerts")]
        rollback = readme_section("## Rollback")
        for name in SWITCHED_SECRETS:
            self.assertIn(f"`{name}`", cutover, name)
            self.assertIn(f"`{name}`", rollback, name)

    def test_alerts_are_configured_secrets_first_then_enabled_then_run(self):
        alerts = readme_section("### Alerts")
        for name in ("BACKEND_URL", "BACKEND_USER", "BACKEND_PASSWORD", "FLOW_ID", "MEMORY_ADMIN_FLOW_ID", "DEEPSEEK_API_KEY"):
            self.assertIn(f"`{name}`", alerts, name)
        enabled = alerts.index("`BACKEND_HEALTH_ENABLED` = `true`")
        self.assertLess(alerts.index("`DEEPSEEK_API_KEY`"), enabled)
        self.assertLess(enabled, alerts.index("Run workflow"))
        self.assertIn("60 days", alerts)

    def test_rollback_is_self_contained_and_copies_memories_back(self):
        rollback = readme_section("## Rollback")
        self.assertNotIn("keep-alive notes", rollback)
        self.assertIn("Enable-ScheduledTask -TaskName 'Ciel backend watchdog'", rollback)
        for text in ("com.docker.compose.volume=langflow_home", "long_term_memory", "user_datasets"):
            self.assertIn(text, rollback)
        # memories are copied while the laptop's Langflow is still stopped
        self.assertLess(rollback.index("long_term_memory"), rollback.index("Enable-ScheduledTask"))

    def test_backups_wait_for_the_privacy_notice(self):
        section = readme_section("## 11.")
        precondition = section.index(
            "The production privacy page must already show the backup notice\n"
            "(privacy.py change merged and deployed)."
        )
        self.assertLess(precondition, section.index("./backup.sh"))
        self.assertLess(precondition, section.index("30 20 * * *"))

    def test_manual_run_sources_env_and_tries_supabase_first(self):
        section = readme_section("## 11.")
        manual = section.index("set -a; . ./.env; set +a\ndocker run")
        supabase = section.index('docker run --rm --network host postgres:17.2 pg_dump -Fc "$SUPABASE_DB_URL" > /dev/null')
        self.assertLess(manual, supabase)
        self.assertLess(supabase, section.index("./backup.sh\n"))
        self.assertLess(supabase, section.index("30 20 * * *"))
        self.assertIn("--schema=public", section)


class OllamaLinkCheckTest(unittest.TestCase):
    def test_script_is_strict_and_probes_then_restarts_ollama(self):
        self.assertIn("set -euo pipefail", LINK_CHECK)
        self.assertIn("docker compose exec -T langflow python -c", LINK_CHECK)
        self.assertIn("127.0.0.1:11434", LINK_CHECK)
        self.assertIn("docker compose restart ollama", LINK_CHECK)
        self.assertIn("date -u", LINK_CHECK)

    def test_does_nothing_unless_langflow_is_running(self):
        # paused for the backup, stopped or restarting: the probe would fail and
        # restart Ollama every minute for nothing
        state = LINK_CHECK.index("docker compose ps -a -q langflow")
        self.assertIn("docker inspect -f '{{.State.Status}}'", LINK_CHECK)
        self.assertIn("!= running ]; then\n  exit 0\nfi", LINK_CHECK)
        self.assertLess(state, LINK_CHECK.index("docker compose exec -T langflow"))
        self.assertLess(LINK_CHECK.index("exit 0"), LINK_CHECK.index("docker compose restart ollama"))

    def test_readme_schedules_it_every_minute_outside_the_backup_section(self):
        cron = (
            "* * * * * cd /opt/ciel/deploy/vps && ./ollama_link_check.sh"
            " >> /var/log/ciel/ollama_link_check.log 2>&1"
        )
        self.assertIn(cron, README)
        placeholder = README.index("Backups and scheduled jobs")
        next_section = README.index("\n## ", placeholder)
        self.assertNotIn(cron, README[placeholder:next_section])  # Task 5 replaces that section

    def test_readme_does_not_say_a_langflow_restart_needs_nothing(self):
        self.assertNotIn("needs nothing", README)
        self.assertIn("docker compose restart langflow ollama", README)


class SecretsBackupNoteTest(unittest.TestCase):
    def test_readme_asks_for_the_keys_in_a_password_manager(self):
        paragraphs = [p for p in README.split("\n\n") if "password manager" in p]
        self.assertTrue(
            any("LANGFLOW_SECRET_KEY" in p and "RESTIC_PASSWORD" in p for p in paragraphs)
        )


class BackupTest(unittest.TestCase):
    def test_backup_pauses_langflow_safely(self):
        trap = BACKUP.index("trap cleanup EXIT")
        self.assertLess(trap, BACKUP.index("docker compose pause langflow"))
        cleanup = BACKUP[BACKUP.index("cleanup() {") : trap]
        self.assertIn("docker compose unpause langflow", cleanup)
        self.assertLess(BACKUP.index("paused=1"), BACKUP.index("docker compose pause langflow"))
        # the explicit unpause marks it, so the EXIT trap does not unpause twice
        self.assertIn("\ndocker compose unpause langflow\npaused=0\n", BACKUP)

    def test_backup_never_leaves_dumps_behind(self):
        # one EXIT trap (every exit path) removes the work dir; signals exit through it
        cleanup = BACKUP[BACKUP.index("cleanup() {") : BACKUP.index("trap cleanup EXIT")]
        self.assertIn('rm -rf "$WORK"', cleanup)
        self.assertRegex(BACKUP, r"trap 'exit 1' INT TERM HUP")
        self.assertNotIn(" ERR", BACKUP)  # an ERR trap is bypassed by exit, set -u and signals
        # trap is installed before the dumps and before the work dir exists
        self.assertLess(BACKUP.index("trap cleanup EXIT"), BACKUP.index('mkdir -m 700 "$WORK"'))
        self.assertLess(BACKUP.index('mkdir -m 700 "$WORK"'), BACKUP.index("pg_dump"))

    def test_backup_validates_settings_before_dumping(self):
        first_dump = BACKUP.index("pg_dump")
        for name in (
            "SUPABASE_DB_URL",
            "RESTIC_REPOSITORY",
            "RESTIC_PASSWORD",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "HEALTHCHECKS_BACKUP_URL",
        ):
            check = "${" + name + ":?}"
            self.assertIn(check, BACKUP)
            self.assertLess(BACKUP.index(check), first_dump, name)
        # and the volume lookup, which can exit 1, comes before the dumps too
        self.assertLess(BACKUP.index("docker volume inspect"), first_dump)

    def test_backup_removes_a_leftover_work_dir_before_the_disk_check(self):
        leftover = BACKUP.index('rm -rf "$WORK"')
        self.assertLess(leftover, BACKUP.index("df --output=pcent /"))

    def test_backup_runs_one_at_a_time(self):
        lock = BACKUP.index("exec 9>/var/lock/ciel-backup.lock")
        self.assertIn("if ! flock -n 9; then", BACKUP)
        # before anything that touches the work dir of a run still in progress
        self.assertLess(lock, BACKUP.index('rm -rf "$WORK"'))
        branch = BACKUP[BACKUP.index("if ! flock -n 9; then") : BACKUP.index("fi", lock)]
        self.assertIn("exit 1", branch)
        self.assertNotIn("HEALTHCHECKS", branch)

    def test_paused_snapshot_has_a_time_limit(self):
        pause = BACKUP.index("docker compose pause langflow")
        limited = BACKUP.index('timeout 45m restic backup "$mountpoint" "$WORK"')
        self.assertLess(pause, limited)
        self.assertLess(limited, BACKUP.index("\ndocker compose unpause langflow\npaused=0\n"))
        self.assertLess(BACKUP.index("trap cleanup EXIT"), pause)  # a timeout still unpauses

    def test_backup_keeps_about_five_weeks(self):
        self.assertIn("restic forget --keep-daily 7 --keep-weekly 4 --prune", BACKUP)
        self.assertNotIn("--keep-monthly", BACKUP)

    def test_backup_includes_supabase_and_langflow_db(self):
        self.assertIn('pg_dump -Fc "$SUPABASE_DB_URL"', BACKUP)
        self.assertIn("pg_dump -U langflow -Fc langflow", BACKUP)
        # Supabase's direct host is IPv6-only and Docker has no IPv6 by default
        self.assertIn("docker run --rm --network host postgres:17.2 pg_dump", BACKUP)

    def test_success_ping_is_last_and_disk_check_is_first(self):
        lines = [l for l in BACKUP.splitlines() if l.strip() and not l.lstrip().startswith("#")]
        self.assertIn("HEALTHCHECKS_BACKUP_URL", lines[-1])
        self.assertLess(BACKUP.index("df --output=pcent /"), BACKUP.index("pg_dump"))

    def test_backup_finds_the_langflow_volume_from_the_compose_labels(self):
        self.assertIn("com.docker.compose.volume=langflow_home", BACKUP)
        self.assertIn("com.docker.compose.project=", BACKUP)
        self.assertIn("docker volume inspect", BACKUP)

    def test_backup_snapshots_use_one_fixed_work_path(self):
        # restic forget groups by host and paths: a random temp dir would make
        # every night its own group and nothing would ever be pruned
        self.assertNotIn("mktemp", BACKUP)

    def test_restore_check_fails_on_empty_memory(self):
        self.assertIn("chromadb.PersistentClient", RESTORE)
        self.assertIn("HEALTHCHECKS_RESTORE_URL", RESTORE)
        self.assertIn("langflowai/langflow:1.12.4", RESTORE)
        self.assertIn("--entrypoint python", RESTORE)
        self.assertIn("restic restore latest --target", RESTORE)
        self.assertIn("pg_restore --list", RESTORE)
        self.assertIn("*[!0-9]*", RESTORE)  # a non-numeric count fails the check
        # the snapshot size, the free space, the memory count and each dump
        self.assertEqual(RESTORE.count("require_positive_count "), 4)
        self.assertNotIn("-lt 1", RESTORE)  # `[ x -lt 1 ]` passes when x is not a number
        self.assertIn("for name in langflow supabase", RESTORE)  # both dumps

    def test_restore_check_runs_one_at_a_time(self):
        lock = RESTORE.index("exec 9>/var/lock/ciel-restore.lock")
        self.assertIn("if ! flock -n 9; then", RESTORE)
        self.assertLess(lock, RESTORE.index("mktemp -d"))
        self.assertLess(lock, RESTORE.index("restic restore latest"))

    def test_restore_check_needs_twice_the_snapshot_size_free(self):
        stats = RESTORE.index("restic stats latest --mode restore-size --json")
        free = RESTORE.index("df --output=avail -B1 /var/tmp")
        check = RESTORE.index('if [ "$free" -lt $((2 * need)) ]; then')
        restore = RESTORE.index("restic restore latest")
        self.assertLess(stats, check)
        self.assertLess(free, check)
        self.assertLess(check, restore)
        self.assertLess(check, RESTORE.index("mktemp -d"))

    def test_scripts_are_strict(self):
        for text in (BACKUP, RESTORE):
            self.assertIn("set -euo pipefail", text)

    def test_readme_schedules_the_three_jobs(self):
        start = README.index("## 11. Backups and scheduled jobs")
        section = README[start : README.index("\n## ", start + 1)]
        source = "set -a; . /opt/ciel/deploy/vps/.env; set +a;"
        for line in (
            f"30 20 * * * {source} cd /opt/ciel/deploy/vps && ./backup.sh"
            " >> /var/log/ciel/backup.log 2>&1",
            f"0 21 1 * * {source} cd /opt/ciel/deploy/vps && ./restore_check.sh"
            " >> /var/log/ciel/restore_check.log 2>&1",
            f"0 20 * * * {source} python3 /opt/ciel/tools/prune_chat_history.py"
            " --days 30 --base-url http://127.0.0.1:7860"
            " >> /var/log/ciel/prune_chat_history.log 2>&1",
        ):
            self.assertIn(line, section)
        self.assertIn("restic init", section)
        self.assertIn("Session pooler", section)
        self.assertIn("r2.cloudflarestorage.com", section)


class LineEndingsTest(unittest.TestCase):
    def test_deploy_files_use_unix_line_endings(self):
        # they are read on Linux
        for path in (
            VPS / "docker-compose.yml",
            VPS / "Caddyfile",
            VPS / ".env.example",
            VPS / "ollama_link_check.sh",
            VPS / "backup.sh",
            VPS / "restore_check.sh",
        ):
            self.assertNotIn(b"\r", path.read_bytes(), path.name)


if __name__ == "__main__":
    unittest.main()
