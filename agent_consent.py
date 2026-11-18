"""Versi persetujuan agent dan pilihan masa simpan log.

Dibaca app Streamlit dan layanan Ciel Agent API, jadi modul ini tidak
mengimpor Streamlit. Kalau teks persetujuan di Pengaturan > Agent berubah,
naikkan AGENT_CONSENT_VERSION: pengguna lama diminta setuju lagi sebelum
perangkat baru bisa didaftarkan.
"""

AGENT_CONSENT_VERSION = "2026-11-18"
LOG_DAYS = (30, 90)   # bawaan 30 hari (docs/privacy-consent.md bagian 4)
