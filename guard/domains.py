"""Pemeriksa alamat untuk guardrail agent.

Tiga hal yang dijaga di sini (docs/security.md bagian 4):
- alamat yang dipakai untuk belanja harus https dan tidak menyamar
  (nama@host, punycode, alamat IP);
- pencocokan dengan domain terdaftar selalu persis, di batas label;
- domain yang hanya mirip ditandai sebagai tiruan.

Semua fungsi di sini murni dan tidak pernah melempar exception untuk
masukan rusak: alamat datang dari halaman web dan dari model.
"""

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class HostCheck:
    host: str | None      # host ASCII huruf kecil, None kalau tidak bisa dipakai
    problem: str | None   # None, "insecure", "userinfo", "ip", "punycode", "malformed"


MALFORMED = HostCheck(None, "malformed")

# Pengganti huruf yang sering dipakai domain tiruan.
FOLDS = (("0", "o"), ("1", "l"), ("3", "e"), ("5", "s"), ("rn", "m"), ("vv", "w"), ("-", ""))


def is_ip(host):
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def check_url(url):
    """Ambil host dari sebuah URL dan sebut masalah pertamanya, kalau ada."""

    if not isinstance(url, str):
        return MALFORMED

    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return MALFORMED

    if not host:
        return MALFORMED

    host = host.lower().rstrip(".")
    ip = is_ip(host)

    if not ip and "." not in host:
        return MALFORMED

    if not host.isascii():
        return HostCheck(None, "punycode")

    if "@" in parts.netloc:
        return HostCheck(host, "userinfo")

    if ip:
        return HostCheck(host, "ip")

    if any(label.startswith("xn--") for label in host.split(".")):
        return HostCheck(host, "punycode")

    if parts.scheme != "https":
        return HostCheck(host, "insecure")

    return HostCheck(host, None)


def match_allowed(host, allowed):
    """Domain terdaftar yang sama dengan host atau menjadi induknya, atau None."""

    if not isinstance(host, str):
        return None

    for domain in allowed:
        if host == domain or host.endswith("." + domain):
            return domain

    return None


def fold(label):
    label = label.lower()

    for old, new in FOLDS:
        label = label.replace(old, new)

    return label


def edit_distance(a, b):
    """Jarak Damerau-Levenshtein (sisip, hapus, ganti, tukar dua huruf bersebelahan)."""

    rows = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]

    for i in range(len(a) + 1):
        rows[i][0] = i

    for j in range(len(b) + 1):
        rows[0][j] = j

    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            rows[i][j] = min(rows[i - 1][j] + 1, rows[i][j - 1] + 1, rows[i - 1][j - 1] + cost)

            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                rows[i][j] = min(rows[i][j], rows[i - 2][j - 2] + 1)

    return rows[-1][-1]


def lookalike_of(host, allowed):
    """Domain terdaftar yang ditiru host, atau None.

    Setiap aturan dicoba untuk semua domain sebelum aturan berikutnya,
    supaya sinyal terkuat menang.
    """

    if not isinstance(host, str):
        return None

    domains = sorted(allowed)

    if match_allowed(host, domains):
        return None

    # Domain resmi dipakai sebagai awalan: toko.co.id.promo-murah.com
    for domain in domains:
        if domain in host:
            return domain

    labels = [fold(label) for label in host.split(".")]
    brands = [(fold(domain.split(".")[0]), domain) for domain in domains]

    # Nama brand ada di dalam label, termasuk dengan angka pengganti huruf.
    for brand, domain in brands:
        if len(brand) >= 4 and any(brand in label for label in labels):
            return domain

    # Selisih satu atau dua huruf. Ambang 1 untuk nama pendek supaya
    # akhiran seperti "shop" tidak dianggap tiruan "shopee".
    for brand, domain in brands:
        limit = 1 if len(brand) <= 7 else 2

        if any(edit_distance(label, brand) <= limit for label in labels):
            return domain

    return None
