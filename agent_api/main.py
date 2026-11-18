"""Layanan Ciel Agent API (docs/agent-architecture.md bagian 6).

`create_app` menerima semua dependensi luar sebagai argumen, jadi uji
memakai tiruan dan tidak pernah menyentuh jaringan.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from agent_api.devices import device_router
from agent_api.tickets import TicketSigner
from agent_api.ws import TaskRunner, ws_router


def create_app(settings, *, store, models, google, clock, missing=()):
    """Aplikasi FastAPI. `settings` None berarti pengaturan belum lengkap."""

    runner = TaskRunner(store)

    @asynccontextmanager
    async def lifespan(app):
        # Pembersih tugas macet berjalan selama proses hidup.
        sweeper = asyncio.create_task(runner.sweep_forever()) if settings is not None else None
        yield

        if sweeper is not None:
            sweeper.cancel()

    app = FastAPI(title="Ciel Agent API", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.runner = runner
    app.state.models = models

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

    app.include_router(device_router(settings, store, google, clock))
    app.include_router(ws_router(settings, store, models, signer, runner, clock))

    return app
