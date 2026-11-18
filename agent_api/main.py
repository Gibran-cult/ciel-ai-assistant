"""Layanan Ciel Agent API (docs/agent-architecture.md bagian 6).

`create_app` menerima semua dependensi luar sebagai argumen, jadi uji
memakai tiruan dan tidak pernah menyentuh jaringan.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from agent_api.devices import device_router
from agent_api.tickets import TicketSigner
from agent_api.ws import TaskRunner, ws_router


def build_app(env):
    """Aplikasi produksi dari environment. Tidak ada panggilan jaringan saat dibangun."""

    import anthropic
    import requests

    from agent_api.claude import ClaudeModel
    from agent_api.gemini import GeminiModel
    from agent_api.google import GoogleClient
    from agent_api.model import FallbackModel
    from agent_api.settings import load_settings
    from agent_api.store import AgentStore

    settings, missing = load_settings(env)

    # Satu-satunya jam sungguhan layanan ini. Semua bagian lain menerimanya
    # sebagai argumen, jadi uji bisa memakai jam tiruan.
    def clock():
        return datetime.now(timezone.utc)

    if settings is None:
        return create_app(None, store=None, models=None, google=None, clock=clock, missing=missing)

    session = requests.Session()
    claude = ClaudeModel(anthropic.Anthropic(api_key=settings.anthropic_key, timeout=60.0, max_retries=2))
    return create_app(
        settings,
        store=AgentStore(settings.supabase_url, settings.supabase_key),
        models=FallbackModel(claude, GeminiModel(session, settings.gemini_key)),
        google=GoogleClient(session, settings.google_client_id, settings.google_client_secret, settings.google_redirect_uri),
        clock=clock,
    )


def production_app():
    """Titik masuk Uvicorn (--factory agent_api.main:production_app)."""

    return build_app(os.environ)


def create_app(settings, *, store, models, google, clock, missing=()):
    """Aplikasi FastAPI. `settings` None berarti pengaturan belum lengkap."""

    runner = TaskRunner(store)

    @asynccontextmanager
    async def lifespan(app):
        # Pembersih tugas macet berjalan selama proses hidup.
        sweeper = asyncio.create_task(runner.maintain_forever(settings.chain_key, clock)) if settings is not None else None
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
