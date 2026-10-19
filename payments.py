"""Pembelian Ciel Pro lewat Midtrans Snap (redirect).

Alurnya:
1. App membuat baris `pro_orders` (status 'pending') untuk akun yang login,
   lalu transaksi Snap dengan server key. Server key hanya ada di secrets
   server, tidak pernah dikirim ke browser.
2. Pengguna membayar di halaman Midtrans (QRIS, e-wallet, VA), lalu kembali
   ke halaman Pricing Ciel. Parameter yang ditambahkan Midtrans ke URL itu
   tidak dipakai: app membaca order terakhir akun ini dari database.
3. Midtrans mengirim notifikasi ke Supabase Edge Function midtrans-notify,
   yang mengecek signature dan Status API, lalu menandai order lunas dan
   menambah Pro 30 hari (ciel_settle_order). App tidak pernah memberi Pro dari
   parameter URL saat pengguna kembali; app hanya membaca status order dan
   status Pro dari database.

Sekali bayar = Pro 30 hari. Tidak ada tagihan otomatis.
"""

import logging
import uuid

import requests

logger = logging.getLogger("ciel_ai.payments")

SNAP_URLS = {
    False: "https://app.sandbox.midtrans.com/snap/v1/transactions",
    True: "https://app.midtrans.com/snap/v1/transactions",
}
TIMEOUT = 20
PRO_DAYS = 30
ITEM_ID = "ciel-pro-30"
# Transaksi yang tidak dibayar kedaluwarsa setelah ini, supaya order lama
# tidak bisa dilunasi berhari-hari kemudian.
EXPIRY_MINUTES = 60


def new_order_id():
    """ID order: 32 karakter hex (cocok untuk Midtrans dan pola ID chat_store)."""
    return uuid.uuid4().hex


def snap_payload(order_id, amount, finish_url, email=None, name=None):
    """Badan permintaan transaksi Snap untuk Pro 30 hari."""

    amount = int(amount)
    payload = {
        "transaction_details": {"order_id": order_id, "gross_amount": amount},
        "item_details": [
            {"id": ITEM_ID, "price": amount, "quantity": 1, "name": f"Ciel Pro {PRO_DAYS} hari"},
        ],
        "expiry": {"unit": "minutes", "duration": EXPIRY_MINUTES},
        "callbacks": {"finish": finish_url},
    }

    # Email hanya untuk bukti bayar dari Midtrans; nama dipotong ke batas Midtrans.
    customer = {}
    if email:
        customer["email"] = str(email)[:255]
    if name:
        customer["first_name"] = str(name)[:50]
    if customer:
        payload["customer_details"] = customer

    return payload


def create_snap_transaction(server_key, production, payload):
    """
    Buat transaksi Snap. Kembalikan redirect_url, atau None jika gagal
    (detail hanya di log server; isi respons Midtrans bisa memuat data order).
    """

    try:
        response = requests.post(
            SNAP_URLS[bool(production)],
            auth=(server_key, ""),
            json=payload,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return str(response.json()["redirect_url"])

    except (requests.exceptions.RequestException, ValueError, KeyError, TypeError) as error:
        status = getattr(getattr(error, "response", None), "status_code", None)
        logger.error("snap_error type=%s status=%s", type(error).__name__, status)
        return None


def finish_url(app_url):
    """Halaman tujuan setelah bayar: Pricing, tempat status order dibaca ulang."""
    return f"{app_url.split('?', 1)[0].rstrip('/')}/?page=pricing"


ORDER_MESSAGES = {
    "paid": ("ok", "Pembayaran diterima. Ciel Pro aktif."),
    "pending": ("wait", "Menunggu konfirmasi pembayaran dari Midtrans. Biasanya kurang dari satu menit."),
    "expire": ("fail", "Waktu pembayaran habis. Silakan beli lagi."),
    "cancel": ("fail", "Pembayaran dibatalkan."),
    "deny": ("fail", "Pembayaran ditolak oleh penyedia pembayaran."),
    "failure": ("fail", "Pembayaran gagal. Silakan coba lagi."),
}


def order_message(order):
    """(jenis, teks) untuk status order dari database, atau None jika order tidak dikenal."""

    if not order:
        return None

    return ORDER_MESSAGES.get(order.get("status"), ORDER_MESSAGES["pending"])
