import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_api.plan import Plan, parse_plan, scope_to_json, widened  # noqa: E402
from guard.risk import Action  # noqa: E402
from guard.scope import TaskScope  # noqa: E402

GOOD = {"steps": ["Buka shopee.co.id", "Cari mouse"], "hosts": ["Shopee.co.id"], "kinds": ["tab_open", "tab_read", "tab_click"]}


class ParsePlanTest(unittest.TestCase):
    def test_good_plan_becomes_a_locked_scope(self):
        plan = parse_plan(GOOD, 500_000)
        self.assertEqual(plan, Plan(
            ("Buka shopee.co.id", "Cari mouse"),
            TaskScope(hosts=frozenset({"shopee.co.id"}), kinds=frozenset({"tab_open", "tab_read", "tab_click"})),
        ))

    def test_hosts_are_optional_and_normalised(self):
        self.assertEqual(parse_plan({"steps": ["Tanya"], "kinds": ["tab_read"]}, 0).scope.hosts, frozenset())
        hosts = parse_plan({**GOOD, "hosts": ["SHOPEE.co.id:443", "shopee.co.id."]}, 0).scope.hosts
        self.assertEqual(hosts, frozenset({"shopee.co.id"}))

    def test_plans_that_ask_for_too_much_are_refused(self):
        changes = (
            {"kinds": ["pay"]}, {"kinds": ["tab_read", "tidak_ada"]}, {"kinds": []}, {"kinds": "tab_read"},
            {"kinds": ["tab_read", 7]}, {"kinds": [["tab_read"]]},
            {"hosts": ["ibank.klikbca.com"]}, {"hosts": ["evil.com/x"]}, {"hosts": "shopee.co.id"}, {"hosts": [None]},
            {"hosts": ["a%d.example" % index for index in range(11)]},
            {"steps": []}, {"steps": ["a"] * 13}, {"steps": ["a" * 201]}, {"steps": [""]}, {"steps": ["  "]}, {"steps": "buka"},
            {"steps": [7]},
            {"spend_cap": 600_000}, {"spend_cap": -1}, {"spend_cap": 1.5}, {"spend_cap": True}, {"spend_cap": "0"},
            {"apps": ["winword"]}, {"folders": ["C:/"]}, {"writable_folders": []}, {"mode": "auto"},
        )

        for change in changes:
            with self.subTest(change=change):
                self.assertIsNone(parse_plan({**GOOD, **change}, 500_000))

        for output in (None, "rencana", [], {}, {"steps": ["a"]}, {"kinds": ["tab_read"]}):
            with self.subTest(output=output):
                self.assertIsNone(parse_plan(output, 500_000))

    def test_spend_cap_needs_a_user_limit(self):
        self.assertEqual(parse_plan({**GOOD, "spend_cap": 300_000}, 500_000).scope.spend_cap, 300_000)
        self.assertEqual(parse_plan({**GOOD, "spend_cap": 500_000}, 500_000).scope.spend_cap, 500_000)

        for per_tx in (0, None, "500000", 500_000.0, True, -1):
            with self.subTest(per_tx=per_tx):
                self.assertIsNone(parse_plan({**GOOD, "spend_cap": 1}, per_tx))
                self.assertEqual(parse_plan(GOOD, per_tx).scope.spend_cap, 0)

    def test_steps_are_trimmed(self):
        self.assertEqual(parse_plan({**GOOD, "steps": ["  Buka toko  "]}, 0).steps, ("Buka toko",))


class WidenedTest(unittest.TestCase):
    def setUp(self):
        self.scope = parse_plan({**GOOD, "spend_cap": 100_000}, 500_000).scope

    def test_adds_only_what_was_asked(self):
        more = widened(self.scope, Action(kind="tab_open", host="Tokopedia.com:443"), "scope_host")
        self.assertEqual(more.hosts, frozenset({"shopee.co.id", "tokopedia.com"}))
        self.assertEqual((more.kinds, more.spend_cap), (self.scope.kinds, 100_000))

        kinds = widened(self.scope, Action(kind="tab_click", host="shopee.co.id", effect="form_submit"), "scope_kind")
        self.assertEqual(kinds.kinds, self.scope.kinds | {"form_submit"})
        self.assertEqual(kinds.hosts, self.scope.hosts)

        typed = widened(self.scope, Action(kind="tab_type", host="shopee.co.id"), "scope_kind")
        self.assertEqual(typed.kinds, self.scope.kinds | {"tab_type"})

    def test_refuses_what_a_user_cannot_approve(self):
        cases = (
            (Action(kind="tab_open", host="evil.com/x"), "scope_host"), (Action(kind="tab_open"), "scope_host"),
            (Action(kind="tab_open", host="ibank.klikbca.com"), "scope_host"),
            (Action(kind="pay"), "scope_kind"), (Action(kind="tidak_ada"), "scope_kind"), (Action(kind=None), "scope_kind"),
            (Action(kind="tab_click", host="shopee.co.id", effect="pay"), "scope_kind"),
            (Action(kind="tab_click", host="shopee.co.id", effect=7), "scope_kind"),
            (Action(kind="ui_click", app="excel"), "scope_app"), (Action(kind="file_write", path="C:/x"), "scope_path"),
            (Action(kind="tab_open", host="tokopedia.com"), "ask_mode"), (Action(kind="tab_open", host="tokopedia.com"), None),
        )

        for action, reason in cases:
            with self.subTest(action=action, reason=reason):
                self.assertIsNone(widened(self.scope, action, reason))


class ScopeJsonTest(unittest.TestCase):
    def test_scope_to_json_is_sorted_and_plain(self):
        self.assertEqual(
            scope_to_json(parse_plan(GOOD, 0).scope),
            {"hosts": ["shopee.co.id"], "kinds": ["tab_click", "tab_open", "tab_read"], "spend_cap": 0},
        )


if __name__ == "__main__":
    unittest.main()
