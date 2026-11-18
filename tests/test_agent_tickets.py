import base64
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from agent_api.main import create_app  # noqa: E402
from agent_api.settings import load_settings  # noqa: E402
from agent_api.tickets import TicketSigner, kid, make_ticket, verify_ticket  # noqa: E402
from tests.agent_fakes import MemoryStore  # noqa: E402
from tests.agent_service_fakes import ENV, Clock  # noqa: E402

SEED_A = bytes.fromhex("11" * 32)
SEED_B = bytes.fromhex("55" * 32)
NOW = 1_795_000_000
SIGNER = TicketSigner((SEED_A,))


def public_of(seed):
    return Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def check(signed, keys=None, task="t1", device="d1", last_seq=2, now=NOW):
    return verify_ticket(signed, keys or SIGNER.public_keys(), task=task, device=device, last_seq=last_seq, now=now)


class TicketTest(unittest.TestCase):
    def test_make_ticket_has_the_fixed_fields(self):
        ticket = make_ticket("t1", "d1", 3, "tab_click", {"ref": 5}, "shopee.co.id", NOW)
        self.assertEqual(ticket, {"v": 1, "task": "t1", "device": "d1", "seq": 3, "tool": "tab_click",
                                  "args": {"ref": 5}, "host": "shopee.co.id", "exp": NOW + 60})

    def test_a_signed_ticket_verifies(self):
        signed = SIGNER.sign(make_ticket("t1", "d1", 3, "tab_read", {}, "shopee.co.id", NOW))
        self.assertEqual(set(signed), {"ticket", "kid", "sig"})
        self.assertIsNone(check(signed))
        self.assertIsNone(check(signed, now=NOW + 60))

    def test_tampering_and_replay_are_refused(self):
        signed = SIGNER.sign(make_ticket("t1", "d1", 3, "tab_click", {"ref": 5}, "shopee.co.id", NOW))
        self.assertEqual(check({**signed, "ticket": {**signed["ticket"], "args": {"ref": 6}}}), "bad_signature")
        self.assertEqual(check({**signed, "ticket": {**signed["ticket"], "host": "evil.example"}}), "bad_signature")
        self.assertEqual(check({**signed, "sig": signed["sig"][:-2] + "AA"}), "bad_signature")
        self.assertEqual(check(signed, last_seq=3), "old_seq")
        self.assertEqual(check(signed, task="t2"), "wrong_task")
        self.assertEqual(check(signed, device="d2"), "wrong_device")
        self.assertEqual(check(signed, now=NOW + 61), "expired")

    def test_broken_input_is_refused_without_raising(self):
        signed = SIGNER.sign(make_ticket("t1", "d1", 3, "tab_read", {}, "shopee.co.id", NOW))
        for broken in (None, [], {}, {**signed, "sig": "%%%"}, {**signed, "sig": 7}, {**signed, "ticket": "x"},
                       {**signed, "extra": 1}, {k: v for k, v in signed.items() if k != "kid"}):
            with self.subTest(broken=broken):
                self.assertIn(check(broken), ("bad_form", "bad_signature"))
        self.assertEqual(check({**signed, "kid": "0" * 16}), "unknown_key")
        self.assertEqual(check(signed, keys=[{"kid": signed["kid"], "alg": "Ed25519", "key": "rusak"}]), "bad_signature")

    def test_rotation_keeps_old_tickets_valid_and_new_ones_use_the_new_key(self):
        old, new = TicketSigner((SEED_A,)), TicketSigner((SEED_B, SEED_A))
        ticket = make_ticket("t1", "d1", 1, "tab_read", {}, "shopee.co.id", NOW)
        self.assertIsNone(check(old.sign(ticket), keys=new.public_keys(), last_seq=0))
        self.assertEqual(new.sign(ticket)["kid"], kid(public_of(SEED_B)))
        self.assertEqual([key["kid"] for key in new.public_keys()], [kid(public_of(SEED_B)), kid(public_of(SEED_A))])
        self.assertEqual(check(new.sign(ticket), keys=old.public_keys(), last_seq=0), "unknown_key")

    def test_public_keys_have_the_published_shape(self):
        self.assertEqual(SIGNER.public_keys(), [{"kid": kid(public_of(SEED_A)), "alg": "Ed25519", "key": b64url(public_of(SEED_A))}])
        self.assertRegex(kid(public_of(SEED_A)), r"^[0-9a-f]{16}$")

    def test_the_signature_covers_canonical_json(self):
        ticket = make_ticket("t1", "d1", 1, "tab_type", {"text": "kursi é", "ref": 2}, "shopee.co.id", NOW)
        reordered = dict(reversed(list(ticket.items())))
        self.assertEqual(SIGNER.sign(ticket)["sig"], SIGNER.sign(reordered)["sig"])


class TicketEndpointTest(unittest.TestCase):
    def test_the_public_endpoint_lists_keys_and_never_a_seed(self):
        settings, _ = load_settings({**ENV, "AGENT_TICKET_KEY_OLD": "44" * 32})
        client = TestClient(create_app(settings, store=MemoryStore(), models=None, google=None, clock=Clock()))
        response = client.get("/v1/ticket-keys")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["keys"]), 2)

        for seed in (bytes.fromhex("11" * 32), bytes.fromhex("44" * 32)):
            self.assertNotIn(b64url(seed), response.text)
            self.assertNotIn(seed.hex(), response.text)


if __name__ == "__main__":
    unittest.main()
