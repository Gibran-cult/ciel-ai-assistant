import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import wake_streamlit  # noqa: E402  (must import without Playwright installed)


class FakeFrame:
    def __init__(self, has_app):
        self.has_app = has_app

    def query_selector(self, selector):
        return object() if self.has_app and selector == wake_streamlit.APP_SELECTOR else None


class FakePage:
    def __init__(self, *frames):
        self.frames = list(frames)


class WakeStreamlitTest(unittest.TestCase):
    def test_app_found_in_any_frame(self):
        # Community Cloud renders the app inside an iframe of the share page.
        self.assertTrue(wake_streamlit.app_rendered(FakePage(FakeFrame(False), FakeFrame(True))))
        self.assertFalse(wake_streamlit.app_rendered(FakePage(FakeFrame(False))))

    def test_url_is_required(self):
        with self.assertRaises(SystemExit):
            wake_streamlit.main([])


class KeepAwakeWorkflowTest(unittest.TestCase):
    workflow = (ROOT / ".github" / "workflows" / "keep-awake.yml").read_text(encoding="utf-8")

    def test_runs_well_inside_the_12_hour_sleep_window(self):
        cron = re.search(r"cron:\s*'([^']+)'", self.workflow).group(1)
        hours = cron.split()[1]
        step = int(hours.split("/")[1]) if "/" in hours else 24
        self.assertLessEqual(step, 6, cron)

    def test_url_comes_from_a_variable_through_env(self):
        # No hard-coded app URL, and no ${{ }} expansion inside the shell line.
        self.assertIn("vars.STREAMLIT_APP_URL", self.workflow)
        run_lines = [line for line in self.workflow.splitlines() if line.strip().startswith("run: python tools/wake")]
        self.assertEqual(len(run_lines), 1)
        self.assertNotIn("${{", run_lines[0])
        self.assertNotIn("streamlit.app", self.workflow.replace("<your-app>.streamlit.app", ""))


class WatchdogScriptTest(unittest.TestCase):
    script = (ROOT / "tools" / "ciel_watchdog.ps1").read_text(encoding="utf-8")

    def test_tunnel_always_starts_with_the_traffic_policy(self):
        self.assertIn("--traffic-policy-file", self.script)
        self.assertIn("not starting an unprotected tunnel", self.script)
        self.assertIn("-eq 401", self.script)

    def test_unstoppable_agent_is_reported_instead_of_starting_a_second_one(self):
        # An ngrok started as administrator cannot be stopped by the task, and a
        # second agent cannot bind the same static domain.
        block = self.script.split("foreach ($agent in $stale)", 1)[1].split("Start-Process -FilePath 'ngrok'", 1)[0]
        self.assertIn("-ErrorAction Stop", block)
        self.assertIn("return $false", block)
        self.assertNotIn("SilentlyContinue", block.split("Start-Sleep", 1)[0])

    def test_langflow_boot_window_is_longer_than_a_boot_and_fits_the_task_limit(self):
        # Desktop needs about 5 minutes to a healthy backend; a shorter window
        # restarts it mid-boot. Two waits plus ngrok must fit the 15-minute limit.
        grace = int(re.search(r"\$LangflowGraceSeconds = (\d+)", self.script).group(1))
        limit = int(re.search(r"ExecutionTimeLimit \(New-TimeSpan -Minutes (\d+)\)", self.script).group(1))
        self.assertGreaterEqual(grace, 480)
        self.assertLess(grace + 60 + 60, limit * 60)
        # The window counts from when Desktop's processes were created, not from this run.
        self.assertIn("CreationDate", self.script)

    def test_desktop_without_a_backend_is_restarted_before_the_full_window(self):
        # Desktop does not respawn a dead backend; waiting the full window would
        # only add downtime. It spawned one 42 s to 2 min 42 s after launch.
        spawn = int(re.search(r"\$BackendSpawnSeconds = (\d+)", self.script).group(1))
        grace = int(re.search(r"\$LangflowGraceSeconds = (\d+)", self.script).group(1))
        self.assertGreaterEqual(spawn, 200)
        self.assertLess(spawn, grace)
        self.assertIn("$backend.Count -eq 0 -and $age -ge $BackendSpawnSeconds", self.script)

    def test_no_tunnel_url_or_credentials_in_the_script(self):
        self.assertNotRegex(self.script, r"https://[a-z0-9-]+\.ngrok")
        self.assertNotRegex(self.script, r"credentials:")


if __name__ == "__main__":
    unittest.main()
