import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_api.tools import TOOLS, Bound, Control, Observation, Rejected, bind  # noqa: E402
from guard.risk import ACTION_LEVELS, Action, classify  # noqa: E402

PAGE = Observation(True, "page", "isi", "shopee.co.id", {
    1: Control("text", submits=False), 2: Control("password"), 3: Control(submits=True), 4: Control(effect="cart_add"), 5: Control(),
    6: Control(submits=False),
})


def call(tool, **args):
    return {"tool": tool, "args": args}


class BindTest(unittest.TestCase):
    def test_host_comes_from_the_client_not_the_model(self):
        elsewhere = Observation(True, "page", "", "Evil.example:443", {5: Control()})
        bound = bind(call("tab_click", ref=5), elsewhere)
        self.assertEqual(bound.action.host, "evil.example")
        self.assertEqual(bind(call("tab_click", ref=5, host="shopee.co.id"), PAGE), Rejected("tab_click", "bad_args"))
        self.assertEqual(bind(call("tab_read", host="shopee.co.id"), elsewhere), Rejected("tab_read", "bad_args"))

    def test_field_type_submit_and_effect_come_from_the_control(self):
        self.assertEqual(bind(call("tab_type", ref=2, text="x"), PAGE).action.field_type, "password")
        self.assertEqual(bind(call("tab_type", ref=1, text="x"), PAGE).action.field_type, "text")
        self.assertEqual(bind(call("tab_type", ref=5, text="x"), PAGE).action.field_type, "unknown")
        self.assertEqual(bind(call("tab_select", ref=5, value="x"), PAGE).action.field_type, "unknown")
        self.assertIs(bind(call("tab_click", ref=3), PAGE).action.submits, True)
        self.assertIs(bind(call("tab_click", ref=6), PAGE).action.submits, False)
        self.assertEqual(bind(call("tab_click", ref=4), PAGE).action.effect, "cart_add")
        self.assertIsNone(bind(call("tab_click", ref=5), PAGE).action.effect)

    def test_a_control_with_unclear_facts_reads_as_risky(self):
        page = Observation(True, "page", "", "shopee.co.id", {
            1: Control(submits=None), 2: Control(field_type=7), 3: "bukan kontrol", 4: Control(effect=["pay"]),
        })
        self.assertIs(bind(call("tab_click", ref=1), page).action.submits, True)
        self.assertEqual(bind(call("tab_type", ref=2, text="x"), page).action.field_type, "unknown")
        self.assertEqual(bind(call("tab_click", ref=3), page), Rejected("tab_click", "unknown_ref"))
        # Efek yang rusak diteruskan apa adanya: guard yang memblokirnya.
        self.assertEqual(classify(bind(call("tab_click", ref=4), page).action).reason, "unknown_kind")

    def test_an_address_with_a_secret_is_refused(self):
        self.assertEqual(bind(call("tab_open", url="https://shopee.co.id/search?q=4111111111111111"), None), Rejected("tab_open", "secret_text"))
        self.assertEqual(bind(call("tab_open", url="https://shopee.co.id/search?q=mouse"), None).tool, "tab_open")

    def test_typed_text_reaches_the_guard(self):
        bound = bind(call("tab_type", ref=1, text="4111 1111 1111 1111"), PAGE)
        self.assertEqual(bound.action.text, "4111 1111 1111 1111")
        self.assertEqual(classify(bound.action).reason, "secret_text")
        self.assertEqual(bind(call("tab_select", ref=1, value="Merah"), PAGE).action.text, "Merah")

    def test_bound_keeps_the_tool_and_its_arguments(self):
        self.assertEqual(
            bind(call("tab_type", ref=1, text="mouse"), PAGE),
            Bound("tab_type", {"ref": 1, "text": "mouse"},
                  Action(kind="tab_type", host="shopee.co.id", text="mouse", field_type="text")),
        )
        self.assertEqual(bind(call("finish", report="Beres."), None), Bound("finish", {"report": "Beres."}, Action(kind="finish")))
        self.assertEqual(bind(call("ask_user", question="Warna apa?"), None).action, Action(kind="ask_user"))

    def test_open_takes_the_host_from_the_url(self):
        self.assertEqual(
            bind(call("tab_open", url="https://Shopee.co.id/x?y=1"), None).action, Action(kind="tab_open", host="shopee.co.id"),
        )

        for url in ("http://shopee.co.id", "https://evil.com\\.shopee.co.id/", "javascript:alert(1)", "", 7, None,
                    "https://user@shopee.co.id/", "https://203.0.113.7/", "https://xn--shope-9ua.co.id/",
                    "https://shopee.co.id/" + "a" * 2000):
            with self.subTest(url=url):
                self.assertEqual(bind(call("tab_open", url=url), None), Rejected("tab_open", "bad_args"))

    def test_page_tools_need_a_page(self):
        pages = (
            None, Observation(False, "page", "", "shopee.co.id"), Observation(True, "page", "", None),
            Observation(True, "page", "", "evil.com/x"), "bukan pengamatan",
        )

        for page in pages:
            for tool, args in (("tab_read", {}), ("tab_close", {}), ("tab_scroll", {"direction": "down"}),
                               ("tab_click", {"ref": 1}), ("form_submit", {"ref": 1})):
                with self.subTest(page=page, tool=tool):
                    self.assertEqual(bind(call(tool, **args), page), Rejected(tool, "no_page"))

        self.assertEqual(bind(call("tab_click", ref=99), PAGE), Rejected("tab_click", "unknown_ref"))

    def test_broken_calls(self):
        for broken in (None, "bayar", ["pay"], {}, {"tool": "tab_read"}, {"tool": "tab_read", "args": {}, "x": 1},
                       {"tool": 7, "args": {}}, {"tool": None, "args": {}}, {"args": {}}):
            with self.subTest(call=broken):
                self.assertEqual(bind(broken, PAGE).reason, "bad_call")

        self.assertEqual(bind("bayar", PAGE).tool, "unknown")

        for tool in ("pay", "shell_run", "file_delete", "cart_add", "tidak_ada", "", "__class__"):
            with self.subTest(tool=tool):
                self.assertEqual(bind({"tool": tool, "args": {}}, PAGE).reason, "tool_unavailable")

        # Nama tool masuk ke log yang tidak bisa diubah. Nama karangan model tidak ikut ke sana.
        self.assertEqual(bind({"tool": "pay", "args": {}}, PAGE).tool, "pay")

        for tool in ("4111 1111 1111 1111", "<script>alert(1)</script>", "Pay", "tab_open\n", "a" * 41, "", "pay2"):
            with self.subTest(tool=tool):
                self.assertEqual(bind({"tool": tool, "args": {}}, PAGE), Rejected("unknown", "tool_unavailable"))

    def test_a_control_that_does_not_say_whether_it_submits_counts_as_submitting(self):
        self.assertIs(bind(call("tab_click", ref=5), PAGE).action.submits, True)
        said = Observation(True, "page", "", "shopee.co.id", {5: Control(submits=False)})
        self.assertIs(bind(call("tab_click", ref=5), said).action.submits, False)

        for broken in (call("tab_click", ref=True), call("tab_click", ref="5"), call("tab_click"), call("tab_click", ref=1.0),
                       call("tab_scroll", direction="left"), call("finish", report=""), call("finish", report="a" * 2001),
                       call("ask_user", question="a" * 501), {"tool": "tab_read", "args": []}, {"tool": "tab_read", "args": None},
                       call("tab_type", ref=1), call("tab_type", ref=1, text=""), call("tab_type", ref=1, text="a" * 2001),
                       call("tab_select", ref=1, value="a" * 201), call("tab_read", extra=1)):
            with self.subTest(call=broken):
                self.assertEqual(bind(broken, PAGE).reason, "bad_args")

    def test_long_unknown_tool_names_are_cut_for_the_log(self):
        self.assertLessEqual(len(bind({"tool": "x" * 500, "args": {}}, PAGE).tool), 40)

    def test_every_tool_is_a_known_action_kind_below_r3(self):
        for tool in TOOLS:
            self.assertIn(ACTION_LEVELS[tool], ("R0", "R1", "R2"))


if __name__ == "__main__":
    unittest.main()
