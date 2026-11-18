"""Login Google untuk pendaftaran perangkat (keputusan D13).

Alur kode otorisasi biasa. Token ID tidak diperiksa tanda tangannya karena
diterima langsung dari endpoint token Google lewat TLS, dengan rahasia klien
(OpenID Connect Core 1.0 bagian 3.1.3.7). Yang tetap diperiksa: penerbit,
audiens, waktu kedaluwarsa, nonce, subjek, dan email yang terverifikasi.
"""

import base64
import json
import logging
from urllib.parse import urlencode

logger = logging.getLogger("ciel.agent_api.google")

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = frozenset({"https://accounts.google.com", "accounts.google.com"})
TIMEOUT = 10


def claims_of(id_token):
    """Isi token ID sebagai dict, atau None kalau bentuknya rusak."""

    parts = id_token.split(".") if isinstance(id_token, str) else []

    if len(parts) != 3:
        return None

    try:
        claims = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
    except ValueError:
        return None

    return claims if isinstance(claims, dict) else None


class GoogleClient:

    def __init__(self, session, client_id, client_secret, redirect_uri):
        self.session = session
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def auth_url(self, state, nonce):
        return AUTH_URL + "?" + urlencode({
            "client_id": self.client_id, "redirect_uri": self.redirect_uri, "response_type": "code",
            "scope": "openid email", "state": state, "nonce": nonce, "prompt": "select_account",
        })

    def subject(self, code, nonce, now):
        """`sub` akun Google untuk kode ini, atau None. Tidak pernah melempar exception."""

        try:
            response = self.session.post(TOKEN_URL, data={
                "code": code, "client_id": self.client_id, "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri, "grant_type": "authorization_code",
            }, timeout=TIMEOUT)

            if response.status_code >= 400:
                logger.warning("google_token_refused status=%s", response.status_code)
                return None

            claims = claims_of(response.json().get("id_token"))
        except Exception as error:
            logger.error("google_token_error type=%s", type(error).__name__)
            return None

        if claims is None:
            return None

        exp, sub = claims.get("exp"), claims.get("sub")
        checks = (
            claims.get("iss") in ISSUERS,
            claims.get("aud") == self.client_id,
            type(exp) is int and exp > now,
            isinstance(nonce, str) and claims.get("nonce") == nonce,
            isinstance(sub, str) and sub != "",
            claims.get("email_verified") is True,
        )

        if not all(checks):
            logger.warning("google_claims_refused failed=%s", [index for index, ok in enumerate(checks) if not ok])
            return None

        return sub
