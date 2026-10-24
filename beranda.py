"""Isi Beranda: template prompt, sapaan, dan waktu dalam WIB.

Beranda menggantikan halaman chat kosong. Template biasa mengisi kotak tanya
(bagian dalam kurung diganti mahasiswa sebelum dikirim); template Pro membuka
dialog fitur yang sudah ada (Riset Skripsi, Kerangka). Rendering ada di app.py.
"""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


RISET_KIND = "riset_skripsi"
WIB = ZoneInfo("Asia/Jakarta")
DAYS = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


@dataclass(frozen=True)
class Template:
    key: str
    label: str
    text: str
    pro: bool
    action: str  # "fill", "riset", atau "kerangka"


TEMPLATES = (
    Template("cari_jurnal", "Cari jurnal", "", True, "riset"),
    Template("jelasin", "Jelasin konsep", "Jelasin [konsep] pelan-pelan pakai contoh angka, lalu kasih 2 soal latihan.", False, "fill"),
    Template("analisis", "Analisis metode", "Analisis: [metode] cocok nggak buat data [jenis data]-ku?", False, "fill"),
    Template("cek_referensi", "Cek referensi", "Cek apakah referensi ini beneran ada: [tempel referensi]", False, "fill"),
    Template("ringkas_file", "Ringkas file proyek", "Ringkas file proyek ini dan tandai klaim yang belum ada sumbernya.", False, "fill"),
    Template("kerangka", "Kerangka Bab 1–3", "", True, "kerangka"),
)


def templates_for(has_files, has_map, riset_enabled, writer_enabled):
    """Template yang bisa dipakai di konteks ini, urutan tetap."""

    hidden = set()
    if not riset_enabled:
        hidden.add("cari_jurnal")
    if not has_files:
        hidden.add("ringkas_file")
    if not (has_map and writer_enabled):
        hidden.add("kerangka")
    return [template for template in TEMPLATES if template.key not in hidden]


def latest_riset(chats, project_id):
    """(chat, indeks pesan) peta Riset Skripsi terbaru di konteks ini, atau None.

    project_id None berarti semua chat, termasuk yang tanpa proyek.
    """

    candidates = sorted(
        (
            chat for chat in chats
            if not chat.get("archived") and (project_id is None or chat.get("project_id") == project_id)
        ),
        key=lambda chat: chat.get("updated", 0),
        reverse=True,
    )
    for chat in candidates:
        messages = chat.get("messages", [])
        for index in range(len(messages) - 1, -1, -1):
            if messages[index].get("kind") == RISET_KIND and not messages[index].get("error"):
                return chat, index
    return None


def _wib(epoch):
    return datetime.fromtimestamp(epoch, WIB)


def greeting(now, name):
    """"Malam, Raka." menurut jam WIB; tanpa nama jika belum masuk."""

    hour = _wib(now).hour
    part = "Pagi" if 4 <= hour <= 10 else "Siang" if 11 <= hour <= 14 else "Sore" if 15 <= hour <= 17 else "Malam"
    first = (name or "").split()
    return f"{part}, {first[0]}." if first else f"{part}."


def relative_time(then, now):
    """21.42 / Kemarin / Sen / 15 Okt / 15 Okt 2025, dalam WIB."""

    then_at, now_at = _wib(then), _wib(now)
    days = (now_at.date() - then_at.date()).days
    if days <= 0:
        return then_at.strftime("%H.%M")
    if days == 1:
        return "Kemarin"
    if days <= 6:
        return DAYS[then_at.weekday()]
    text = f"{then_at.day} {MONTHS[then_at.month - 1]}"
    return text if then_at.year == now_at.year else f"{text} {then_at.year}"
