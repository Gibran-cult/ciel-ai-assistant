"""Log aksi agent (docs/security.md bagian 3).

Setiap aksi dicatat sebagai satu AuditEvent. Setiap catatan menyimpan hash
yang dihitung dari hash catatan sebelumnya, jadi catatan yang diubah,
dihapus, atau ditukar urutannya akan ketahuan saat rantainya diperiksa.

Yang dicatat hanya target (host, nama aplikasi, atau nama file), tidak
pernah isi halaman, isi file, atau teks rahasia.
"""

import hashlib
import hmac
import json
import re
from dataclasses import asdict, dataclass

from guard.domains import normalize_host
from guard.risk import find_secrets


@dataclass(frozen=True)
class AuditEvent:
    owner: str
    device: str
    task: str
    seq: int
    kind: str
    target: str
    level: str                 # "R0" sampai "R3"
    decision: str              # "allow" | "confirm" | "block" | "handover"
    reason: str | None
    approved_by: str | None    # siapa yang menyetujui, kalau ada konfirmasi
    result: str | None
    at: str                    # waktu ISO 8601, UTC. Disimpan persis seperti ini (kolom teks)


MIN_KEY = 16   # byte


def chain_hash(prev_hash, event, key=None):
    """Hash satu catatan, dihitung dari hash catatan sebelumnya.

    Dengan key (rahasia server), hasilnya HMAC: orang yang bisa menulis ke
    tabel log tetap tidak bisa menghitung ulang rantainya. Tanpa key, hasilnya
    SHA-256 biasa, yang hanya mendeteksi perubahan tak sengaja.
    """

    canonical = json.dumps(asdict(event), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    data = (prev_hash + "\n" + canonical).encode("utf-8")

    if key is None:
        return hashlib.sha256(data).hexdigest()

    if not isinstance(key, bytes) or len(key) < MIN_KEY:
        raise ValueError("kunci rantai log harus bytes, minimal 16 byte")

    return hmac.new(key, data, hashlib.sha256).hexdigest()


def verify_chain(rows, first_prev="", head=None, key=None):
    """Indeks baris pertama yang hash-nya tidak cocok, atau None kalau rantai utuh.

    rows: daftar (AuditEvent, hash tersimpan), urut dari yang paling lama.
    head: hash catatan terakhir yang disimpan terpisah. Kalau diberikan,
    baris terakhir yang dipotong ikut ketahuan: hasilnya len(rows), yaitu
    indeks baris pertama yang hilang.
    """

    prev = first_prev

    for index, (event, stored) in enumerate(rows):
        if chain_hash(prev, event, key) != stored:
            return index

        prev = stored

    if head is not None and prev != head:
        return len(rows)

    return None


def redact(text, limit=120):
    """Teks yang aman untuk log: rahasia diganti, lalu dipotong."""

    if not isinstance(text, str):
        return ""

    for start, end, _ in reversed(find_secrets(text)):
        text = text[:start] + "[disaring]" + text[end:]

    return text[:limit]


def target_of(action):
    """Target aksi untuk log: host, nama aplikasi, atau folder dan nama file."""

    # Hanya nama host yang sah yang dicatat. Teks lain di kolom host bisa
    # memuat jalur dan parameter kueri, dan itu tidak boleh masuk log.
    host = normalize_host(action.host)

    if host:
        return host

    if isinstance(action.app, str) and action.app:
        return action.app.lower()

    if isinstance(action.path, str):
        parts = [part for part in re.split(r"[\\/]", action.path) if part]
        return "/".join(parts[-2:])

    return ""
