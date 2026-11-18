"""Uji asap Ciel Agent API yang sudah berjalan (staging atau produksi).

Tidak login, tidak memanggil model, dan tidak menghabiskan biaya. Yang dicek:
/healthz, kunci publik tiket, penolakan alamat kembali asing, penolakan
Origin asing di WebSocket, dan batas waktu pesan hello.

    python tools/agent_smoke.py --base https://agent-staging.ciel-ai.web.id --origin chrome-extension://<id>
"""

import argparse
import sys

FOREIGN = "https://smoke.invalid"
CHALLENGE = "A" * 43


def check(http, connect, origin):
    """Daftar masalah, kosong kalau semua pemeriksaan lulus.

    http: objek dengan get(path, params=..., follow_redirects=...), misalnya httpx.Client.
    connect(path, origin): kode penutupan WebSocket, atau None kalau server sempat mengirim pesan.
    """

    problems = []

    def run(name, step):
        try:
            message = step()
        except Exception as error:
            message = f"{name}: gagal ({type(error).__name__})"

        if message:
            problems.append(message)

    def healthz():
        status = http.get("/healthz").status_code
        return None if status == 200 else f"healthz: status {status}, seharusnya 200"

    def ticket_keys():
        response = http.get("/v1/ticket-keys")
        keys = response.json().get("keys") if response.status_code == 200 else None
        return None if keys else "ticket-keys: tidak ada kunci publik"

    def login():
        params = {"challenge": CHALLENGE, "redirect": FOREIGN + "/", "state": "smoke"}
        status = http.get("/v1/device/login", params=params, follow_redirects=False).status_code
        return None if status == 400 else f"device/login: alamat kembali asing tidak ditolak (status {status}, seharusnya 400)"

    def foreign_origin():
        code = connect("/v1/ws", FOREIGN)
        return None if code == 4403 else f"ws: Origin asing tidak ditolak (kode {code}, seharusnya 4403)"

    def no_hello():
        code = connect("/v1/ws", origin)
        return None if code == 4408 else f"ws: koneksi tanpa hello tidak ditutup (kode {code}, seharusnya 4408)"

    run("healthz", healthz)
    run("ticket-keys", ticket_keys)
    run("device/login", login)
    run("ws", foreign_origin)
    run("ws", no_hello)
    return problems


def socket_connector(base):
    """connect() untuk server sungguhan, memakai klien websockets."""

    from websockets.exceptions import ConnectionClosed
    from websockets.sync.client import connect as ws_connect

    root = "wss://" + base.split("://", 1)[1] if base.startswith("https://") else "ws://" + base.split("://", 1)[-1]

    def connect(path, origin):
        with ws_connect(root.rstrip("/") + path, origin=origin, open_timeout=10) as socket:
            try:
                socket.recv(timeout=20)
                return None
            except ConnectionClosed as closed:
                return closed.rcvd.code if closed.rcvd else None

    return connect


def main(argv=None):
    parser = argparse.ArgumentParser(description="Uji asap Ciel Agent API")
    parser.add_argument("--base", required=True, help="misalnya https://agent-staging.ciel-ai.web.id")
    parser.add_argument("--origin", required=True, help="Origin ekstensi yang terdaftar, chrome-extension://<id>")
    args = parser.parse_args(argv)

    import httpx

    with httpx.Client(base_url=args.base, timeout=15) as http:
        problems = check(http, socket_connector(args.base), args.origin)

    print("ok" if not problems else "\n".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
