"""Batas belanja per transaksi dan per bulan (docs/security.md bagian 4).

Batas diatur pengguna. Bawaannya 0, artinya fitur pembelian mati sampai
pengguna mengisinya. Semua jumlah adalah rupiah bulat (int). Jumlah yang
rusak (float, bool, teks, negatif) selalu ditolak.
"""

from dataclasses import dataclass
from datetime import timedelta, timezone

# Bulan untuk batas belanja dihitung di WIB, tanpa pergantian jam musiman.
JAKARTA = timezone(timedelta(hours=7))


@dataclass(frozen=True)
class SpendLimits:
    per_tx: int = 0
    per_month: int = 0


@dataclass(frozen=True)
class LimitVerdict:
    ok: bool
    reason: str | None       # None, "purchases_off", "limit_exceeded"
    remaining_tx: int        # sisa batas transaksi setelah pembelian ini
    remaining_month: int     # sisa batas bulan ini setelah pembelian ini


def month_key(now):
    """Bulan kalender di Asia/Jakarta, misalnya "2026-11". Waktu tanpa zona dibaca sebagai UTC."""

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    return now.astimezone(JAKARTA).strftime("%Y-%m")


def rupiah(value, minimum):
    """Nilai kalau int murni (bukan bool) dan tidak di bawah minimum, selain itu None."""

    return value if type(value) is int and value >= minimum else None


def purchases_on(limits, task_cap):
    """Benar kalau pengguna sudah mengisi kedua batas dan tugas ini boleh belanja."""

    return (
        rupiah(limits.per_tx, 1) is not None
        and rupiah(limits.per_month, 1) is not None
        and rupiah(task_cap, 1) is not None
    )


def check_spend(total, limits, spent_this_month, task_cap):
    per_tx = rupiah(limits.per_tx, 1)
    per_month = rupiah(limits.per_month, 1)

    if per_tx is None or per_month is None:
        return LimitVerdict(False, "purchases_off", 0, 0)

    total = rupiah(total, 1)
    spent = rupiah(spent_this_month, 0)
    cap = rupiah(task_cap, 0)

    # Sisa dihitung dengan jumlah rusak dianggap 0, supaya tetap bisa ditampilkan.
    remaining_tx = max(0, min(per_tx, cap or 0) - (total or 0))
    remaining_month = max(0, per_month - (spent or 0) - (total or 0))

    if total is None or spent is None or cap is None:
        return LimitVerdict(False, "limit_exceeded", remaining_tx, remaining_month)

    if total > per_tx or spent + total > per_month or total > cap:
        return LimitVerdict(False, "limit_exceeded", remaining_tx, remaining_month)

    return LimitVerdict(True, None, remaining_tx, remaining_month)
