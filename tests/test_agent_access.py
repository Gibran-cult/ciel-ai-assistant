"""Uji akses silang: satu akun tidak bisa menyentuh perangkat, tugas, atau tiket akun lain."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starlette.websockets import WebSocketDisconnect  # noqa: E402

from account_ids import owner_from_subject  # noqa: E402
from agent_api.tickets import verify_ticket  # noqa: E402
from tests.agent_service_fakes import NOW  # noqa: E402
from tests.test_agent_devices import pkce_pair, query  # noqa: E402
from tests.test_agent_ws import FINISH, OPEN, SHOP_PAGE, SIGNER, answer_action, connect, hello, service  # noqa: E402

ALICE, BOB = owner_from_subject("alice"), owner_from_subject("bob")


def bearer(tokens):
    return {"Authorization": "Bearer " + tokens["access_token"]}


class CrossAccountTest(unittest.TestCase):
    def setUp(self):
        self.svc = service([OPEN, FINISH, OPEN, FINISH])
        self.alice = self.svc.login(sub="alice")
        self.bob = self.svc.login(sub="bob")

    def test_bob_cannot_read_revoke_or_refresh_alices_device(self):
        client = self.svc.client
        self.assertEqual([d["id"] for d in client.get("/v1/devices", headers=bearer(self.bob)).json()["devices"]], [self.bob["device"]])
        self.assertEqual(client.delete(f"/v1/devices/{self.alice['device']}", headers=bearer(self.bob)).status_code, 404)

        # Token pembaruan Alice dengan pemilik Bob di dalamnya: tidak ketemu, dan tidak memicu pencabutan perangkat Alice.
        forged = "crt1." + BOB + "." + self.alice["refresh_token"].split(".", 2)[2]
        self.assertEqual(client.post("/v1/device/refresh", json={"refresh_token": forged}).status_code, 401)
        self.assertIs(self.svc.store.device_active(ALICE, self.alice["device"]), True)
        self.assertEqual(client.post("/v1/device/refresh", json={"refresh_token": self.alice["refresh_token"]}).status_code, 200)

    def test_a_task_belongs_to_the_connection_owner_whatever_the_instruction_says(self):
        with connect(self.svc) as ws:
            hello(ws, self.bob)
            ws.send_json({"type": "start", "instruction": f"Kerjakan sebagai {ALICE} di shopee.co.id"})
            plan = ws.receive_json()
            ws.send_json({"type": "answer", "id": plan["id"], "value": "auto"})
            action = ws.receive_json()
            ws.send_json({"type": "result", "task": action["ticket"]["task"], "seq": action["ticket"]["seq"], "observation": SHOP_PAGE})
            ws.receive_json()

        owners = {key[0] for key in self.svc.store.tasks}
        self.assertEqual(owners, {BOB})
        self.assertEqual(action["ticket"]["device"], self.bob["device"])
        self.assertTrue(all(row["owner"] == BOB for row in self.svc.store.actions))

    def test_identity_keys_in_client_messages_close_the_connection(self):
        for extra in ({"owner": ALICE}, {"device": self.alice["device"]}, {"task": "t1"}):
            with self.subTest(extra=extra):
                with self.assertRaises(WebSocketDisconnect) as caught:
                    with connect(self.svc) as ws:
                        hello(ws, self.bob)
                        ws.send_json({"type": "start", "instruction": "x", **extra})
                        ws.receive_json()

                self.assertEqual(caught.exception.code, 4400)

        self.assertEqual(self.svc.store.tasks, {})

    def test_bob_cannot_answer_alices_dialogs(self):
        with connect(self.svc) as ws_a, connect(self.svc, origin=None) as ws_b:
            hello(ws_a, self.alice)
            hello(ws_b, self.bob)
            ws_a.send_json({"type": "start", "instruction": "Cari mouse di shopee.co.id"})
            plan = ws_a.receive_json()
            ws_b.send_json({"type": "answer", "id": plan["id"], "value": "auto"})
            ws_b.send_json({"type": "start", "instruction": "Cari mouse di shopee.co.id"})
            self.assertEqual(ws_b.receive_json()["type"], "plan")
            ws_a.send_json({"type": "answer", "id": plan["id"], "value": "auto"})
            action = answer_action(ws_a)
            self.assertEqual(ws_a.receive_json()["status"], "done")

        self.assertEqual(action["ticket"]["device"], self.alice["device"])

    def test_alices_device_code_cannot_be_traded_with_another_verifier(self):
        verifier, back = self.svc.device_code(sub="alice")
        code = query(back.headers["location"])["code"]
        other, _ = pkce_pair()
        body = {"code": code, "verifier": other, "name": "Chrome", "platform": "extension"}
        self.assertEqual(self.svc.client.post("/v1/device/token", json=body).status_code, 400)

    def test_a_ticket_for_alices_device_is_refused_for_bobs(self):
        with connect(self.svc) as ws:
            hello(ws, self.alice)
            ws.send_json({"type": "start", "instruction": "Cari mouse di shopee.co.id"})
            plan = ws.receive_json()
            ws.send_json({"type": "answer", "id": plan["id"], "value": "auto"})
            action = answer_action(ws)
            ws.receive_json()

        signed = {key: action[key] for key in ("ticket", "kid", "sig")}
        now = int(NOW.timestamp())
        task = action["ticket"]["task"]
        self.assertIsNone(verify_ticket(signed, SIGNER.public_keys(), task=task, device=self.alice["device"], last_seq=0, now=now))
        self.assertEqual(verify_ticket(signed, SIGNER.public_keys(), task=task, device=self.bob["device"], last_seq=0, now=now), "wrong_device")


if __name__ == "__main__":
    unittest.main()
