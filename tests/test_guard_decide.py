"""guard/decide.py: satu keputusan per aksi, dalam urutan yang tetap."""

import unittest
from dataclasses import replace

from guard.decide import PURCHASE_KINDS, Context, Decision, decide
from guard.limits import SpendLimits
from guard.risk import ACTION_LEVELS, R3, Action
from guard.scope import TaskScope
from guard.stores import StoreVerdict

SKRIPSI = "C:/Users/nadia/Dokumen/Skripsi"

OFFICIAL = StoreVerdict(
    True, "marketplace", None, "shopee.co.id", None,
    {"store_name": "Toko Contoh", "badge_text": "Shopee Mall", "domain": "shopee.co.id", "checked_at": "2026-11-14T03:42:00+00:00"},
)
REJECTED = StoreVerdict(False, None, "no_official_badge", "shopee.co.id", None, {})

SCOPE = TaskScope(
    hosts=frozenset({"shopee.co.id"}), apps=frozenset({"winword"}),
    writable_folders=(SKRIPSI,),
    kinds=frozenset(kind for kind, level in ACTION_LEVELS.items() if level != R3),
    spend_cap=500_000,
)


def ctx(**kw):
    base = dict(
        stopped=False, ticket_ok=True, mode="auto", scope=SCOPE, adult_verified=True,
        limits=SpendLimits(per_tx=500_000, per_month=1_500_000), spent_this_month=0,
        store=OFFICIAL, purchase_total=261_000,
    )
    base.update(kw)
    return Context(**base)


class DecideTest(unittest.TestCase):
    def test_stop_and_ticket_come_first(self):
        read = Action(kind="tab_read", host="shopee.co.id")
        self.assertEqual(decide(read, ctx(stopped=True)), Decision("block", "R0", "stopped"))
        self.assertEqual(decide(read, ctx(ticket_ok=False)), Decision("block", "R0", "bad_ticket"))
        self.assertEqual(decide(Action(kind="pay"), ctx(stopped=True)), Decision("block", "R3", "stopped"))

    def test_unclear_stop_or_ticket_blocks(self):
        read = Action(kind="tab_read", host="shopee.co.id")
        self.assertEqual(decide(read, ctx(stopped=None)).reason, "stopped")
        self.assertEqual(decide(read, ctx(ticket_ok=None)).reason, "bad_ticket")
        self.assertEqual(decide(read, ctx(ticket_ok="ya")).reason, "bad_ticket")

    def test_r3_is_blocked_or_handed_over(self):
        self.assertEqual(decide(Action(kind="shell_run"), ctx()), Decision("block", "R3", "shell_run"))
        self.assertEqual(decide(Action(kind="format_disk"), ctx()), Decision("block", "R3", "unknown_kind"))
        typing = Action(kind="tab_type", host="shopee.co.id", text="x", field_type="password")
        self.assertEqual(decide(typing, ctx()), Decision("handover", "R3", "secret_field"))
        for kind in ("pay", "captcha_solve", "account_create", "oauth_grant", "terms_accept"):
            self.assertEqual(decide(Action(kind=kind), ctx()).outcome, "handover")

    def test_blocked_targets_and_secret_text_are_blocked(self):
        self.assertEqual(decide(Action(kind="ui_read", app="bitwarden"), ctx()), Decision("block", "R3", "blocked_app"))
        self.assertEqual(decide(Action(kind="tab_read", host="ibank.klikbca.com"), ctx()), Decision("block", "R3", "blocked_host"))
        card = Action(kind="tab_type", host="shopee.co.id", text="4111 1111 1111 1111")
        self.assertEqual(decide(card, ctx()), Decision("block", "R3", "secret_text"))

    def test_r3_cannot_be_unlocked_by_mode_or_scope(self):
        wide = ctx(mode="auto", scope=replace(ctx().scope, kinds=frozenset({"pay", "shell_run"})))
        self.assertEqual(decide(Action(kind="pay"), wide).outcome, "handover")
        self.assertEqual(decide(Action(kind="shell_run"), wide).outcome, "block")

    def test_out_of_scope_asks_or_blocks(self):
        self.assertEqual(decide(Action(kind="tab_read", host="example.org"), ctx()), Decision("confirm", "R0", "scope_host"))
        denied = Action(kind="file_list", path="C:/Users/nadia/.ssh")
        self.assertEqual(decide(denied, ctx()), Decision("block", "R0", "path_denied"))
        self.assertEqual(decide(Action(kind="ui_click", app="excel"), ctx()), Decision("confirm", "R1", "scope_app"))
        outside = Action(kind="file_delete", path="C:/Users/nadia/Unduhan/a.txt")
        self.assertEqual(decide(outside, ctx()), Decision("confirm", "R2", "scope_path"))
        narrow = ctx(scope=replace(SCOPE, kinds=frozenset({"tab_read"})))
        self.assertEqual(decide(Action(kind="tab_click", host="shopee.co.id"), narrow), Decision("confirm", "R1", "scope_kind"))

    def test_modes(self):
        click = Action(kind="tab_click", host="shopee.co.id")
        self.assertEqual(decide(click, ctx(mode="auto")), Decision("allow", "R1", "tab_click"))
        self.assertEqual(decide(click, ctx(mode="ask")), Decision("confirm", "R1", "ask_mode"))
        self.assertEqual(decide(click, ctx(mode="apa saja")).outcome, "confirm")
        self.assertEqual(decide(click, ctx(mode=None)).outcome, "confirm")
        read = Action(kind="tab_read", host="shopee.co.id")
        self.assertEqual(decide(read, ctx(mode="ask")), Decision("allow", "R0", "tab_read"))

    def test_r2_always_confirms(self):
        delete = Action(kind="file_delete", path=SKRIPSI + "/lama.docx")
        for mode in ("auto", "ask"):
            self.assertEqual(decide(delete, ctx(mode=mode)), Decision("confirm", "R2", "file_delete"))

    def test_escalated_actions_confirm_even_in_auto_mode(self):
        tainted = Action(kind="tab_type", host="shopee.co.id", text="halo", tainted=True)
        self.assertEqual(decide(tainted, ctx(mode="auto")), Decision("confirm", "R2", "tainted_target"))
        submit = Action(kind="tab_click", host="shopee.co.id", submits=True)
        self.assertEqual(decide(submit, ctx(mode="auto")), Decision("confirm", "R2", "submits"))

    def test_purchase_gates(self):
        handoff = Action(kind="checkout_handoff", host="shopee.co.id")
        self.assertEqual(decide(handoff, ctx()), Decision("confirm", "R2", "checkout_handoff"))
        self.assertEqual(decide(handoff, ctx(adult_verified=False)), Decision("block", "R2", "underage"))
        self.assertEqual(decide(handoff, ctx(adult_verified=None)), Decision("block", "R2", "underage"))
        self.assertEqual(decide(handoff, ctx(store=REJECTED)), Decision("block", "R2", "no_official_badge"))
        self.assertEqual(decide(handoff, ctx(store=None)), Decision("block", "R2", "not_listed"))
        self.assertEqual(decide(handoff, ctx(store=replace(REJECTED, reason=None))), Decision("block", "R2", "not_listed"))
        self.assertEqual(decide(handoff, ctx(purchase_total=600_000)), Decision("block", "R2", "limit_exceeded"))
        self.assertEqual(decide(handoff, ctx(purchase_total=None)), Decision("block", "R2", "limit_exceeded"))
        self.assertEqual(decide(handoff, ctx(limits=SpendLimits())), Decision("block", "R2", "purchases_off"))

    def test_purchase_gate_order_is_age_then_store_then_limit(self):
        handoff = Action(kind="checkout_handoff", host="shopee.co.id")
        everything_wrong = ctx(adult_verified=False, store=REJECTED, purchase_total=900_000)
        self.assertEqual(decide(handoff, everything_wrong).reason, "underage")
        self.assertEqual(decide(handoff, ctx(store=REJECTED, purchase_total=900_000)).reason, "no_official_badge")

    def test_task_spend_cap_and_monthly_total_apply(self):
        handoff = Action(kind="checkout_handoff", host="shopee.co.id")
        self.assertEqual(decide(handoff, ctx(scope=replace(SCOPE, spend_cap=100_000))).reason, "limit_exceeded")
        self.assertEqual(decide(handoff, ctx(spent_this_month=1_400_000)).reason, "limit_exceeded")

    def test_checkout_prepare_is_limited_too(self):
        prepare = Action(kind="checkout_prepare", host="shopee.co.id")
        self.assertEqual(decide(prepare, ctx()), Decision("allow", "R1", "checkout_prepare"))
        self.assertEqual(decide(prepare, ctx(purchase_total=600_000)), Decision("block", "R1", "limit_exceeded"))

    def test_cart_add_needs_official_store_but_no_total(self):
        add = Action(kind="cart_add", host="shopee.co.id")
        self.assertEqual(decide(add, ctx(purchase_total=None)), Decision("allow", "R1", "cart_add"))
        self.assertEqual(decide(add, ctx(store=REJECTED)).outcome, "block")

    def test_order_cancel_needs_store_and_confirmation_but_no_total(self):
        cancel = Action(kind="order_cancel", host="shopee.co.id")
        self.assertEqual(decide(cancel, ctx(purchase_total=None)), Decision("confirm", "R2", "order_cancel"))
        self.assertIn("order_cancel", PURCHASE_KINDS)

    def test_handover_only_for_targets_inside_the_task(self):
        # Temuan I4: serah terima di halaman yang bukan bagian tugas adalah bantuan phishing.
        outside = Action(kind="tab_type", host="evil.example", text="x", field_type="password")
        self.assertEqual(decide(outside, ctx()), Decision("block", "R3", "secret_field"))
        bank = Action(kind="tab_type", host="ibank.klikbca.com", text="x", field_type="password")
        self.assertEqual(decide(bank, ctx()), Decision("block", "R3", "blocked_host"))
        vault = Action(kind="ui_type", app="bitwarden", text="x", field_type="password")
        self.assertEqual(decide(vault, ctx()), Decision("block", "R3", "blocked_app"))
        other_app = Action(kind="ui_type", app="excel", text="x", field_type="password")
        self.assertEqual(decide(other_app, ctx()), Decision("block", "R3", "secret_field"))
        inside_app = Action(kind="ui_type", app="winword", text="x", field_type="password")
        self.assertEqual(decide(inside_app, ctx()), Decision("handover", "R3", "secret_field"))

    def test_bank_host_stays_blocked_in_every_spelling(self):
        # Temuan C2, termasuk saat ejaan itu sengaja dimasukkan ke lingkup.
        for host in ("ibank.klikbca.com.", "ibank.klikbca.com:443", "IBANK.klikbca.com"):
            wide = ctx(scope=replace(SCOPE, hosts=frozenset({"shopee.co.id", host})))
            with self.subTest(host=host):
                self.assertEqual(decide(Action(kind="tab_read", host=host), wide), Decision("block", "R3", "blocked_host"))

    def test_host_with_a_path_or_backslash_is_blocked(self):
        for host in ("evil.com/.shopee.co.id", "evil.com\\.shopee.co.id", "evil.com#.shopee.co.id"):
            with self.subTest(host=host):
                self.assertEqual(decide(Action(kind="tab_open", host=host), ctx()), Decision("block", "R3", "bad_host"))

    def test_store_verdict_must_be_for_the_host_of_the_action(self):
        # Temuan I5.
        two_hosts = ctx(scope=replace(SCOPE, hosts=frozenset({"shopee.co.id", "evil.example"})))
        self.assertEqual(decide(Action(kind="cart_add", host="evil.example"), two_hosts), Decision("block", "R1", "not_listed"))
        self.assertEqual(decide(Action(kind="checkout_handoff", host="evil.example"), two_hosts), Decision("block", "R2", "not_listed"))
        self.assertEqual(decide(Action(kind="cart_add", host="mall.shopee.co.id"), two_hosts).outcome, "allow")

    def test_nothing_goes_into_the_cart_while_purchases_are_off(self):
        # Temuan I6.
        add = Action(kind="cart_add", host="shopee.co.id")
        self.assertEqual(decide(add, ctx(limits=SpendLimits())), Decision("block", "R1", "purchases_off"))
        self.assertEqual(decide(add, ctx(scope=replace(SCOPE, spend_cap=0))), Decision("block", "R1", "purchases_off"))
        prepare = Action(kind="checkout_prepare", host="shopee.co.id")
        self.assertEqual(decide(prepare, ctx(scope=replace(SCOPE, spend_cap=0))), Decision("block", "R1", "purchases_off"))
        cancel = Action(kind="order_cancel", host="shopee.co.id")
        self.assertEqual(decide(cancel, ctx(limits=SpendLimits())), Decision("confirm", "R2", "order_cancel"))

    def test_possible_secret_asks_even_in_auto_mode(self):
        typing = Action(kind="tab_type", host="shopee.co.id", text="Ab3d" * 8)
        self.assertEqual(decide(typing, ctx(mode="auto")), Decision("confirm", "R2", "possible_secret"))

    def test_broken_action_never_raises(self):
        for action in (Action(kind=None), Action(kind="tab_read", host=7), Action(kind="file_move", path=object())):
            with self.subTest(action=action):
                self.assertIn(decide(action, ctx()).outcome, ("block", "confirm"))

    def test_broken_context_blocks(self):
        read = Action(kind="tab_read", host="shopee.co.id")
        self.assertEqual(decide(read, ctx(scope=None)), Decision("block", "R3", "internal_error"))
        self.assertEqual(decide(read, None), Decision("block", "R3", "internal_error"))
        self.assertEqual(decide(None, ctx()), Decision("block", "R3", "internal_error"))


if __name__ == "__main__":
    unittest.main()
