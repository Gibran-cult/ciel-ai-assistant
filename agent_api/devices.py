"""Pendaftaran perangkat dan tokennya (docs/security.md bagian 7, keputusan D13).

Alurnya:
1. Perangkat membuka /v1/device/login dengan tantangan PKCE dan alamat
   kembali yang terdaftar. Layanan menyimpan keduanya di state bertanda
   tangan HMAC, lalu mengarahkan ke Google.
2. Google kembali ke /v1/device/callback. Layanan menukar kodenya,
   menghitung ID pemilik dari `sub`, lalu memberi kode perangkat sekali
   pakai (60 detik) ke alamat kembali tadi.
3. Perangkat menukar kode itu dengan verifier PKCE di /v1/device/token
   dan menerima token akses (15 menit) dan token pembaruan.

Token selalu berbentuk "<awalan>.<pemilik>.<acak>" dan hanya hash SHA-256
dari seluruh string yang disimpan. Karena pemiliknya ada di dalam token,
pencarian token tetap difilter pemilik seperti kueri lain.
"""

import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from account_ids import owner_from_subject
from chat_store import OWNER_PATTERN

logger = logging.getLogger("ciel.agent_api.devices")

STATE_SECONDS = 600
CODE_SECONDS = 60
ACCESS_SECONDS = 900
REFRESH_SECONDS = 30 * 86400
ADDRESS_LIMIT = (10, 600)   # permintaan login per IP per 10 menit

PREFIXES = {"code": "cdc1", "access": "cat1", "refresh": "crt1"}
CHALLENGE_RE = re.compile(r"[A-Za-z0-9_-]{43}")
CLIENT_STATE_RE = re.compile(r"[A-Za-z0-9._~-]{1,128}")


class TokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(max_length=200)
    verifier: str = Field(pattern=r"^[A-Za-z0-9._~-]{43,128}$")
    name: str = Field(min_length=1, max_length=60)
    platform: Literal["extension", "desktop"]


def b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def unb64url(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def new_token(kind, owner):
    """(token, hash) baru untuk pemilik ini."""

    token = f"{PREFIXES[kind]}.{owner}.{secrets.token_urlsafe(32)}"
    return token, token_hash(token)


def parse_token(token, kind):
    """(pemilik, hash) kalau awalan cocok dengan jenisnya dan pemiliknya sah, atau None."""

    if not isinstance(token, str) or len(token) > 200:
        return None

    parts = token.split(".")

    if len(parts) != 3 or parts[0] != PREFIXES.get(kind) or not OWNER_PATTERN.match(parts[1]) or not parts[2]:
        return None

    return parts[1], token_hash(token)


def sign_state(key, payload):
    body = b64url(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    return f"{body}.{b64url(hmac.new(key, body.encode(), hashlib.sha256).digest())}"


def read_state(key, state, now):
    """Isi state kalau tanda tangannya cocok dan belum kedaluwarsa, atau None."""

    if not isinstance(state, str) or state.count(".") != 1:
        return None

    body, mac = state.split(".")
    expected = b64url(hmac.new(key, body.encode(), hashlib.sha256).digest())

    if not hmac.compare_digest(mac, expected):
        return None

    try:
        payload = json.loads(unb64url(body))
    except ValueError:
        return None

    if not isinstance(payload, dict) or type(payload.get("exp")) is not int or payload["exp"] < now:
        return None

    return payload


def iso(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def expired(row, now):
    try:
        return datetime.fromisoformat(row["expires_at"]).timestamp() <= now
    except (KeyError, TypeError, ValueError):
        return True


def refuse(status, error):
    return JSONResponse({"error": error}, status_code=status)


def issue_pair(store, owner, device, now):
    """Token akses dan pembaruan baru untuk perangkat ini, atau None kalau gagal disimpan."""

    access, access_hash = new_token("access", owner)
    refresh, refresh_hash = new_token("refresh", owner)

    if not store.save_token(owner, access_hash, "access", iso(now + ACCESS_SECONDS), device=device):
        return None

    if not store.save_token(owner, refresh_hash, "refresh", iso(now + REFRESH_SECONDS), device=device):
        return None

    return {"device": device, "access_token": access, "refresh_token": refresh, "expires_in": ACCESS_SECONDS}


def device_router(settings, store, google, clock):
    router = APIRouter()

    def now():
        return int(clock().timestamp())

    def address_limit(request):
        """Jawaban penolakan kalau alamat ini terlalu sering, atau None."""

        address = request.client.host if request.client else "unknown"
        reached, full = store.rate_limit_hit({f"agent-ip:{address}": ADDRESS_LIMIT}, now())

        if reached is not True:
            return refuse(503, "unavailable")

        return refuse(429, "rate_limited") if full else None

    @router.get("/v1/device/login")
    def login(request: Request, challenge: str = "", redirect: str = "", state: str = ""):
        limited = address_limit(request)

        if limited:
            return limited

        if not CHALLENGE_RE.fullmatch(challenge) or redirect not in settings.device_redirects or not CLIENT_STATE_RE.fullmatch(state):
            return refuse(400, "bad_request")

        nonce = secrets.token_urlsafe(16)
        signed = sign_state(settings.state_key, {"c": challenge, "r": redirect, "s": state, "n": nonce, "exp": now() + STATE_SECONDS})
        return RedirectResponse(google.auth_url(signed, nonce), status_code=302)

    @router.get("/v1/device/callback")
    def callback(request: Request, code: str = "", state: str = ""):
        limited = address_limit(request)

        if limited:
            return limited

        payload = read_state(settings.state_key, state, now())

        if payload is None or not code:
            return refuse(400, "bad_request")

        owner = owner_from_subject(google.subject(code, payload.get("n"), now()))

        if not owner:
            return refuse(400, "login_failed")

        device_code, code_hash = new_token("code", owner)

        if not store.save_token(owner, code_hash, "code", iso(now() + CODE_SECONDS), challenge=payload["c"], redirect=payload["r"]):
            return refuse(503, "unavailable")

        separator = "&" if "?" in payload["r"] else "?"
        return RedirectResponse(payload["r"] + separator + urlencode({"code": device_code, "state": payload["s"]}), status_code=302)

    @router.post("/v1/device/token")
    async def token(request: Request):
        limited = address_limit(request)

        if limited:
            return limited

        try:
            body = TokenRequest.model_validate(await request.json())
        except (ValidationError, ValueError):
            return refuse(400, "bad_request")

        parsed = parse_token(body.code, "code")

        if parsed is None:
            return refuse(400, "invalid_grant")

        owner, code_hash = parsed
        # Kode dipakai lebih dulu, sebelum verifier dicek: tebakan verifier
        # yang salah tetap menghabiskan kodenya.
        row = store.use_token(owner, code_hash)
        proof = b64url(hashlib.sha256(body.verifier.encode()).digest())

        if (row is None or row.get("kind") != "code" or expired(row, now())
                or not hmac.compare_digest(str(row.get("challenge")), proof)):
            return refuse(400, "invalid_grant")

        device = secrets.token_hex(8)

        if not store.create_device(owner, device, body.name, body.platform):
            return refuse(503, "unavailable")

        tokens = issue_pair(store, owner, device, now())

        if tokens is None:
            return refuse(503, "unavailable")

        logger.info("device_registered owner=%s device=%s platform=%s", owner, device, body.platform)
        return tokens

    return router
