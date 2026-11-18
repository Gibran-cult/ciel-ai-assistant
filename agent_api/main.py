"""Layanan Ciel Agent API (docs/agent-architecture.md bagian 6).

`create_app` menerima semua dependensi luar sebagai argumen, jadi uji
memakai tiruan dan tidak pernah menyentuh jaringan.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from agent_api.tickets import TicketSigner


def create_app(settings, *, store, models, google, clock, missing=()):
    """Aplikasi FastAPI. `settings` None berarti pengaturan belum lengkap."""

    app = FastAPI(title="Ciel Agent API", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/healthz")
    def healthz():
        if settings is None:
            return JSONResponse({"ok": False, "missing": list(missing)}, status_code=503)

        return {"ok": True}

    if settings is None:
        return app

    signer = TicketSigner(settings.ticket_keys)

    @app.get("/v1/ticket-keys")
    def ticket_keys():
        return {"keys": signer.public_keys()}

    return app
