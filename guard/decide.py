"""Satu keputusan untuk setiap aksi agent (docs/security.md bagian 2).

Ini satu-satunya pintu yang dipakai loop agent. Urutannya tetap, dan
jawaban pertama yang cocok dikembalikan:

1. stop sedang aktif                      -> blokir
2. tiket aksi tidak sah                   -> blokir
3. aksi R3                                -> blokir, atau serah terima ke pengguna
4. di luar lingkup tugas                  -> minta perluasan lingkup, atau blokir
5. aksi belanja: usia, toko resmi, batas  -> blokir kalau salah satu gagal
6. R2                                     -> konfirmasi, di mode apa pun
7. R1                                     -> jalan di mode "auto", selain itu konfirmasi
8. R0                                     -> jalan

Model hanya mengusulkan aksi. Tidak ada prompt atau mode yang bisa
melewati urutan ini, dan apa pun yang tidak terduga berakhir sebagai blokir.
"""

from dataclasses import dataclass

from guard.domains import match_allowed, normalize_host
from guard.limits import SpendLimits, check_spend, purchases_on
from guard.risk import R0, R1, R2, R3, classify
from guard.scope import TaskScope, in_scope
from guard.stores import StoreVerdict


@dataclass(frozen=True)
class Context:
    stopped: bool                        # tombol stop ditekan atau tugas dibatalkan
    ticket_ok: bool                      # tiket aksi sah dan perangkat belum dicabut
    mode: str                            # "ask" (bawaan) atau "auto"
    scope: TaskScope
    adult_verified: bool                 # akun terverifikasi 18 tahun ke atas
    limits: SpendLimits
    spent_this_month: int
    store: StoreVerdict | None = None    # hasil verify_store untuk aksi belanja
    purchase_total: int | None = None    # total ringkasan pembelian, rupiah


@dataclass(frozen=True)
class Decision:
    outcome: str   # "allow" | "confirm" | "block" | "handover"
    level: str
    reason: str


PURCHASE_KINDS = frozenset({"cart_add", "checkout_prepare", "checkout_handoff", "order_cancel"})

# Aksi belanja yang membawa total, jadi batas belanja ikut diperiksa.
SPEND_CHECKED = frozenset({"checkout_prepare", "checkout_handoff"})

# Aksi R3 yang bisa dikerjakan pengguna sendiri di tempat yang sama:
# agent berhenti, pengguna mengerjakan bagian itu, lalu agent melanjutkan.
HANDOVER_REASONS = frozenset({
    "secret_field", "pay", "captcha_solve", "account_create", "oauth_grant", "terms_accept",
})

INTERNAL_ERROR = Decision("block", R3, "internal_error")


def decide(action, ctx):
    try:
        return decide_checked(action, ctx, classify(action))
    except Exception:
        return INTERNAL_ERROR


def target_outside(action, scope):
    """Benar kalau aksi menyebut situs atau aplikasi yang tidak ada di lingkup tugas."""

    if isinstance(action.host, str):
        host = normalize_host(action.host)
        return host is None or not match_allowed(host, scope.hosts)

    if isinstance(action.app, str):
        return action.app.lower() not in scope.apps

    return False


def decide_checked(action, ctx, risk):
    level = risk.level

    # Nilai yang tidak jelas dibaca ke arah yang aman.
    if ctx.stopped is not False:
        return Decision("block", level, "stopped")

    if ctx.ticket_ok is not True:
        return Decision("block", level, "bad_ticket")

    if level == R3:
        # Serah terima hanya untuk target yang memang bagian dari tugas.
        # Meminta pengguna mengisi kata sandi di halaman lain sama saja
        # dengan membantu halaman itu memancing data.
        handover = risk.reason in HANDOVER_REASONS and not target_outside(action, ctx.scope)
        return Decision("handover" if handover else "block", level, risk.reason)

    scope = in_scope(action, ctx.scope)

    if not scope.inside:
        if scope.reason == "path_denied":
            return Decision("block", level, "path_denied")

        return Decision("confirm", level, "scope_" + scope.reason)

    # Gerbang belanja berlaku untuk jenis aksinya dan untuk efeknya, supaya
    # klik biasa pada tombol keranjang atau checkout tidak melewatinya.
    purchase = {action.kind, action.effect} & PURCHASE_KINDS

    if purchase:
        if ctx.adult_verified is not True:
            return Decision("block", level, "underage")

        store = ctx.store

        if store is None or store.official is not True:
            reason = store.reason if store is not None and store.reason else "not_listed"
            return Decision("block", level, reason)

        # Status resmi berlaku untuk toko yang diperiksa, tidak untuk situs lain.
        host = normalize_host(action.host)

        if host is None or not isinstance(store.domain, str) or not match_allowed(host, (store.domain,)):
            return Decision("block", level, "not_listed")

        # Membatalkan pesanan tetap boleh saat pembelian dimatikan.
        if purchase != {"order_cancel"} and not purchases_on(ctx.limits, ctx.scope.spend_cap):
            return Decision("block", level, "purchases_off")

        if purchase & SPEND_CHECKED:
            spend = check_spend(ctx.purchase_total, ctx.limits, ctx.spent_this_month, ctx.scope.spend_cap)

            if not spend.ok:
                return Decision("block", level, spend.reason)

    if level == R2:
        return Decision("confirm", level, risk.reason)

    if level == R1:
        if ctx.mode == "auto":
            return Decision("allow", level, risk.reason)

        return Decision("confirm", level, "ask_mode")

    if level == R0:
        return Decision("allow", level, risk.reason)

    return INTERNAL_ERROR
