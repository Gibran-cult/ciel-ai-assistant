"""ID pemilik akun, dipakai app Streamlit dan Ciel Agent API.

Kedua layanan harus menghitungnya persis sama dari `sub` Google, supaya
satu akun punya satu memori, satu riwayat, dan satu log agent.
"""

import hashlib


def owner_from_subject(subject):
    """16 karakter heksadesimal dari subjek login, atau "" kalau subjek kosong."""

    if not isinstance(subject, str) or not subject:
        return ""

    return hashlib.sha256(f"ciel-memory:{subject}".encode()).hexdigest()[:16]
