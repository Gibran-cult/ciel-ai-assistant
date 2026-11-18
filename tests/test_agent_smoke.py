import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, WebSocket  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from agent_api import ws as ws_module  # noqa: E402
from agent_api.main import create_app  # noqa: E402
from agent_api.settings import load_settings  # noqa: E402
from tests.agent_fakes import MemoryStore  # noqa: E402
from tests.agent_service_fakes import ENV, Clock  # noqa: E402
from tools.agent_smoke import check  # noqa: E402

GOOD_ORIGIN = "chrome-extension://abcdefghijklmnop"


def test_connect(client):
    """Sambungan WebSocket lewat TestClient: kode penutupan, atau None kalau sempat ada pesan."""

    def connect(path, origin):
        try:
            with client.websocket_connect(path, headers={"origin": origin}) as ws:
                ws.receive_text()
                return None
        except WebSocketDisconnect as closed:
            return closed.code

    return connect


class SmokeTest(unittest.TestCase):
    def test_a_correct_service_passes(self):
        client = TestClient(create_app(load_settings(ENV)[0], store=MemoryStore(), models=None, google=None, clock=Clock()))

        with patch.object(ws_module, "HELLO_SECONDS", 0.2):
            self.assertEqual(check(client, test_connect(client), GOOD_ORIGIN), [])

    def test_a_service_that_accepts_any_origin_fails_with_a_clear_message(self):
        app = FastAPI()

        @app.get("/healthz")
        def healthz():
            return {"ok": True}

        @app.get("/v1/ticket-keys")
        def keys():
            return {"keys": []}

        @app.websocket("/v1/ws")
        async def socket(websocket: WebSocket):
            await websocket.accept()
            await websocket.send_text("halo")

        client = TestClient(app)
        problems = check(client, test_connect(client), GOOD_ORIGIN)
        self.assertIn("ticket-keys: tidak ada kunci publik", problems)
        self.assertIn("ws: Origin asing tidak ditolak (kode None, seharusnya 4403)", problems)
        self.assertIn("ws: koneksi tanpa hello tidak ditutup (kode None, seharusnya 4408)", problems)
        self.assertIn("device/login: alamat kembali asing tidak ditolak (status 404, seharusnya 400)", problems)

    def test_a_dead_service_fails(self):
        client = TestClient(create_app(None, store=None, models=None, google=None, clock=Clock(), missing=["AGENT_CHAIN_KEY"]))
        problems = check(client, test_connect(client), GOOD_ORIGIN)
        self.assertIn("healthz: status 503, seharusnya 200", problems)


if __name__ == "__main__":
    unittest.main()
