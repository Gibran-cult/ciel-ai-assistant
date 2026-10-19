"""Pembelian Ciel Pro lewat Midtrans: payments.py, order di chat_store, Pricing, Privasi, dan alur app."""

import os
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import requests
import streamlit
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
sys.path.insert(0, str(ROOT))

import chat_store  # noqa: E402
import payments  # noqa: E402
import pricing  # noqa: E402
import privacy  # noqa: E402
from tests.test_chat_store import ALICE, ENV, SIGNED_IN, SIGNED_IN_OWNER, Response  # noqa: E402

ORDER = "0123456789abcdef0123456789abcdef"


def iso(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


class SnapTest(unittest.TestCase):

    def test_payload_is_one_30_day_item_with_an_expiry_and_return_page(self):
        payload = payments.snap_payload(ORDER, 79_000, "https://ciel.example/?page=pricing",
                                        email="a@example.com", name="N" * 80)
        self.assertEqual(payload["transaction_details"], {"order_id": ORDER, "gross_amount": 79_000})
        self.assertEqual(payload["item_details"], [
            {"id": "ciel-pro-30", "price": 79_000, "quantity": 1, "name": "Ciel Pro 30 hari"},
        ])
        self.assertEqual(payload["expiry"], {"unit": "minutes", "duration": 60})
        self.assertEqual(payload["callbacks"], {"finish": "https://ciel.example/?page=pricing"})
        self.assertEqual(payload["customer_details"], {"email": "a@example.com", "first_name": "N" * 50})
        self.assertNotIn("customer_details", payments.snap_payload(ORDER, 79_000, "u"))

    def test_order_ids_fit_midtrans_and_the_store(self):
        order_id = payments.new_order_id()
        self.assertRegex(order_id, r"^[0-9a-f]{32}$")
        self.assertRegex(order_id, chat_store.ROW_ID_PATTERN.pattern)

    def test_finish_url_drops_the_current_query(self):
        self.assertEqual(payments.finish_url("https://ciel.streamlit.app/?page=login"),
                         "https://ciel.streamlit.app/?page=pricing")
        self.assertEqual(payments.finish_url("http://localhost:8501"), "http://localhost:8501/?page=pricing")

    def test_snap_uses_the_server_key_and_the_right_environment(self):
        with patch("requests.post", return_value=Response({"token": "t", "redirect_url": "https://pay.example/x"})) as post:
            self.assertEqual(payments.create_snap_transaction("SB-key", False, {"a": 1}), "https://pay.example/x")
            payments.create_snap_transaction("key", True, {"a": 1})
        sandbox, production = post.call_args_list
        self.assertEqual(sandbox.args[0], "https://app.sandbox.midtrans.com/snap/v1/transactions")
        self.assertEqual(sandbox.kwargs["auth"], ("SB-key", ""))
        self.assertEqual(production.args[0], "https://app.midtrans.com/snap/v1/transactions")

    def test_snap_failures_return_none_without_details(self):
        with self.assertLogs("ciel_ai.payments", level="ERROR") as logs:
            with patch("requests.post", return_value=Response(status=401)):
                self.assertIsNone(payments.create_snap_transaction("k", False, {}))
            with patch("requests.post", return_value=Response({"error_messages": ["x"]})):
                self.assertIsNone(payments.create_snap_transaction("k", False, {}))
        self.assertNotIn("SB-", "".join(logs.output))

    def test_order_messages(self):
        self.assertEqual(payments.order_message({"status": "paid"})[0], "ok")
        self.assertEqual(payments.order_message({"status": "pending"})[0], "wait")
        self.assertEqual(payments.order_message({"status": "expire"})[0], "fail")
        self.assertEqual(payments.order_message({"status": "something new"})[0], "wait")
        self.assertIsNone(payments.order_message({}))
        self.assertIsNone(payments.order_message(None))


class OrderStoreTest(unittest.TestCase):

    def setUp(self):
        self.store = chat_store.ChatStore("https://db.example.invalid", "service-key")

    def test_create_order_inserts_a_pending_row_for_the_owner(self):
        with patch("requests.post", return_value=Response()) as post:
            self.assertTrue(self.store.create_order(ALICE, ORDER, 79_000))
        self.assertEqual(post.call_args.args[0], "https://db.example.invalid/rest/v1/pro_orders")
        self.assertEqual(post.call_args.kwargs["json"],
                         {"owner": ALICE, "id": ORDER, "amount": 79_000, "status": "pending"})

    def test_latest_order_is_read_for_this_owner_only(self):
        rows = [{"id": ORDER, "status": "paid", "created_at": "2026-11-17T00:00:00+00:00"}]
        with patch("requests.request", return_value=Response(rows)) as request:
            order = self.store.load_latest_order(ALICE)
        self.assertEqual(order, {"id": ORDER, "status": "paid", "created_at": 1_794_873_600.0})
        params = request.call_args.kwargs["params"]
        self.assertEqual((params["owner"], params["order"], params["limit"]), (f"eq.{ALICE}", "created_at.desc", "1"))

        with patch("requests.request", return_value=Response([])):
            self.assertEqual(self.store.load_latest_order(ALICE), {})
        with self.assertLogs("ciel_ai.chat_store", level="ERROR"), \
                patch("requests.request", return_value=Response(status=500)):
            self.assertIsNone(self.store.load_latest_order(ALICE))

    def test_bad_ids_never_reach_the_database(self):
        with self.assertLogs("ciel_ai.chat_store", level="ERROR"), patch("requests.post") as post:
            self.assertFalse(self.store.create_order(ALICE, "x&status=eq.paid", 1))
            self.assertFalse(self.store.create_order("a,b", ORDER, 1))
        post.assert_not_called()

    def test_sql_settles_once_and_only_from_the_service_role(self):
        sql = (ROOT / "docs" / "chat_store.sql").read_text(encoding="utf-8")
        self.assertIn("create table if not exists public.pro_orders", sql)
        self.assertIn("alter table public.pro_orders enable row level security;", sql)
        self.assertIn("if paid_order.status = 'paid' then\n        return 'already_paid';", sql)
        self.assertIn("if p_gross_amount is distinct from paid_order.amount then", sql)
        self.assertIn("for update", sql)
        self.assertIn("greatest(pro_members.expires_at, now()) + interval '30 days'", sql)
        self.assertIn("revoke execute on function public.ciel_settle_order(text, numeric, text) from public, anon, authenticated;", sql)


def render_page(pro_action=False):
    import pricing as page
    import streamlit as st

    page.render_pricing(pro_action=(lambda: st.button("Beli Pro 30 hari", key="pro_buy")) if pro_action else None)


class PricingCheckoutTest(unittest.TestCase):

    def text(self, at):
        return " ".join(md.value for md in at.markdown)

    def test_pro_is_a_buyable_card_when_payments_are_on(self):
        at = AppTest.from_function(render_page, kwargs={"pro_action": True}).run()
        self.assertFalse(at.exception)
        self.assertEqual([b.label for b in at.button], ["Mulai chat", "Beli Pro 30 hari"])
        html = self.text(at)
        self.assertIn("Rp79.000</strong><span>untuk 30 hari", html)
        self.assertIn("Sekali bayar, tanpa langganan", html)
        self.assertIn("Bagaimana cara membayar Pro?", html)
        self.assertNotIn("Rencana Rp79.000/bulan", html)
        self.assertIn("Rencana Rp149.000/bulan per pengguna", html)  # Tim stays planned

    def test_pro_stays_planned_without_payments(self):
        at = AppTest.from_function(render_page).run()
        html = self.text(at)
        self.assertEqual([b.label for b in at.button], ["Mulai chat"])
        self.assertIn("Rencana Rp79.000/bulan", html)
        self.assertNotIn("Bagaimana cara membayar Pro?", html)

    def test_privacy_names_midtrans_only_when_payments_are_on(self):
        def text(payments_on):
            return " ".join(" ".join(items) for _, items in privacy.privacy_sections(30, True, True, payments=payments_on))
        self.assertIn("Midtrans", text(True))
        self.assertIn("tidak pernah menerima atau menyimpan data kartu", text(True))
        self.assertNotIn("Midtrans", text(False))


class CheckoutAppTest(unittest.TestCase):

    SECRETS = {
        "auth": {"redirect_uri": "http://localhost/oauth2callback"},
        "SUPABASE_URL": "https://db.example.invalid",
        "SUPABASE_SERVICE_KEY": "service-key",
        "MIDTRANS_SERVER_KEY": "SB-Mid-server-test",
        "APP_URL": "https://ciel.example",
    }

    def database(self, order=None, pro_until=None):
        tables = {
            "pro_orders": [order] if order else [],
            "pro_members": [{"expires_at": iso(pro_until)}] if pro_until else [],
        }
        return Mock(side_effect=lambda method, url, **kw: Response(tables.get(url.rsplit("/", 1)[1], [])))

    def run_pricing(self, user, database, at=None, secrets=None, post=None):
        with patch.dict(os.environ, ENV), patch.object(streamlit, "user", user), \
                patch("requests.request", database), patch("requests.post", post or Mock(return_value=Response())):
            if at is None:
                at = AppTest.from_file(str(APP_PATH), default_timeout=60)
                for key, value in (secrets or self.SECRETS).items():
                    at.secrets[key] = value
                at.query_params["page"] = "pricing"
            at.run()
        return at

    def test_guests_are_asked_to_sign_in_first(self):
        at = self.run_pricing({}, self.database())
        self.assertFalse(at.exception)
        self.assertEqual(at.button(key="pro_login").label, "Masuk untuk membeli")

    def test_buying_creates_an_order_then_a_snap_link(self):
        at = self.run_pricing(SIGNED_IN, self.database())
        self.assertFalse(at.exception)
        self.assertEqual(at.button(key="pro_buy").label, "Beli Pro 30 hari")

        at.button(key="pro_buy").click()
        post = Mock(side_effect=lambda url, **kw: Response(
            {"token": "t", "redirect_url": "https://app.sandbox.midtrans.com/snap/v4/redirection/t"}
            if "midtrans" in url else None
        ))
        at = self.run_pricing(SIGNED_IN, self.database(), at=at, post=post)

        order_call, snap_call = post.call_args_list
        order = order_call.kwargs["json"]
        self.assertEqual(order_call.args[0], "https://db.example.invalid/rest/v1/pro_orders")
        self.assertEqual((order["owner"], order["amount"], order["status"]), (SIGNED_IN_OWNER, 79_000, "pending"))
        snap = snap_call.kwargs["json"]
        self.assertEqual(snap["transaction_details"], {"order_id": order["id"], "gross_amount": 79_000})
        self.assertEqual(snap["callbacks"]["finish"], "https://ciel.example/?page=pricing")
        self.assertEqual(snap_call.kwargs["auth"], ("SB-Mid-server-test", ""))

        link_buttons = at.get("link_button")
        self.assertEqual(len(link_buttons), 1)
        self.assertIn("snap/v4/redirection", link_buttons[0].proto.url)

    def test_failed_snap_shows_an_error_and_no_link(self):
        at = self.run_pricing(SIGNED_IN, self.database())
        at.button(key="pro_buy").click()
        post = Mock(side_effect=lambda url, **kw: Response(status=401) if "midtrans" in url else Response())
        with self.assertLogs("ciel_ai.payments", level="ERROR"):
            at = self.run_pricing(SIGNED_IN, self.database(), at=at, post=post)
        self.assertEqual(len(at.get("link_button")), 0)
        self.assertIn("belum bisa dibuka", at.error[0].value)

    def test_returning_after_payment_reads_the_database_not_the_url(self):
        paid = {"id": ORDER, "status": "paid", "created_at": iso(time.time() - 120)}
        at = AppTest.from_file(str(APP_PATH), default_timeout=60)
        for key, value in self.SECRETS.items():
            at.secrets[key] = value
        # What Midtrans may append to the finish URL is ignored.
        at.query_params["page"] = "pricing?order_id=forged&transaction_status=settlement"
        at = self.run_pricing(SIGNED_IN, self.database(order=paid, pro_until=time.time() + 30 * 86400), at=at)

        self.assertFalse(at.exception)
        self.assertIn("Pembayaran diterima. Ciel Pro aktif sampai", at.success[0].value)
        self.assertEqual(at.button(key="pro_buy").label, "Perpanjang 30 hari")

    def test_pending_order_offers_a_recheck_and_never_grants_pro(self):
        pending = {"id": ORDER, "status": "pending", "created_at": iso(time.time() - 60)}
        at = self.run_pricing(SIGNED_IN, self.database(order=pending))
        self.assertIn("Menunggu konfirmasi", at.info[0].value)
        self.assertTrue(at.button(key="pro_recheck"))
        self.assertEqual(at.button(key="pro_buy").label, "Beli Pro 30 hari")

    def test_old_orders_are_not_shown(self):
        old = {"id": ORDER, "status": "expire", "created_at": iso(time.time() - 3 * 86400)}
        at = self.run_pricing(SIGNED_IN, self.database(order=old))
        self.assertEqual(len(at.error), 0)

    def test_without_a_server_key_pro_is_not_for_sale(self):
        secrets = {k: v for k, v in self.SECRETS.items() if k != "MIDTRANS_SERVER_KEY"}
        at = self.run_pricing(SIGNED_IN, self.database(), secrets=secrets)
        self.assertFalse(at.exception)
        self.assertNotIn("pro_buy", [b.key for b in at.button])


if __name__ == "__main__":
    unittest.main()
