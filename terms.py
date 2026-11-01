"""Halaman Syarat dan Ketentuan Ciel.

Strukturnya sama dengan privacy.py: terms_sections() mengembalikan isi
halaman dari konfigurasi app.py (nama pengelola, kontak, penyedia
pembayaran), dan render_terms() menggambarnya dengan gaya halaman Privasi.

Ketentuan ini mengikuti UU 8/1999 tentang Perlindungan Konsumen: Pasal 18
melarang klausula baku yang menolak pengembalian uang begitu saja,
mengalihkan semua tanggung jawab, atau membuat aturan baru berlaku surut
atas layanan yang sudah dibayar. Jadi bagian Pengembalian dana menyebut
kapan uang dikembalikan, bukan kapan tidak. Ini daftar periksa produk,
bukan nasihat hukum.
"""

import html

import streamlit as st

from pricing import PLANS, format_idr
from privacy import PRIVACY_CSS


# Versi yang disetujui pengguna di gerbang persetujuan (tabel consents).
# Naikkan setiap kali Ketentuan atau Privasi berubah secara material, supaya
# setiap akun diminta setuju lagi sekali.
LEGAL_VERSION = "2026-11-01.2"

# Ubah tanggal ini setiap kali isi halaman berubah.
TERMS_UPDATED = "1 November 2026"


def terms_sections(operator=None, contact_url=None, payments=False):
    """Kembalikan daftar (judul, [paragraf HTML]) untuk halaman Syarat dan Ketentuan."""

    contact = (
        f'<a href="{html.escape(contact_url, quote=True)}">kontak pengelola</a>'
        if contact_url
        else "pengelola Ciel"
    )

    # Tanpa nama pengelola kalimat pertama dilewati, seperti di halaman Privasi.
    who = [f"Ciel dikelola oleh <strong>{html.escape(operator)}</strong>."] if operator else []
    who += [
        f"Pertanyaan, keluhan, atau permintaan soal layanan ini: {contact}."
        if contact_url
        else "Pertanyaan, keluhan, atau permintaan soal layanan ini bisa disampaikan ke pengelola Ciel.",
        "Dengan memakai Ciel, kamu menyetujui ketentuan ini dan Kebijakan Privasi Ciel.",
    ]

    sections = [
        ("Siapa yang mengelola Ciel", who),
        ("Ciel adalah AI", [
            "Jawaban Ciel dibuat oleh AI dan bisa keliru, termasuk sumber yang dikutip.",
            "Periksa jawaban dan sumbernya sebelum kamu pakai untuk tugas, skripsi, "
            "atau keputusan penting.",
            "Ciel bukan pengganti nasihat hukum, medis, atau keuangan dari ahlinya.",
        ]),
        ("Kejujuran akademik", [
            "Ciel membantu kamu belajar dan mencari sumber, bukan menulis tugas untukmu.",
            "Kamu tetap bertanggung jawab atas karya yang kamu kumpulkan dan wajib "
            "mengikuti aturan kampusmu soal penggunaan AI.",
        ]),
        ("Yang tidak boleh", [
            "Memakai Ciel untuk membuat atau menyebarkan konten yang melanggar hukum.",
            "Mengirim data pribadi orang lain tanpa hak.",
            "Menyerang, membebani, atau mengakali batas pemakaian layanan.",
            "Menjual atau membagikan akses akunmu ke orang lain.",
            "Jika aturan ini dilanggar, akses ke Ciel bisa dibatasi atau dihentikan.",
        ]),
        ("Isi milikmu", [
            "Pesan, file, dan foto yang kamu kirim tetap milikmu.",
            "Ciel hanya memakainya untuk menjawab dan menjalankan fitur yang kamu "
            "minta, seperti yang dijelaskan di halaman Privasi.",
        ]),
    ]

    if payments:
        pro = next(plan for plan in PLANS if plan["id"] == "pro")
        sections.append(("Ciel Pro", [
            f"Harga Ciel Pro {format_idr(pro['monthly'])}. Sekali bayar untuk 30 hari, "
            "tanpa tagihan otomatis.",
            f"Pembayaran diproses oleh {html.escape(payments)}. Pro aktif begitu "
            "pembayaran terkonfirmasi, dan pembelian berikutnya menambah 30 hari "
            "dari sisa masa aktif.",
        ]))
        sections.append(("Pengembalian dana", [
            "Uangmu dikembalikan penuh jika kamu sudah membayar tetapi Pro tidak "
            "aktif dalam 1&times;24 jam, atau jika kamu terbayar dua kali untuk "
            "order yang sama.",
            "Jika fitur Pro tidak bisa dipakai karena gangguan dari sisi Ciel lebih "
            "dari 3 hari berturut-turut, masa Pro-mu diperpanjang sebanyak hari "
            "gangguan itu.",
            f"Ajukan permintaan lewat {contact} paling lambat 7 hari setelah "
            "membayar, dengan menyebut nomor order. Kami menjawab paling lambat "
            "3 hari kerja, dan pengembalian dana dikirim paling lambat 14 hari "
            "kerja setelah permintaan disetujui.",
            "Jika kamu tidak menyetujui perubahan ketentuan saat masa Pro masih "
            "berjalan, sisa masa Pro-mu dikembalikan secara prorata.",
            "Permintaan dengan alasan lain tetap kami tinjau satu per satu.",
        ]))

    sections += [
        ("Usia", [
            "Jika kamu berusia di bawah 18 tahun, gunakan Ciel dengan izin dan "
            "pendampingan orang tua atau wali.",
        ]),
        ("Batas layanan", [
            "Paket gratis punya batas pesan per jam yang bisa berubah agar Ciel "
            "tetap lancar untuk semua orang. Selama masa Pro yang sudah dibayar, "
            "batas Pro tidak diturunkan.",
            "Ciel berusaha selalu bisa dipakai, tetapi bisa berhenti sementara "
            "untuk perawatan atau saat layanan pihak ketiga terganggu.",
        ]),
        ("Perubahan ketentuan", [
            "Perubahan ketentuan diumumkan di halaman ini sebelum berlaku.",
            "Perubahan tidak mengurangi masa Pro yang sudah kamu bayar.",
            "Jika perubahannya besar, kamu akan diminta menyetujuinya lagi saat "
            "masuk berikutnya. Jika kamu tidak setuju, kamu bisa berhenti memakai "
            "Ciel, dan sisa masa Pro yang sudah dibayar dikembalikan (lihat "
            "Pengembalian dana).",
        ]),
        ("Hukum dan sengketa", [
            "Ketentuan ini tunduk pada hukum Republik Indonesia.",
            "Jika ada perselisihan, kita selesaikan dulu secara musyawarah. Jika "
            "belum selesai, kamu bisa menempuh Badan Penyelesaian Sengketa "
            "Konsumen (BPSK) atau pengadilan sesuai UU Perlindungan Konsumen.",
        ]),
    ]

    return sections


def render_terms(operator=None, contact_url=None, payments=False):
    st.markdown(PRIVACY_CSS, unsafe_allow_html=True)

    parts = [
        '<div class="ciel-privacy">',
        "<h1>Syarat dan Ketentuan</h1>",
        "<p>Aturan main memakai Ciel dan Ciel Pro.</p>",
        f'<p class="ciel-updated">Terakhir diperbarui: {TERMS_UPDATED}</p>',
    ]

    for title, items in terms_sections(operator, contact_url, payments):
        parts.append(f"<h2>{html.escape(title)}</h2><ul>")
        parts.extend(f"<li>{item}</li>" for item in items)
        parts.append("</ul>")

    parts.append("</div>")

    st.markdown("".join(parts), unsafe_allow_html=True)
