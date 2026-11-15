import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_api.limits import (  # noqa: E402
    MAX_REPAIRS, MAX_SECONDS, MAX_STEPS, AgentConfig, day_start, load_config, over_limit, start_refusal, task_rate_limits,
)

ON = AgentConfig(True, 1000, {"free": 2, "pro": 20})
ALICE = "a1b2c3d4e5f60718"


class ConfigTest(unittest.TestCase):
    def test_spec_numbers(self):
        self.assertEqual((MAX_STEPS, MAX_SECONDS, MAX_REPAIRS), (40, 900, 2))

    def test_agent_is_off_unless_configured(self):
        self.assertEqual(load_config({}), AgentConfig())
        self.assertEqual(AgentConfig(), AgentConfig(False, 0, {}))

        for value in ("true", "yes", "0", "", " 1", "1 ", "on"):
            with self.subTest(value=value):
                self.assertIs(load_config({"AGENT_ENABLED": value}).enabled, False)

        env = {"AGENT_ENABLED": "1", "AGENT_DAILY_COST_CAP": "1000", "AGENT_TASKS_PER_DAY_FREE": "2", "AGENT_TASKS_PER_DAY_PRO": "x"}
        self.assertEqual(load_config(env), AgentConfig(True, 1000, {"free": 2, "pro": 0}))

        for value in ("-5", "1.5", "seribu", "", "1e3"):
            with self.subTest(value=value):
                self.assertEqual(load_config({"AGENT_DAILY_COST_CAP": value}).daily_cost_cap, 0)

    def test_start_refusal_order(self):
        self.assertEqual(start_refusal(AgentConfig(), "pro", 0), "agent_off")
        self.assertEqual(start_refusal(AgentConfig("1", 1000, {"pro": 5}), "pro", 0), "agent_off")
        self.assertEqual(start_refusal(AgentConfig(True, 0, {"pro": 5}), "pro", 0), "cost_cap")

        for cost in (1000, 5000, None, "0", -1, 1.0, True):
            with self.subTest(cost=cost):
                self.assertEqual(start_refusal(ON, "pro", cost), "cost_cap")

        self.assertEqual(start_refusal(ON, "tamu", 0), "no_quota")
        self.assertEqual(start_refusal(ON, None, 0), "no_quota")
        self.assertEqual(start_refusal(AgentConfig(True, 1000, {"free": 0}), "free", 0), "no_quota")
        self.assertEqual(start_refusal(AgentConfig(True, 1000, {"free": True}), "free", 0), "no_quota")
        self.assertIsNone(start_refusal(ON, "free", 999))
        self.assertIsNone(start_refusal(ON, "pro", 0))

    def test_task_rate_limits(self):
        self.assertEqual(task_rate_limits(ALICE, "pro", ON), {"agent:" + ALICE: (20, 86400)})
        self.assertEqual(task_rate_limits(ALICE, "free", ON), {"agent:" + ALICE: (2, 86400)})


class ClockTest(unittest.TestCase):
    def test_day_start_is_midnight_in_jakarta(self):
        self.assertEqual(day_start(datetime(2026, 11, 15, 18, 30, tzinfo=timezone.utc)), "2026-11-16T00:00:00+07:00")
        self.assertEqual(day_start(datetime(2026, 11, 15, 16, 59, tzinfo=timezone.utc)), "2026-11-15T00:00:00+07:00")
        self.assertEqual(day_start(datetime(2026, 11, 15, 17, 0, 0, 5, tzinfo=timezone.utc)), "2026-11-16T00:00:00+07:00")

    def test_over_limit(self):
        start = datetime(2026, 11, 15, tzinfo=timezone.utc)
        self.assertIsNone(over_limit(39, start, start + timedelta(seconds=900), 2))
        self.assertEqual(over_limit(40, start, start, 0), "limit_steps")
        self.assertEqual(over_limit(0, start, start + timedelta(seconds=901), 0), "limit_time")
        self.assertEqual(over_limit(0, start, start, 3), "stuck")
        self.assertEqual(over_limit(40, start, start + timedelta(hours=1), 9), "limit_steps")


if __name__ == "__main__":
    unittest.main()
