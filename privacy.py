"""Halaman privasi Ciel.

Isi halaman mengikuti konfigurasi yang dikirim app.py (lama retensi,
login, panel "Data saya", nama pengelola, kontak), supaya yang dijanjikan
ke pengguna selalu sama dengan yang benar-benar terjadi.

Bagian-bagiannya mengikuti informasi yang diminta UU 27/2022 tentang
Pelindungan Data Pribadi: identitas pengelola (Pasal 5), dasar dan tujuan
pemrosesan serta jenis data dan retensi (Pasal 20-21), hak subjek data dan
cara memintanya (Pasal 6-14), data anak (Pasal 25), pemberitahuan
kegagalan pelindungan (Pasal 46), dan pemrosesan di luar Indonesia
(Pasal 56). Ini daftar periksa produk, bukan nasihat hukum.
"""

import html

import streamlit as st


# Ubah tanggal ini setiap kali isi halaman berubah (Pasal 21 ayat 2).
PRIVACY_UPDATED = "28 Oktober 2026"


PRIVACY_CSS = """
<style>
.ciel-privacy h1 {
    margin: 0 0 0.7rem;
    font-family: var(--font-serif);
    font-size: clamp(1.9rem, 3.8vw, 2.6rem);
    font-weight: 400;
    letter-spacing: -0.025em;
    line-height: 1.08;
    color: var(--c-text);
}
.ciel-privacy h2 {
    margin: 2rem 0 0.6rem;
    font-size: 1.05rem;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--c-text);
}
.stApp .ciel-privacy p,
.stApp .ciel-privacy li { font-size: 0.92rem; line-height: 1.65; color: var(--c-muted); }
.stApp .ciel-privacy .ciel-updated { margin-top: 0.3rem; font-size: 0.82rem; color: var(--c-faint); }
.stApp .ciel-privacy ul { padding-left: 1.1rem; margin: 0; }
.stApp .ciel-privacy li { margin: 0 0 0.45rem; }
.stApp .ciel-privacy strong { color: var(--c-text); font-weight: 600; }
.stApp .ciel-privacy a { color: var(--c-accent); }
</style>
"""


def privacy_sections(retention_days, memory_enabled, data_controls, contact_url=None, operator=None, history_saved=False, payments=False):
    """Kembalikan daftar (judul, [paragraf HTML]) untuk halaman privasi."""

    days = int(retention_days)
    contact_link = (
        f'<a href="{html.escape(contact_url, quote=True)}">hubungi kami</a>'
        if contact_url
        else None
    )

    who = []

    if operator:
        who.append(f"Ciel dikelola oleh <strong>{html.escape(operator)}</strong>.")

    who.append(
        f"Pertanyaan atau permintaan soal datamu: {contact_link}."
        if contact_link
        else "Pertanyaan atau permintaan soal datamu bisa disampaikan ke pengelola Ciel."
    )

    purpose = [
        "Ciel memproses pesan, file, dan foto yang kamu kirim untuk menyusun "
        "jawaban" + (
            ", dan jika kamu login, untuk mengingat konteks belajarmu lintas "
            "percakapan." if memory_enabled else "."
        ),
        "Dasarnya adalah persetujuanmu saat memakai Ciel. Kamu bisa menariknya "
        "kapan saja dengan berhenti memakai Ciel dan meminta datamu dihapus.",
    ]

    processing = [
        "Pesan dan file yang kamu lampirkan dikirim ke server Ciel untuk dijawab.",
        "Untuk menyusun jawaban, isi pesan juga diproses oleh penyedia model AI "
        "dan layanan pencarian web pihak ketiga. Server mereka bisa berada di "
        "<strong>luar Indonesia</strong>. Dengan memakai Ciel, kamu menyetujui "
        "pemrosesan ini.",
        "Foto yang kamu kirim diperkecil, lalu dibaca oleh layanan model AI "
        "pihak ketiga dengan paket berbayar yang tidak memakai data untuk "
        "melatih model; servernya juga bisa berada di luar Indonesia. Jika "
        "layanan itu tidak tersedia, foto dibaca oleh model di server Ciel sendiri.",
        "Embedding memory diproses oleh model yang berjalan di server Ciel sendiri.",
    ]

    stored = [
        (
            "<strong>Riwayat chat dan proyek di sidebar</strong>: setelah login, "
            "judul dan isi percakapanmu, serta nama proyek dan isi file yang kamu "
            "tambahkan ke proyek, disimpan di database Ciel supaya tetap ada saat "
            "halaman dimuat ulang, sampai kamu menghapusnya (Hapus chat atau Hapus "
            "proyek di sidebar). Mengarsipkan chat hanya menyembunyikannya dari "
            "daftar. Tanpa login, riwayat dan proyek ini hanya ada di browsermu "
            "dan hilang saat tab ditutup."
            if history_saved
            else "<strong>Riwayat chat dan proyek di sidebar</strong> hanya ada di "
            "browsermu dan hilang saat tab ditutup."
        ),
        f"<strong>Riwayat pesan di server:</strong> setiap pesan dan jawaban "
        f"disimpan di server Ciel paling lama <strong>{days} hari</strong>, "
        "lalu dihapus otomatis. Pesan tanpa login disimpan dengan kode acak, "
        "bukan namamu.",
        "<strong>Cadangan terenkripsi:</strong> dibuat dari server Ciel setiap "
        "malam dan disimpan paling lama 5 minggu. Data yang kamu hapus ikut "
        "hilang dari cadangan setelah itu.",
    ]

    if memory_enabled:
        stored.append(
            "<strong>Long-term memory</strong> (hanya setelah login): hal penting "
            "yang kamu minta Ciel ingat, disimpan sampai kamu menghapusnya dan "
            "hanya bisa dibaca oleh akunmu."
        )
        stored.append(
            "<strong>Dataset pribadi</strong> (hanya setelah login): data tabel "
            "yang kamu minta Ciel simpan, misalnya log belajar dari file atau "
            "dari chat. Disimpan di server Ciel sampai kamu menghapusnya, hanya "
            "bisa dibaca oleh akunmu, dan hanya dipakai untuk menghitung "
            "statistik dan melatih model untukmu. Ciel tidak menyimpan dataset "
            "tanpa permintaanmu dan tidak memakainya untuk pengguna lain."
        )
        stored.append(
            "<strong>Akun Google:</strong> nama dan email dipakai untuk "
            "menampilkan status login. Memory memakai kode yang diturunkan dari "
            "akunmu, bukan emailmu."
        )
    else:
        stored.append(
            "<strong>Long-term memory</strong> belum aktif di deployment ini, "
            "jadi Ciel tidak menyimpan memory jangka panjang."
        )

    if payments:
        stored.append(
            "<strong>Pembelian Ciel Pro:</strong> pembayaran diproses oleh "
            "<strong>Midtrans</strong>, penyedia pembayaran pihak ketiga. "
            "Ciel mengirim email dan namamu ke Midtrans untuk bukti bayar, dan "
            "menyimpan nomor order, nominal, status bayar, serta masa aktif Pro "
            "dengan kode akunmu. Ciel tidak pernah menerima atau menyimpan data "
            "kartu, rekening, atau PIN e-wallet-mu."
        )

    stored.append(
        "<strong>Catatan teknis:</strong> saat terjadi error, server mencatat "
        "kode permintaan (Request ID) dan detail error untuk perbaikan."
    )

    rights = [
        "Kamu berhak melihat datamu dan mendapat salinannya, memperbaikinya, "
        "meminta pemrosesannya dihentikan atau datanya dihapus, menarik "
        "persetujuan, dan meminta datamu dalam format yang bisa dipindahkan.",
    ]

    if memory_enabled and data_controls:
        rights.append(
            "Setelah login, buka menu akun di kanan atas lalu <strong>Data saya</strong> untuk "
            "melihat dan menghapus memory-mu, melihat, mengunduh, dan menghapus "
            "dataset pribadimu, serta menghapus riwayat chat-mu di server."
        )
    elif memory_enabled:
        rights.append(
            "Penghapusan memory, dataset pribadi, dan riwayat chat belum bisa dilakukan sendiri "
            "dari aplikasi; sampaikan permintaan ke pengelola."
        )

    rights.append(
        "Untuk permintaan apa pun soal datamu, kirim lewat "
        f'<a href="{html.escape(contact_url, quote=True)}">kontak pengelola</a>; '
        "setiap permintaan dicatat dan dijawab."
        if contact_url
        else "Untuk permintaan apa pun soal datamu, sampaikan ke pengelola; "
        "setiap permintaan dicatat dan dijawab."
    )
    rights.append(
        "Riwayat pesan tanpa login tidak bisa dihubungkan ke dirimu, jadi tidak "
        f"bisa dihapus per orang; pesan itu terhapus otomatis setelah {days} hari."
    )

    children = [
        "Jika kamu berusia di bawah 18 tahun, gunakan Ciel dengan izin dan "
        "pendampingan orang tua atau wali.",
    ]

    incidents = [
        "Jika terjadi kegagalan pelindungan data yang menyangkut datamu, "
        "pengelola akan memberi tahu secara tertulis paling lambat 3&times;24 jam "
        "setelah mengetahuinya.",
        "Jika isi halaman ini berubah, perubahannya diumumkan di halaman ini "
        "sebelum berlaku.",
    ]

    advice = [
        "Jangan kirim kata sandi, nomor identitas, data kesehatan, data "
        "keuangan, atau informasi rahasia lain ke Ciel.",
    ]

    return [
        ("Siapa yang mengelola Ciel", who),
        ("Untuk apa datamu diproses", purpose),
        ("Apa yang terjadi saat kamu mengirim pesan", processing),
        ("Apa yang disimpan", stored),
        ("Hakmu atas datamu", rights),
        ("Pengguna di bawah 18 tahun", children),
        ("Kebocoran data dan perubahan halaman ini", incidents),
        ("Saran", advice),
    ]


def render_privacy(retention_days=30, memory_enabled=False, data_controls=False, contact_url=None, operator=None, history_saved=False, payments=False):
    st.markdown(PRIVACY_CSS, unsafe_allow_html=True)

    parts = [
        '<div class="ciel-privacy">',
        "<h1>Privasi</h1>",
        "<p>Ringkasan data apa yang Ciel proses dan simpan, dan cara kamu "
        "mengendalikannya.</p>",
        f'<p class="ciel-updated">Terakhir diperbarui: {PRIVACY_UPDATED}</p>',
    ]

    for title, items in privacy_sections(retention_days, memory_enabled, data_controls, contact_url, operator, history_saved, payments):
        parts.append(f"<h2>{html.escape(title)}</h2><ul>")
        parts.extend(f"<li>{item}</li>" for item in items)
        parts.append("</ul>")

    parts.append("</div>")

    st.markdown("".join(parts), unsafe_allow_html=True)
