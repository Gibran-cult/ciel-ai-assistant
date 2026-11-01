"""Isi halaman Pengaturan: profil pengguna, tab, dan ekspor riwayat chat.

Profil (nama lengkap, nama panggilan, bidang studi, preferensi jawaban) diisi
pengguna sendiri, lalu dipakai untuk sapaan Beranda dan dikirim ke Langflow
sebagai blok konteks di depan pesan chat biasa. Semua field satu baris, jadi
isian pengguna tidak bisa membuka bagian "###" baru di pesan itu. Rendering
ada di app.py.
"""

import json
import unicodedata
from datetime import datetime, timezone


PROFILE_LIMITS = {"full_name": 80, "nickname": 30, "field": 80, "preferences": 300}

# (id, label, ikon Material), urutan tetap. Tab di LOGIN_TABS butuh login.
SETTINGS_TABS = (
    ("profil", "Profil", ":material/person:"),
    ("tampilan", "Tampilan", ":material/contrast:"),
    ("data", "Data saya", ":material/database:"),
    ("paket", "Paket", ":material/sell:"),
    ("privasi", "Privasi", ":material/shield:"),
    ("ketentuan", "Ketentuan", ":material/gavel:"),
)
LOGIN_TABS = frozenset({"profil", "data"})

# Alamat lama (?page=pricing, ?page=privacy) tetap dipakai landing dan
# Midtrans, jadi dibuka sebagai tab Pengaturan, begitu juga ?page=terms.
PAGE_TABS = {"pricing": "paket", "privacy": "privasi", "terms": "ketentuan"}


def _clean_text(value, limit):
    if not isinstance(value, str):
        return ""

    kept = "".join(
        " " if char.isspace() else char
        for char in value
        if char.isspace() or unicodedata.category(char) != "Cc"
    )
    return " ".join(kept.split())[:limit]


def clean_profile(raw):
    """Profil dengan keempat field, string satu baris sesuai batas panjang."""

    raw = raw or {}
    return {key: _clean_text(raw.get(key), limit) for key, limit in PROFILE_LIMITS.items()}


def display_name(profile, account_name):
    """Nama di sidebar: nama lengkap dari profil, atau nama akun Google."""
    return profile.get("full_name") or account_name


def call_name(profile, account_name):
    """Cara Ciel memanggil pengguna: nama panggilan utuh, atau kata pertama nama."""

    if profile.get("nickname"):
        return profile["nickname"]

    words = (profile.get("full_name") or account_name or "").split()
    return words[0] if words else ""


def profile_context(profile):
    """Blok profil untuk di depan pesan ke Langflow, atau "" jika profil kosong."""

    lines = [
        f"{label}: {profile[key]}"
        for key, label in (
            ("nickname", "Panggil pengguna"),
            ("full_name", "Nama lengkap"),
            ("field", "Bidang studi"),
            ("preferences", "Preferensi jawaban"),
        )
        if profile.get(key)
    ]

    if not lines:
        return ""

    return (
        "### Profil pengguna (diisi pengguna di Pengaturan)\n"
        + "\n".join(lines)
        + "\nIkuti profil ini selama tidak bertentangan dengan aturanmu soal sumber dan kejujuran.\n\n"
        "### Pesan\n"
    )


def settings_tab(page, tab, logged_in):
    """Tab Pengaturan yang ditampilkan untuk ?page= dan ?tab= ini."""

    allowed = [key for key, _, _ in SETTINGS_TABS if logged_in or key not in LOGIN_TABS]
    chosen = PAGE_TABS.get(page) or tab
    return chosen if chosen in allowed else allowed[0]


def export_chats_json(chats):
    """Riwayat chat sebagai JSON untuk diunduh: judul, waktu, dan teks pesan saja."""

    exported = [
        {
            "title": chat["title"],
            "updated": datetime.fromtimestamp(chat["updated"], timezone.utc).isoformat(),
            "messages": [
                {"role": message["role"], "content": str(message.get("content", ""))}
                for message in chat["messages"]
            ],
        }
        for chat in sorted(chats.values(), key=lambda chat: chat["updated"], reverse=True)
    ]
    return json.dumps(exported, ensure_ascii=False, indent=2)
