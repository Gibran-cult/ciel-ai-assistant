"""Log aktivitas agent dalam bahasa biasa, untuk Pengaturan > Agent (rencana 2C).

Modul murni tanpa Streamlit. Isinya hanya teks; tampilannya menulis teks ini
dengan elemen teks biasa, jadi nilai dari log (jenis aksi, target) yang mirip
HTML tidak pernah dirender. Bentuk barisnya mengikuti docs/design-system.md
bagian "Log aktivitas".
"""

import csv
import io
from dataclasses import dataclass
from datetime import datetime

from guard.limits import JAKARTA   # UTC+7 tetap, sama dengan perhitungan batas belanja
MONTHS = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
MAX_TARGET = 60
FORMULA_START = ("=", "+", "-", "@")


@dataclass(frozen=True)
class LogLine:
    seq: int
    time: str
    level: str
    action: str
    target: str
    result: str
    reason: str
    device: str


ACTION_TEXT = {
    "tab_open": "Membuka halaman",
    "tab_read": "Membaca halaman",
    "tab_click": "Mengklik",
    "tab_type": "Mengetik di kolom",
    "tab_select": "Memilih di daftar",
    "tab_scroll": "Menggulir halaman",
    "tab_close": "Menutup tab",
    "form_submit": "Mengirim formulir",
    "ask_user": "Bertanya kepadamu",
    "finish": "Selesai dan melapor",
}

# Alasan guard yang ditampilkan saat aksi ditahan, ditolak, atau butuh
# persetujuan. Kalimat toko mengikuti tabel pesan di docs/design-system.md.
REASON_TEXT = {
    "not_listed": "Situs ini belum ada di daftar toko resmi Ciel.",
    "no_official_badge": "Toko ini tidak punya label resmi dari marketplace, jadi aku nggak bisa memastikan barangnya asli.",
    "lookalike_domain": "Alamat situs ini mirip toko resmi tetapi berbeda. Situs seperti ini sering dipakai untuk menipu.",
    "automation_forbidden": "Aturan situs ini melarang alat otomatis.",
    "underage": "Fitur pembelian hanya untuk pengguna 18 tahun ke atas.",
    "purchases_off": "Fitur pembelian belum kamu aktifkan.",
    "limit_exceeded": "Total ini melewati batas belanja yang kamu atur.",
    "ask_mode": "Mode \"Tanya dulu\": setiap perubahan menunggu persetujuanmu.",
    "submits": "Aksi ini mengirim data, jadi butuh persetujuanmu.",
    "tainted_target": "Alamat tujuan ini berasal dari isi halaman, jadi butuh persetujuanmu.",
    "scope_host": "Situs ini di luar rencana tugas.",
    "scope_kind": "Jenis aksi ini di luar rencana tugas.",
    "secret_field": "Kolom ini meminta data rahasia, jadi kamu yang mengisinya sendiri.",
    "secret_text": "Teks ini tampak berisi data rahasia, jadi tidak dikirim.",
    "possible_secret": "Teks ini mungkin berisi data rahasia, jadi butuh persetujuanmu.",
    "blocked_host": "Situs ini selalu diblokir untuk agent.",
    "blocked_app": "Aplikasi ini selalu diblokir untuk agent.",
    "stopped": "Tugas sudah dihentikan.",
    "bad_ticket": "Perangkat sudah tidak tersambung atau sudah dicabut.",
    "unknown_ref": "Kontrol yang dimaksud tidak ada di halaman.",
    "no_page": "Belum ada halaman yang terbuka.",
    "bad_args": "Permintaan model tidak sesuai aturan, jadi ditolak.",
    "bad_call": "Permintaan model tidak sesuai aturan, jadi ditolak.",
    "tool_unavailable": "Aksi ini tidak tersedia untuk agent.",
}

CHAIN_TEXT = {
    "ok": "Log utuh",
    "broken": "Log rusak: ada catatan yang berubah",
    "missing": "Ada catatan yang hilang",
    "extra": "Catatan terakhir belum terkunci",
    None: "Belum diperiksa",
}


def text(value):
    return value if isinstance(value, str) else ""


def when(value, today):
    """Waktu Asia/Jakarta: "HH.MM" hari ini, "D Bln HH.MM" hari lain, "?" kalau rusak."""

    try:
        moment = datetime.fromisoformat(value).astimezone(JAKARTA)
    except (TypeError, ValueError):
        return "?"

    clock = f"{moment.hour:02d}.{moment.minute:02d}"
    return clock if moment.date() == today else f"{moment.day} {MONTHS[moment.month - 1]} {clock}"


def result_text(decision, result):
    if result == "widened":
        return "Lingkup diperluas"

    if result == "declined":
        return "Kamu tolak"

    if result == "expired":
        return "Kedaluwarsa"

    if result == "failed":
        return "Gagal"

    if decision == "block":
        return "Diblokir"

    if decision == "handover":
        return "Kamu kerjakan sendiri" if result == "handed_over" else "Kamu tolak"

    if result == "ok":
        return "Disetujui kamu" if decision == "confirm" else "Selesai"

    return "Dikirim"


def describe(row, today):
    """Satu baris log sebagai LogLine. Nilai yang rusak menjadi teks aman, tidak pernah exception."""

    kind = text(row.get("kind"))
    target = text(row.get("target"))
    decision, reason = row.get("decision"), text(row.get("reason"))
    explained = ""

    # Alasan hanya ditulis kalau aksinya ditahan, ditolak, atau ditanyakan.
    if decision in ("block", "confirm", "handover") and reason:
        explained = REASON_TEXT.get(reason, f"Diblokir aturan keamanan ({reason}).")

    return LogLine(
        seq=row.get("seq") if type(row.get("seq")) is int else 0,
        time=when(row.get("at"), today),
        level=text(row.get("level")) or "?",
        action=ACTION_TEXT.get(kind, f"Aksi lain ({kind or '?'})"),
        target=target if len(target) <= MAX_TARGET else target[:MAX_TARGET - 1] + "…",
        result=result_text(decision, row.get("result")),
        reason=explained,
        device=text(row.get("device")),
    )


SAME_ACTION = ("kind", "target", "decision", "approved_by")


def is_result_of(previous, row):
    """Benar kalau `row` adalah baris hasil untuk baris "dikirim" `previous`.

    Baris yang diblokir juga tidak punya hasil, jadi yang digabung hanya
    baris izin atau konfirmasi tepat sebelumnya, dengan aksi yang sama.
    """

    return (
        previous.get("result") is None and row.get("result") is not None
        and previous.get("decision") in ("allow", "confirm")
        and all(previous.get(key) == row.get(key) for key in SAME_ACTION)
        and type(previous.get("seq")) is int and row.get("seq") == previous["seq"] + 1
    )


def pair_rows(rows):
    """Satu baris per aksi: baris "dikirim" (tanpa hasil) digantikan baris hasilnya.

    Loop menulis dua baris untuk aksi yang dikirim ke klien: satu sebelum
    dikirim (hasil kosong) dan satu tepat setelahnya dengan hasilnya.
    """

    paired = []

    for row in rows:
        if paired and is_result_of(paired[-1], row):
            paired[-1] = row
        else:
            paired.append(row)

    return paired


def filter_lines(lines, *, device=None, level=None, result=None):
    return [
        line for line in lines
        if (device is None or line.device == device) and (level is None or line.level == level) and (result is None or line.result == result)
    ]


def safe_cell(value):
    return "'" + value if value.startswith(FORMULA_START) else value


def export_csv(lines):
    """Log sebagai CSV. Sel yang diawali tanda rumus diberi awalan ' supaya tidak dijalankan spreadsheet."""

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["waktu", "risiko", "aksi", "target", "hasil", "alasan", "perangkat"])

    for line in lines:
        writer.writerow([safe_cell(value) for value in (line.time, line.level, line.action, line.target, line.result, line.reason, line.device)])

    return buffer.getvalue()
