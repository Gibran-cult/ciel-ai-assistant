"""Pengaturan layanan Ciel Agent API dari environment server.

Semua nilai dibaca sekali saat proses mulai. Nilai yang kosong atau rusak
tidak membuat proses mati: layanan tetap hidup dan /healthz menyebut nama
variabelnya, tanpa pernah menyebut isinya.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from agent_api.limits import AgentConfig, load_config

REQUIRED_TEXT = (
    "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
    "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "AGENT_GOOGLE_REDIRECT_URI",
)
REQUIRED_LISTS = ("AGENT_DEVICE_REDIRECTS", "AGENT_WS_ORIGINS")
# Kunci heksadesimal: (nama, panjang minimal dalam byte, panjang persis atau None)
KEYS = (("AGENT_TICKET_KEY", 32, 32), ("AGENT_CHAIN_KEY", 32, None), ("AGENT_STATE_KEY", 32, None))
VERSION_RE = re.compile(r"(\d{1,4})\.(\d{1,4})\.(\d{1,4})")


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_key: str
    anthropic_key: str
    gemini_key: str
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    device_redirects: frozenset
    ws_origins: frozenset
    ticket_keys: tuple        # seed Ed25519 32 byte; yang pertama menandatangani
    chain_key: bytes
    state_key: bytes
    switch_file: str
    min_client_version: tuple
    agent: AgentConfig


def text(env, name):
    value = env.get(name)
    return value.strip() if isinstance(value, str) and value.strip() else None


def key_bytes(value, minimum, exact):
    try:
        raw = bytes.fromhex(value)
    except (TypeError, ValueError):
        return None

    if len(raw) < minimum or (exact is not None and len(raw) != exact):
        return None

    return raw


def load_settings(env: Mapping) -> tuple:
    """(Settings, []) kalau lengkap, atau (None, nama variabel yang bermasalah)."""

    if not isinstance(env, Mapping):
        return None, ["environment"]

    missing = [name for name in REQUIRED_TEXT if text(env, name) is None]
    lists = {}

    for name in REQUIRED_LISTS:
        value = text(env, name)
        items = frozenset(item.strip() for item in value.split(",") if item.strip()) if value else frozenset()

        if not items:
            missing.append(name)

        lists[name] = items

    keys = {}

    for name, minimum, exact in KEYS:
        keys[name] = key_bytes(text(env, name), minimum, exact)

        if keys[name] is None:
            missing.append(name)

    old = None

    if text(env, "AGENT_TICKET_KEY_OLD") is not None:
        old = key_bytes(text(env, "AGENT_TICKET_KEY_OLD"), 32, 32)

        if old is None:
            missing.append("AGENT_TICKET_KEY_OLD")

    version = VERSION_RE.fullmatch(text(env, "AGENT_MIN_CLIENT_VERSION") or "0.0.0")

    if version is None:
        missing.append("AGENT_MIN_CLIENT_VERSION")

    if missing:
        return None, missing

    return Settings(
        supabase_url=text(env, "SUPABASE_URL"),
        supabase_key=text(env, "SUPABASE_SERVICE_KEY"),
        anthropic_key=text(env, "ANTHROPIC_API_KEY"),
        gemini_key=text(env, "GEMINI_API_KEY"),
        google_client_id=text(env, "GOOGLE_CLIENT_ID"),
        google_client_secret=text(env, "GOOGLE_CLIENT_SECRET"),
        google_redirect_uri=text(env, "AGENT_GOOGLE_REDIRECT_URI"),
        device_redirects=lists["AGENT_DEVICE_REDIRECTS"],
        ws_origins=lists["AGENT_WS_ORIGINS"],
        ticket_keys=(keys["AGENT_TICKET_KEY"],) + ((old,) if old else ()),
        chain_key=keys["AGENT_CHAIN_KEY"],
        state_key=keys["AGENT_STATE_KEY"],
        switch_file=text(env, "AGENT_SWITCH_FILE") or "/data/agent_off",
        min_client_version=tuple(int(part) for part in version.groups()),
        agent=load_config({name: value for name, value in env.items() if isinstance(value, str)}),
    ), []
