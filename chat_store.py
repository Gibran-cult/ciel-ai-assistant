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

import requests

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

    def _upsert(self, action, table, row):
        # Upsert lewat primary key (owner, id): PostgREST tidak memakai filter
        # di POST, jadi owner dan id ada di badan baris dan divalidasi di sini.
        if not OWNER_PATTERN.match(row["owner"] or "") or not ROW_ID_PATTERN.match(str(row["id"])):
            logger.error("chat_store_rejected action=%s", action)
            return False

        try:
            response = requests.post(
                f"{self.base}/{table}",
                headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
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
