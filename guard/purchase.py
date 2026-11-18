"""Ringkasan pembelian dan token konfirmasinya (docs/security.md bagian 4).

Pengguna menyetujui satu ringkasan: toko, barang, harga, ongkir, total.
Token konfirmasi mengikat persetujuan itu ke isi ringkasan, ke akun, dan ke
waktu. Kalau harga berubah setelah disetujui, token lama tidak berlaku dan
konfirmasi harus diulang.

Token berbentuk "kedaluwarsa.nonce.mac". Yang menyimpan nonce terpakai
adalah pemanggil (tabel purchase_confirmations).
"""

import hashlib
import hmac
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime

PURCHASE_TTL = 600   # detik
MIN_SECRET = 16      # byte; rahasia yang lebih pendek dianggap salah konfigurasi
MAC_RE = re.compile(r"[0-9a-f]{64}")
NONCE_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")


@dataclass(frozen=True)
class Item:
    name: str
    variant: str
    qty: int
    unit_price: int


@dataclass(frozen=True)
class PurchaseSummary:
    store_domain: str
    store_name: str
    badge_text: str
    items: tuple[Item, ...]
    shipping: int
    fees: int
    discount: int
    total: int


def whole(value):
    """Rupiah bulat yang tidak negatif. bool dan float ditolak."""

    return type(value) is int and value >= 0


def totals_consistent(summary):
    """Benar kalau total sama dengan jumlah bagian-bagiannya."""

    try:
        items = summary.items

        if not isinstance(items, tuple) or not items:
            return False

        # Kolom teks ikut ditandatangani dan ditampilkan ke pengguna, jadi
        # harus benar-benar teks. Label dan varian boleh kosong.
        if not isinstance(summary.store_domain, str) or not summary.store_domain:
            return False

        if not isinstance(summary.store_name, str) or not isinstance(summary.badge_text, str):
            return False

        subtotal = 0

        for item in items:
            if not isinstance(item, Item) or not whole(item.qty) or item.qty < 1 or not whole(item.unit_price):
                return False

            if not isinstance(item.name, str) or not item.name or not isinstance(item.variant, str):
                return False

            subtotal += item.qty * item.unit_price

        amounts = (summary.shipping, summary.fees, summary.discount, summary.total)

        if not all(whole(amount) for amount in amounts):
            return False

        return summary.total == subtotal + summary.shipping + summary.fees - summary.discount
    except AttributeError:
        return False


def summary_digest(summary):
    canonical = json.dumps(asdict(summary), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def seconds(now):
    """Detik sejak epoch, atau None untuk waktu tanpa zona.

    Waktu tanpa zona ditolak. Menebak zonanya bisa membuat token yang
    seharusnya berumur 10 menit tetap berlaku berjam-jam.
    """

    if not isinstance(now, datetime) or now.tzinfo is None:
        return None

    return int(now.timestamp())


def plain(value, forbidden):
    return isinstance(value, str) and value != "" and not any(char in value for char in forbidden)


def sign(summary, owner, exp, nonce, secret):
    """MAC untuk satu konfirmasi, atau None kalau ada masukan yang tidak bisa dipakai."""

    if not isinstance(secret, bytes) or len(secret) < MIN_SECRET:
        return None

    # "|" memisahkan kolom di pesan yang ditandatangani. Nonce hanya boleh
    # huruf, angka, "_" dan "-", jadi tidak bisa memuat pemisah atau baris baru.
    if not plain(owner, "|") or not isinstance(nonce, str) or not NONCE_RE.fullmatch(nonce):
        return None

    if not totals_consistent(summary):
        return None

    try:
        digest = summary_digest(summary)
    except (TypeError, ValueError):
        return None

    message = f"{owner}|{exp}|{nonce}|{digest}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def issue_confirmation(summary, owner, now, secret, nonce):
    """Token untuk ringkasan yang baru disetujui pengguna, atau None."""

    issued = seconds(now)

    if issued is None:
        return None

    exp = issued + PURCHASE_TTL
    mac = sign(summary, owner, exp, nonce, secret)
    return f"{exp}.{nonce}.{mac}" if mac else None


def check_confirmation(token, summary, owner, now, secret, used_nonces):
    """(True, None) kalau token sah untuk ringkasan ini, selain itu (False, alasan).

    Token datang dari klien, jadi bentuk apa pun yang tidak terduga
    dijawab "malformed" dan tidak pernah memicu exception.
    """

    try:
        return check_token(token, summary, owner, now, secret, used_nonces)
    except Exception:
        return False, "malformed"


def check_token(token, summary, owner, now, secret, used_nonces):
    current = seconds(now)

    if not isinstance(token, str) or current is None:
        return False, "malformed"

    parts = token.split(".")

    if len(parts) != 3:
        return False, "malformed"

    exp_text, nonce, mac = parts

    # 12 digit cukup untuk ribuan tahun dan mencegah angka raksasa.
    if not (exp_text.isascii() and exp_text.isdigit()) or len(exp_text) > 12:
        return False, "malformed"

    if not NONCE_RE.fullmatch(nonce) or not MAC_RE.fullmatch(mac):
        return False, "malformed"

    exp = int(exp_text)

    if current > exp:
        return False, "expired"

    if nonce in used_nonces:
        return False, "used"

    expected = sign(summary, owner, exp, nonce, secret)

    if expected is None or not hmac.compare_digest(expected.encode("ascii"), mac.encode("utf-8")):
        return False, "mismatch"

    return True, None
