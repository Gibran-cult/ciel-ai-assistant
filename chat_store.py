"""Riwayat chat dan proyek tersimpan untuk pengguna yang login (Supabase lewat REST).

Satu baris tabel `chats` per percakapan dan satu baris tabel `projects` per
proyek sidebar, keduanya dengan kunci (owner, id). Pemilik
selalu memory_owner_id() dari app, tidak pernah input pengguna, dan setiap
permintaan memfilter `owner=eq.<owner>` supaya satu akun tidak bisa membaca
atau menghapus data akun lain. Service key hanya ada di secrets server;
tabelnya memakai RLS tanpa policy (lihat docs/chat_store.sql), jadi anon key
Supabase tidak bisa membacanya.

Kegagalan jaringan atau database tidak pernah melempar error ke app: fungsi
mengembalikan None/False dan mencatatnya di log, supaya chat tetap jalan.
"""

import base64
import logging
import re
from datetime import datetime, timezone

import requests

from account_settings import clean_profile

logger = logging.getLogger("ciel_ai.chat_store")

OWNER_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
# ID chat dan proyek: potongan uuid4().hex dari app.
ROW_ID_PATTERN = re.compile(r"^[A-Za-z0-9]{1,32}$")

# Batas jumlah baris per tabel yang dimuat saat sesi dimulai.
LOAD_LIMIT = 200

# Thumbnail yang terkirim berukuran puluhan KB. Foto asli dari pesan yang gagal
# (disimpan di sesi untuk tombol Coba lagi) bisa sampai 5 MB dan tidak disimpan.
MAX_STORED_IMAGE_BYTES = 256 * 1024

TIMEOUT = 15

# Dipanggil di jalur kirim pesan, jadi Supabase yang lambat tidak boleh
# menahan jawaban lama: lewat batas ini app memakai hitungan di proses.
RATE_LIMIT_TIMEOUT = 3


def encode_message(message):
    """Pesan sesi -> JSON: tanpa payload, gambar sebagai base64."""

    stored = {key: value for key, value in message.items() if key not in ("payload", "images")}
    stored["content"] = str(message.get("content", ""))

    images = [
        {
            "name": image["name"],
            "mime": image["mime"],
            "data": base64.b64encode(image["data"]).decode("ascii"),
        }
        for image in message.get("images") or []
        if len(image["data"]) <= MAX_STORED_IMAGE_BYTES
    ]

    if message.get("role") == "user":
        stored["images"] = images

    return stored


def decode_message(stored):
    message = dict(stored)

    if "images" in stored:
        message["images"] = [
            {**image, "data": base64.b64decode(image["data"])}
            for image in stored["images"]
        ]

    return message


def to_row(owner, chat):
    # Tabel CSV/TSV lampiran tidak disimpan (besar); pengguna mengunggah
    # ulang untuk analisis lanjutan setelah memuat ulang halaman.
    return {
        "owner": owner,
        "id": chat["id"],
        "title": chat["title"],
        "project_id": chat.get("project_id"),
        "archived": bool(chat.get("archived")),
        "updated": chat["updated"],
        "messages": [encode_message(m) for m in chat["messages"]],
    }


def from_row(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "project_id": row.get("project_id"),
        "archived": bool(row.get("archived")),
        "updated": row["updated"],
        "messages": [decode_message(m) for m in row.get("messages") or []],
    }


def to_project_row(owner, project):
    # Ukuran file sudah dibatasi app saat upload (MAX_PROJECT_CHARS), jadi
    # isi file disimpan apa adanya, termasuk tabel CSV/TSV untuk analisis.
    return {
        "owner": owner,
        "id": project["id"],
        "name": project["name"],
        "created": project["created"],
        "files": project["files"],
    }


def from_project_row(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "created": row["created"],
        "files": list(row.get("files") or []),
    }


class ChatStore:

    def __init__(self, url, service_key):
        self.base = f"{url.rstrip('/')}/rest/v1"
        self.headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        }

    def _request(self, method, action, owner, table="chats", row_id=None, **kwargs):
        """Kirim satu permintaan untuk pemilik ini. Kembalikan response atau None."""

        if not OWNER_PATTERN.match(owner or ""):
            logger.error("chat_store_rejected action=%s reason=owner", action)
            return None

        if row_id is not None and not ROW_ID_PATTERN.match(str(row_id)):
            logger.error("chat_store_rejected action=%s reason=id", action)
            return None

        params = {"owner": f"eq.{owner}", **kwargs.pop("params", {})}

        if row_id is not None:
            params["id"] = f"eq.{row_id}"

        try:
            response = requests.request(
                method,
                f"{self.base}/{table}",
                headers={**self.headers, **kwargs.pop("headers", {})},
                params=params,
                timeout=TIMEOUT,
                **kwargs,
            )
            response.raise_for_status()

        except requests.exceptions.RequestException as error:
            logger.error(
                "chat_store_error action=%s type=%s error=%s",
                action,
                type(error).__name__,
                error,
            )
            return None

        return response

    def _load(self, action, owner, table, order, from_row):
        """Semua baris milik pemilik ({id: item}), atau None jika gagal."""

        response = self._request(
            "GET",
            action,
            owner,
            table,
            params={"select": "*", "order": order, "limit": str(LOAD_LIMIT)},
        )

        if response is None:
            return None

        try:
            items = [from_row(row) for row in response.json()]
        except (ValueError, KeyError, TypeError) as error:
            logger.error("chat_store_error action=%s type=%s error=%s", action, type(error).__name__, error)
            return None

        return {item["id"]: item for item in items}

    def _upsert(self, action, table, row, resolution="merge-duplicates"):
        # Upsert lewat primary key (owner, id), atau owner saja untuk profil:
        # PostgREST tidak memakai filter di POST, jadi kuncinya ada di badan
        # baris dan divalidasi di sini.
        if not OWNER_PATTERN.match(row["owner"] or "") or ("id" in row and not ROW_ID_PATTERN.match(str(row["id"]))):
            logger.error("chat_store_rejected action=%s", action)
            return False

        try:
            response = requests.post(
                f"{self.base}/{table}",
                headers={**self.headers, "Prefer": f"resolution={resolution},return=minimal"},
                json=row,
                timeout=TIMEOUT,
            )
            response.raise_for_status()

        except requests.exceptions.RequestException as error:
            logger.error("chat_store_error action=%s type=%s error=%s", action, type(error).__name__, error)
            return False

        return True

    def load(self, owner):
        return self._load("load", owner, "chats", "updated.desc", from_row)

    def save(self, owner, chat):
        return self._upsert("save", "chats", to_row(owner, chat))

    def delete(self, owner, chat_id):
        return self._request("DELETE", "delete", owner, row_id=chat_id) is not None

    def delete_all(self, owner):
        return self._request("DELETE", "delete_all", owner) is not None

    def load_projects(self, owner):
        return self._load("load_projects", owner, "projects", "created.asc", from_project_row)

    def save_project(self, owner, project):
        return self._upsert("save_project", "projects", to_project_row(owner, project))

    def delete_project(self, owner, project_id):
        return self._request("DELETE", "delete_project", owner, "projects", row_id=project_id) is not None

    def load_profile(self, owner):
        """Profil Pengaturan akun ini (kosong jika belum diisi), atau None jika gagal."""

        response = self._request(
            "GET",
            "load_profile",
            owner,
            "profiles",
            params={"select": "full_name,nickname,field,preferences", "limit": "1"},
        )

        if response is None:
            return None

        try:
            rows = response.json()
            return clean_profile(rows[0] if rows else {})
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            logger.error("chat_store_error action=load_profile type=%s error=%s", type(error).__name__, error)
            return None

    def save_profile(self, owner, profile):
        return self._upsert("save_profile", "profiles", {"owner": owner, **clean_profile(profile)})

    def delete_profile(self, owner):
        return self._request("DELETE", "delete_profile", owner, "profiles") is not None

    def delete_account(self, owner):
        """Hapus chat, proyek, dan profil akun ini. Semua dicoba walau ada yang gagal.

        Catatan pembelian (pro_orders, pro_members) dan bukti persetujuan
        (consents) tidak ikut dihapus; lihat docs/chat_store.sql.
        """
        results = [
            self.delete_all(owner),
            self._request("DELETE", "delete_projects", owner, "projects") is not None,
            self.delete_profile(owner),
        ]
        return all(results)

    def load_consent(self, owner):
        """Versi ketentuan terbaru yang disetujui akun ini ("" jika belum ada), atau None jika gagal."""

        response = self._request(
            "GET",
            "load_consent",
            owner,
            "consents",
            params={"select": "version", "order": "accepted_at.desc", "limit": "1"},
        )

        if response is None:
            return None

        try:
            rows = response.json()
            return str(rows[0]["version"]) if rows else ""
        except (ValueError, KeyError, TypeError, AttributeError, IndexError) as error:
            logger.error("chat_store_error action=load_consent type=%s error=%s", type(error).__name__, error)
            return None

    def save_consent(self, owner, version):
        # Persetujuan pertama untuk versi ini yang dipakai sebagai bukti, jadi
        # baris yang sudah ada tidak ditimpa.
        return self._upsert("save_consent", "consents", {"owner": owner, "version": version}, "ignore-duplicates")

    def load_pro_until(self, owner):
        """
        Akhir masa Pro akun ini (epoch detik), 0.0 jika tidak pernah Pro,
        atau None jika gagal dibaca. Tabel `pro_members` hanya diisi admin
        (SQL) atau webhook pembayaran, tidak pernah oleh app.
        """

        response = self._request(
            "GET",
            "load_pro_until",
            owner,
            "pro_members",
            params={"select": "expires_at"},
        )

        if response is None:
            return None

        try:
            rows = response.json()
            return pro_until_from_rows(rows)
        except (ValueError, KeyError, TypeError) as error:
            logger.error("chat_store_error action=load_pro_until type=%s error=%s", type(error).__name__, error)
            return None

    def create_order(self, owner, order_id, amount, provider="midtrans"):
        """Order Pro baru (status 'pending'). Hanya Edge Function yang menandainya lunas."""
        return self._upsert(
            "create_order",
            "pro_orders",
            {"owner": owner, "id": order_id, "amount": int(amount), "status": "pending", "provider": provider},
        )

    def attach_order_ref(self, owner, order_id, ref, tx):
        """Simpan id payment request dan transaksi Mayar, supaya webhooknya bisa dicocokkan ke order."""

        response = self._request(
            "PATCH",
            "attach_order_ref",
            owner,
            "pro_orders",
            row_id=order_id,
            json={"provider_ref": ref, "provider_tx": tx},
            headers={"Prefer": "return=minimal"},
        )
        return response is not None

    def load_latest_order(self, owner):
        """
        Order Pro terakhir akun ini ({id, status, created_at, provider, ref}),
        {} jika belum pernah membeli, None jika gagal dibaca. Dipakai saat
        pengguna kembali dari halaman bayar, tanpa mempercayai parameter URL.
        """

        response = self._request(
            "GET",
            "load_latest_order",
            owner,
            "pro_orders",
            params={"select": "id,status,created_at,provider,provider_ref", "order": "created_at.desc", "limit": "1"},
        )

        if response is None:
            return None

        try:
            rows = response.json()
            if not rows:
                return {}
            row = rows[0]
            return {
                "id": row["id"],
                "status": row["status"],
                "created_at": parse_timestamp(row["created_at"]),
                "provider": row.get("provider") or "midtrans",
                "ref": row.get("provider_ref"),
            }
        except (ValueError, KeyError, TypeError) as error:
            logger.error("chat_store_error action=load_latest_order type=%s error=%s", type(error).__name__, error)
            return None

    def rate_limit_hit(self, limits, now):
        """
        Hitung dan catat satu pesan di database (fungsi ciel_rate_limit_hit),
        supaya batas bertahan saat app restart. `limits` = {key: (batas,
        jendela_detik)}. Kembalikan (True, None) jika boleh, (True, key) jika
        key itu penuh, atau (False, None) jika Supabase tidak terjangkau.
        """

        try:
            response = requests.post(
                f"{self.base}/rpc/ciel_rate_limit_hit",
                headers=self.headers,
                json={"p_limits": [[key, limit, window] for key, (limit, window) in limits.items()], "p_now": now},
                timeout=RATE_LIMIT_TIMEOUT,
            )
            response.raise_for_status()
            full = response.json()

            # Hanya null (boleh) atau nama key (penuh) yang berarti.
            if full is not None and not isinstance(full, str):
                raise TypeError(f"unexpected response {type(full).__name__}")

        except (requests.exceptions.RequestException, ValueError, TypeError) as error:
            logger.error("chat_store_error action=rate_limit_hit type=%s error=%s", type(error).__name__, error)
            return False, None

        return True, full


# timestamptz dari PostgREST: pecahan detik 0-6 digit dan zona "+00:00" atau
# "Z". datetime.fromisoformat di Python 3.10 hanya menerima 3 atau 6 digit.
TIMESTAMP_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}(?::?\d{2})?)?$"
)


def parse_timestamp(text):
    """Teks timestamptz -> epoch detik. Tanpa zona dianggap UTC."""

    match = TIMESTAMP_PATTERN.match(str(text).strip())

    if not match:
        raise ValueError(f"timestamp tidak dikenali: {text!r}")

    day, clock, fraction, zone = match.groups()
    moment = datetime.fromisoformat(f"{day}T{clock}").replace(
        microsecond=int((fraction or "0").ljust(6, "0")),
        tzinfo=timezone.utc,
    )

    if zone and zone != "Z":
        sign = -1 if zone[0] == "-" else 1
        digits = zone[1:].replace(":", "")
        offset = int(digits[:2]) * 3600 + int(digits[2:4] or 0) * 60
        return moment.timestamp() - sign * offset

    return moment.timestamp()


def pro_until_from_rows(rows):
    """[{"expires_at": "2026-11-17T00:00:00+00:00"}] -> epoch detik; [] -> 0.0."""

    if not rows:
        return 0.0

    return parse_timestamp(rows[0]["expires_at"])
