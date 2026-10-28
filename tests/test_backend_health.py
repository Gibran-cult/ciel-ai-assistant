import io
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import check_deepseek_balance  # noqa: E402
from check_deepseek_balance import balance_ok  # noqa: E402

WORKFLOW = (ROOT / ".github" / "workflows" / "backend-health.yml").read_text(encoding="utf-8")
KEY = "sk-test-123"


def payload(*infos, available=True):
    return {"is_available": available, "balance_infos": list(infos)}


def usd(total):
    return {"currency": "USD", "total_balance": total, "granted_balance": "0.00", "topped_up_balance": total}


def run_main(argv=None, response=None, error=None):
    """Run main() with the network mocked and no .env; return (exit code, output)."""
    out, err = io.StringIO(), io.StringIO()
    get = MagicMock(side_effect=error) if error else MagicMock(return_value=response)
    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": KEY}), \
            patch.object(check_deepseek_balance, "load_settings", lambda env_file: dict(os.environ)), \
            patch.object(check_deepseek_balance.requests, "get", get), \
            redirect_stdout(out), redirect_stderr(err):
        code = check_deepseek_balance.main(argv or [])
    return code, out.getvalue() + err.getvalue(), get


def fake_response(status, body=None):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = body if body is not None else {}
    return response


class BalanceOkTests(unittest.TestCase):
    def test_healthy_balance(self):
        self.assertEqual(balance_ok(payload(usd("7.50")), 3.0)[0], True)

    def test_balance_exactly_at_the_minimum_passes(self):
        self.assertTrue(balance_ok(payload(usd("3.00")), 3.0)[0])

    def test_low_balance_fails(self):
        ok, message = balance_ok(payload(usd("2.99")), 3.0)
        self.assertFalse(ok)
        self.assertIn("2.99", message)

    def test_unavailable_account_fails(self):
        self.assertFalse(balance_ok(payload(available=False), 3.0)[0])

    def test_missing_usd_names_the_currencies(self):
        ok, message = balance_ok(payload({"currency": "CNY", "total_balance": "50"}), 3.0)
        self.assertFalse(ok)
        self.assertIn("CNY", message)

    def test_empty_balance_infos_fails(self):
        self.assertFalse(balance_ok(payload(), 3.0)[0])

    def test_unreadable_balance_fails(self):
        self.assertFalse(balance_ok(payload(usd("abc")), 3.0)[0])

    def test_non_finite_balance_is_unreadable(self):
        # float() accepts these; nan < min is False, so nan would otherwise pass
        for raw in ("nan", "NaN", "inf", "-inf", "Infinity"):
            ok, message = balance_ok(payload(usd(raw)), 3.0)
            self.assertFalse(ok, raw)
            self.assertIn("tidak terbaca", message, raw)


class CliTests(unittest.TestCase):
    def test_healthy_balance_exits_0(self):
        code, output, get = run_main(response=fake_response(200, payload(usd("7.50"))))
        self.assertEqual(code, 0)
        self.assertIn("7.50", output)
        self.assertEqual(get.call_args.args[0], "https://api.deepseek.com/user/balance")
        self.assertEqual(get.call_args.kwargs["headers"], {"Authorization": f"Bearer {KEY}"})
        self.assertIn("timeout", get.call_args.kwargs)

    def test_low_balance_exits_1(self):
        code, _, _ = run_main(response=fake_response(200, payload(usd("1.00"))))
        self.assertEqual(code, 1)

    def test_min_usd_flag_is_used(self):
        code, _, _ = run_main(["--min-usd", "10"], response=fake_response(200, payload(usd("7.50"))))
        self.assertEqual(code, 1)

    def test_non_200_exits_1_without_printing_the_key(self):
        code, output, _ = run_main(response=fake_response(401))
        self.assertEqual(code, 1)
        self.assertIn("401", output)
        self.assertNotIn(KEY, output)

    def test_network_error_exits_1_without_printing_the_key(self):
        code, output, _ = run_main(error=requests.exceptions.ConnectionError(f"failed for Bearer {KEY}"))
        self.assertEqual(code, 1)
        self.assertNotIn(KEY, output)

    def test_missing_key_exits_1(self):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(check_deepseek_balance, "load_settings", lambda env_file: {}), \
                patch.object(check_deepseek_balance.requests, "get") as get, \
                redirect_stdout(out), redirect_stderr(err):
            code = check_deepseek_balance.main([])
        self.assertEqual(code, 1)
        get.assert_not_called()


class WorkflowTests(unittest.TestCase):
    def test_workflow_is_gated_pinned_and_read_only(self):
        self.assertIn("vars.BACKEND_HEALTH_ENABLED == 'true'", WORKFLOW)
        self.assertIn("contents: read", WORKFLOW)
        self.assertNotRegex(WORKFLOW, r"uses: [^@]+@v\d")  # SHAs, not tags
        self.assertIn("python tools/check_gateway.py", WORKFLOW)
        self.assertIn("python tools/check_deepseek_balance.py", WORKFLOW)

    def test_balance_is_checked_even_when_the_gateway_probe_failed(self):
        # a down backend must not hide a low balance; the job still fails if either fails
        gateway = WORKFLOW.index("- name: Probe the gateway")
        balance = WORKFLOW.index("- name: Check the DeepSeek balance")
        self.assertLess(gateway, balance)
        step = WORKFLOW[balance:]
        self.assertIn("if: ${{ !cancelled() }}", step)
        self.assertNotIn("continue-on-error", WORKFLOW)
        self.assertNotIn("if:", WORKFLOW[gateway:balance])

    def test_workflow_runs_every_half_hour_and_by_hand(self):
        self.assertIn("cron: '7,37 * * * *'", WORKFLOW)
        self.assertIn("workflow_dispatch:", WORKFLOW)

    def test_secrets_are_mapped_through_env_not_run_text(self):
        for name in ("BACKEND_URL", "BACKEND_USER", "BACKEND_PASSWORD", "FLOW_ID", "MEMORY_ADMIN_FLOW_ID", "DEEPSEEK_API_KEY"):
            self.assertIn(f"secrets.{name}", WORKFLOW)
        for line in WORKFLOW.splitlines():
            if line.strip().startswith("run:"):
                self.assertNotIn("secrets.", line)


if __name__ == "__main__":
    unittest.main()
