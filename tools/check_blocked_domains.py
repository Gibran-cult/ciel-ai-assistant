"""Periksa calon domain untuk guard/blocked_targets.json.

Untuk setiap calon, skrip membuka beranda situs (GET, tanpa data pengguna,
tanpa login), mengikuti pengalihan, lalu mencatat alamat akhir, judul
halaman, dan apakah nama mereknya muncul di judul atau alamat akhir.
Hasilnya baris tabel untuk docs/blocked-targets.md dan ringkasan yang gagal.

    python tools/check_blocked_domains.py > hasil.md

Yang gagal tidak dimasukkan ke daftar sebelum pemilik memeriksanya sendiri.
"""

import datetime
import html
import re
import sys

import requests

# (kategori, merek, domain, kata yang harus muncul di judul atau alamat akhir)
CANDIDATES = [
    ("Bank", "BCA", "klikbca.com", "bca"),
    ("Bank", "BCA", "bca.co.id", "bca"),
    ("Bank", "Bank Mandiri", "bankmandiri.co.id", "mandiri"),
    ("Bank", "BRI", "bri.co.id", "bri"),
    ("Bank", "BNI", "bni.co.id", "bni"),
    ("Bank", "Bank Syariah Indonesia", "bankbsi.co.id", "bsi"),
    ("Bank", "CIMB Niaga", "cimbniaga.co.id", "cimb"),
    ("Bank", "PermataBank", "permatabank.com", "permata"),
    ("Bank", "Danamon", "danamon.co.id", "danamon"),
    ("Bank", "BTN", "btn.co.id", "btn"),
    ("Bank", "OCBC Indonesia", "ocbc.id", "ocbc"),
    ("Bank", "Maybank Indonesia", "maybank.co.id", "maybank"),
    ("Bank", "Panin Bank", "panin.co.id", "panin"),
    ("Bank", "Bank Mega", "bankmega.com", "mega"),
    ("Bank", "UOB Indonesia", "uob.co.id", "uob"),
    ("Bank", "Bank Jago", "jago.com", "jago"),
    ("Bank", "SeaBank", "seabank.co.id", "seabank"),
    ("Bank", "blu by BCA Digital", "bcadigital.co.id", "bca"),
    ("Bank", "Jenius", "jenius.com", "jenius"),
    ("Bank", "Allo Bank", "allobank.com", "allo"),
    ("Dompet digital", "DANA", "dana.id", "dana"),
    ("Dompet digital", "OVO", "ovo.id", "ovo"),
    ("Dompet digital", "GoPay", "gopay.co.id", "gopay"),
    ("Dompet digital", "LinkAja", "linkaja.id", "linkaja"),
    ("Pengelola kata sandi", "1Password", "1password.com", "1password"),
    ("Pengelola kata sandi", "Bitwarden", "bitwarden.com", "bitwarden"),
    ("Pengelola kata sandi", "LastPass", "lastpass.com", "lastpass"),
    ("Pengelola kata sandi", "Dashlane", "dashlane.com", "dashlane"),
    ("Pengelola kata sandi", "Keeper", "keepersecurity.com", "keeper"),
    ("Pengelola kata sandi", "NordPass", "nordpass.com", "nordpass"),
    ("Pengelola kata sandi", "Google Password Manager", "passwords.google.com", "password"),
    ("Pengelola kata sandi", "Proton Pass", "pass.proton.me", "proton"),
    ("Investasi", "Indodax", "indodax.com", "indodax"),
    ("Investasi", "Tokocrypto", "tokocrypto.com", "tokocrypto"),
    ("Investasi", "Pintu", "pintu.co.id", "pintu"),
    ("Investasi", "Ajaib", "ajaib.co.id", "ajaib"),
    ("Investasi", "Stockbit", "stockbit.com", "stockbit"),
    ("Investasi", "Bibit", "bibit.id", "bibit"),
    ("Paylater dan pinjaman", "Kredivo", "kredivo.com", "kredivo"),
    # kredivo.com mengalihkan ke kredivo.id (dicek 18 November 2026).
    ("Paylater dan pinjaman", "Kredivo", "kredivo.id", "kredivo"),
    ("Paylater dan pinjaman", "Akulaku", "akulaku.com", "akulaku"),
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; blocked-list-check/1.0)", "Accept-Language": "id,en;q=0.8"}
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
META_RE = re.compile(r"<meta[^>]+(?:property|name)=[\"'](og:site_name|og:title|application-name)[\"'][^>]*content=[\"']([^\"']*)[\"']",
                     re.IGNORECASE)
# Teks yang terlihat kira-kira: tanpa skrip dan gaya.
STRIP_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


def fetch(domain):
    """Beranda situs, mencoba https://domain lalu https://www.domain."""

    last = None

    for host in (domain, f"www.{domain}"):
        try:
            return requests.get(f"https://{host}/", headers=HEADERS, timeout=40, allow_redirects=True), None
        except requests.RequestException as error:
            last = type(error).__name__

    return None, last


def check(domain, keyword):
    """(status, alamat akhir, judul, bukti) — bukti None kalau merek tidak terlihat dari situsnya sendiri."""

    response, error = fetch(domain)

    if response is None:
        return None, None, f"gagal dibuka ({error})", None

    page = response.text[:400_000]
    match = TITLE_RE.search(page)
    title = " ".join(html.unescape(match.group(1)).split())[:120].replace("|", "/") if match else ""
    metas = {name.lower(): html.unescape(value) for name, value in META_RE.findall(page)}
    text = html.unescape(TAG_RE.sub(" ", STRIP_RE.sub(" ", page))).lower()

    # Alamat akhir hampir selalu memuat kata itu, jadi buktinya harus dari isi
    # halaman: judul, tanda meta situs, atau teks halaman yang menyebut merek.
    if keyword in title.lower():
        evidence = "judul"
    elif any(keyword in value.lower() for value in metas.values()):
        evidence = "meta " + ", ".join(sorted(name for name, value in metas.items() if keyword in value.lower()))
    elif len(re.findall(rf"\b{re.escape(keyword)}\b", text)) >= 3:
        evidence = "teks halaman"
    else:
        evidence = None

    return response.status_code, response.url, title, evidence


def main():
    today = datetime.date.today().isoformat()
    rows, failed = [], []

    for category, brand, domain, keyword in CANDIDATES:
        status, final, title, evidence = check(domain, keyword)
        row = (f"| `{domain}` | {category} | {brand} | https://{domain}/ | {final or '-'} | {title or '-'} | "
               f"{evidence or '-'} | {status or '-'} | {today} |")
        (rows if evidence else failed).append(row)

    print("## Lolos\n")
    print("| Domain | Kategori | Merek | Dibuka | Alamat akhir | Judul halaman | Bukti | Status | Dicek |")
    print("|---|---|---|---|---|---|---|---|---|")
    print("\n".join(rows))
    print("\n## Gagal (merek tidak terlihat dari isi situsnya sendiri)\n")
    print("\n".join(failed) if failed else "Tidak ada.")


if __name__ == "__main__":
    sys.exit(main())
