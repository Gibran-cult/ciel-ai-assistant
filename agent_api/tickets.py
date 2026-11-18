"""Tiket aksi bertanda tangan Ed25519 (docs/agent-architecture.md bagian 6, keputusan D11).

Setiap aksi yang dikirim ke klien membawa tiket: tugas, perangkat, nomor
urut, tool, argumen, host yang dinilai guard, dan waktu kedaluwarsa. Server
menandatangani dengan kunci privat. Ekstensi dan desktop memeriksa dengan
kunci publik, jadi klien tidak pernah memegang rahasia yang bisa dipakai
untuk memalsukan tiket.

`verify_ticket` di sini adalah acuan untuk pemeriksaan di klien.
"""

import base64
import binascii
import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

TICKET_SECONDS = 60
SIGNED_KEYS = frozenset({"ticket", "kid", "sig"})


def b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def unb64url(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def canonical(ticket):
    """Bentuk tiket yang ditandatangani: JSON dengan kunci terurut, tanpa spasi."""

    return json.dumps(ticket, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def kid(public_key):
    return hashlib.sha256(public_key).hexdigest()[:16]


def make_ticket(task, device, seq, tool, args, host, now):
    return {"v": 1, "task": task, "device": device, "seq": seq, "tool": tool, "args": args, "host": host,
            "exp": now + TICKET_SECONDS}


class TicketSigner:
    """Seed pertama menandatangani. Semua seed muncul di daftar kunci publik (masa peralihan rotasi)."""

    def __init__(self, seeds):
        self.keys = [Ed25519PrivateKey.from_private_bytes(seed) for seed in seeds]
        self.publics = [key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw) for key in self.keys]

    def sign(self, ticket):
        return {"ticket": ticket, "kid": kid(self.publics[0]), "sig": b64url(self.keys[0].sign(canonical(ticket)))}

    def public_keys(self):
        return [{"kid": kid(public), "alg": "Ed25519", "key": b64url(public)} for public in self.publics]


def verify_ticket(signed, keys, *, task, device, last_seq, now):
    """Alasan tiket ditolak, atau None kalau sah. Tidak pernah melempar exception."""

    try:
        if not isinstance(signed, dict) or set(signed) != SIGNED_KEYS:
            return "bad_form"

        ticket, key_id, sig = signed["ticket"], signed["kid"], signed["sig"]

        if not isinstance(ticket, dict) or not isinstance(key_id, str) or not isinstance(sig, str):
            return "bad_form"

        public = next((entry for entry in keys if entry.get("kid") == key_id and entry.get("alg") == "Ed25519"), None)

        if public is None:
            return "unknown_key"

        try:
            Ed25519PublicKey.from_public_bytes(unb64url(public["key"])).verify(unb64url(sig), canonical(ticket))
        except (InvalidSignature, ValueError, binascii.Error, TypeError):
            return "bad_signature"

        if ticket.get("task") != task:
            return "wrong_task"

        if ticket.get("device") != device:
            return "wrong_device"

        seq, exp = ticket.get("seq"), ticket.get("exp")

        if type(seq) is not int or seq <= last_seq:
            return "old_seq"

        if type(exp) is not int or now > exp:
            return "expired"

        return None
    except Exception:
        return "bad_form"
