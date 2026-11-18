"""Layanan agent lokal untuk uji ujung ke ujung ekstensi. HANYA UNTUK UJI.

Menjalankan aplikasi agent sungguhan (agent_api.main.create_app) dengan
penyimpanan di memori, model bernaskah, dan Google tiruan, ditambah:

- situs tiruan HTTPS (sertifikat buatan sendiri) untuk host toko.test,
  dari extension/tests/e2e/shop/;
- POST /test/device: membuat perangkat dan pasangan token untuk satu akun
  uji, supaya uji tidak perlu login Google;
- POST /test/script: mengganti naskah model untuk tugas berikutnya.

Kedua endpoint /test hanya ada di skrip ini, tidak pernah di aplikasi
produksi. Semua pendengar terikat ke 127.0.0.1.

    python tools/agent_e2e_server.py --origin chrome-extension://<id>
"""

import argparse
import datetime
import ipaddress
import json
import ssl
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402
from cryptography import x509  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from cryptography.x509.oid import NameOID  # noqa: E402
from fastapi import Request  # noqa: E402

from account_ids import owner_from_subject  # noqa: E402
from agent_api.devices import issue_pair  # noqa: E402
from agent_api.main import create_app  # noqa: E402
from agent_api.model import ScriptedModel  # noqa: E402
from agent_api.settings import load_settings  # noqa: E402
from tests.agent_fakes import MemoryStore  # noqa: E402
from tests.agent_service_fakes import ENV  # noqa: E402

HOST = "127.0.0.1"
SHOP = ROOT / "extension" / "tests" / "e2e" / "shop"
TEST_OWNER = owner_from_subject("e2e-tester")
DEFAULT_PLAN = {"steps": ["Baca halaman"], "hosts": ["toko.test"], "kinds": ["tab_read"], "spend_cap": 0}


class SwitchableModel:
    """Model bernaskah yang naskahnya bisa diganti uji lewat /test/script."""

    def __init__(self):
        self.script = (DEFAULT_PLAN, [])
        self.current = ScriptedModel(*self.script)

    def load(self, plan, calls):
        self.script = (plan, list(calls))

    def plan(self, instruction):
        # Setiap tugas baru memutar naskah dari awal.
        self.current = ScriptedModel(*self.script)
        return self.current.plan(instruction)

    def act(self, view):
        return self.current.act(view)


class NoGoogle:
    """Login Google tidak dipakai di uji ujung ke ujung (lihat /test/device)."""

    def __getattr__(self, name):
        raise RuntimeError("Google tidak tersedia di server uji")


def clock():
    return datetime.datetime.now(datetime.timezone.utc)


def build(origin):
    env = {**ENV, "AGENT_WS_ORIGINS": origin, "AGENT_TASKS_PER_MONTH_FREE": "1000",
           "AGENT_DEVICE_REDIRECTS": "https://abcdefghijklmnop.chromiumapp.org/"}
    settings, missing = load_settings(env)

    if settings is None:
        raise SystemExit(f"pengaturan uji tidak lengkap: {missing}")

    store = MemoryStore()
    model = SwitchableModel()
    app = create_app(settings, store=store, models=model, google=NoGoogle(), clock=clock)

    @app.post("/test/device")
    def test_device():
        device = f"e2e{len(store.devices) + 1}"
        store.create_device(TEST_OWNER, device, "Chrome uji", "extension")
        return issue_pair(store, TEST_OWNER, device, int(clock().timestamp()))

    @app.get("/test/actions")
    def test_actions():
        """Log aksi tugas terakhir akun uji: jenis, keputusan guard, alasan, dan hasil."""

        tasks = [task_id for owner, task_id in store.tasks if owner == TEST_OWNER]
        last = tasks[-1] if tasks else None
        return [{key: row.get(key) for key in ("seq", "kind", "target", "decision", "reason", "result")}
                for row in store.actions if row.get("owner") == TEST_OWNER and row.get("task") == last]

    @app.post("/test/script")
    async def test_script(request: Request):
        body = await request.json()
        model.load(body["plan"], body.get("calls", []))
        return {"ok": True}

    return app


def certificate(folder):
    """Sertifikat buatan sendiri untuk toko.test, hanya untuk situs tiruan."""

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "toko.test")])
    now = clock()
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=7))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("toko.test"), x509.IPAddress(ipaddress.ip_address(HOST))]), False)
            .sign(key, hashes.SHA256()))
    cert_path, key_path = Path(folder) / "toko.pem", Path(folder) / "toko.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return cert_path, key_path


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        # Formulir tiruan: kiriman apa pun diarahkan ke halaman terima kasih.
        length = int(self.headers.get("content-length") or 0)
        self.rfile.read(length)
        self.send_response(303)
        self.send_header("location", "/terima.html")
        self.end_headers()


def serve_shop(port, folder):
    cert_path, key_path = certificate(folder)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    server = ThreadingHTTPServer((HOST, port), partial(QuietHandler, directory=str(SHOP)))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8611)
    parser.add_argument("--shop-port", type=int, default=8612)
    parser.add_argument("--origin", required=True, help="chrome-extension://<id> ekstensi uji")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory() as folder:
        serve_shop(args.shop_port, folder)
        print(json.dumps({"api": f"http://{HOST}:{args.port}", "shop": f"https://toko.test:{args.shop_port}"}), flush=True)
        uvicorn.run(build(args.origin), host=HOST, port=args.port, log_level="warning", ws_max_size=262144)


if __name__ == "__main__":
    main()
