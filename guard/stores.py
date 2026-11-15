"""Verifikasi toko resmi sebelum pembelian (docs/security.md bagian 4).

Model tidak ikut memutuskan. Klien (adapter toko di ekstensi) mengirim apa
yang dibacanya dari halaman, dan fungsi di sini memutuskan resmi atau tidak
dengan satu kode alasan. Kalau ada yang tidak bisa dipastikan, jawabannya
menolak.
"""

from dataclasses import dataclass, field

from guard.domains import check_url, lookalike_of, match_allowed
from guard.registry import Marketplace, is_stale

# Asal navigasi yang boleh dipakai untuk belanja: alamat yang diketik agent
# sendiri, atau tautan di dalam domain yang sama.
TRUSTED_NAV = frozenset({"typed", "internal"})


@dataclass(frozen=True)
class StoreEvidence:
    url: str               # alamat halaman produk (atau halaman situs brand)
    nav_origin: str        # "typed" | "internal" | "external" | "ad" | "message"
    store_name: str        # nama toko di halaman produk
    store_page_name: str   # nama toko di halaman toko
    badge_text: str        # teks label di halaman produk, "" kalau tidak ada
    adapter_ok: bool       # False kalau adapter tidak menemukan struktur halaman
    # Halaman toko di marketplace. Label resmi harus terlihat di sana juga.
    # Tidak dipakai untuk situs brand.
    store_page_url: str = ""
    store_page_badge: str = ""


@dataclass(frozen=True)
class StoreVerdict:
    official: bool
    kind: str | None            # "marketplace" | "brand_site" | None
    reason: str | None          # kode alasan saat official False
    domain: str | None          # domain terdaftar yang cocok
    lookalike_of: str | None    # domain resmi yang ditiru, kalau ada
    proof: dict = field(default_factory=dict)


def rejected(reason, domain=None, imitated=None):
    return StoreVerdict(False, None, reason, domain, imitated, {})


def text(value):
    return value.strip() if isinstance(value, str) else ""


def verify_store(evidence, registry, now, automated):
    """Putuskan apakah toko di evidence resmi. Alasan pertama yang cocok menang."""

    try:
        return decide_store(evidence, registry, now, automated)
    except Exception:
        # Apa pun yang tidak terduga berarti status toko tidak bisa dipastikan.
        return rejected("badge_unverifiable")


def decide_store(evidence, registry, now, automated):
    check = check_url(evidence.url)

    if check.problem == "insecure":
        return rejected("insecure")

    if check.problem in ("punycode", "userinfo"):
        return rejected("lookalike_domain")

    if check.problem:
        return rejected("not_listed")

    host = check.host
    entry = registry.find(host)

    if entry is None:
        imitated = lookalike_of(host, registry.allowed_domains())
        return rejected("lookalike_domain", imitated=imitated) if imitated else rejected("not_listed")

    domain = match_allowed(host, registry.allowed_domains())
    nav = evidence.nav_origin

    if not isinstance(nav, str) or nav not in TRUSTED_NAV:
        return rejected("untrusted_navigation", domain)

    if entry.approved is not True:
        return rejected("not_listed", domain)

    if is_stale(entry.checked, now.date()):
        return rejected("registry_stale", domain)

    # Nilai automated yang tidak jelas dihitung sebagai otomatis.
    if automated is not False and entry.automation != "allowed":
        return rejected("automation_forbidden", domain)

    name = text(evidence.store_name)

    if not isinstance(entry, Marketplace):
        proof = {"store_name": name, "badge_text": "", "domain": domain, "checked_at": now.isoformat()}
        return StoreVerdict(True, "brand_site", None, domain, None, proof)

    if evidence.adapter_ok is not True:
        return rejected("badge_unverifiable", domain)

    labels = {label.strip().casefold(): label for label in entry.official_labels}
    badge = text(evidence.badge_text).casefold()

    if badge not in labels:
        return rejected("no_official_badge", domain)

    # Halaman toko harus berada di marketplace yang sama, dan label resminya
    # harus terlihat di sana juga. Label di satu halaman saja bisa ditiru
    # lewat gambar atau teks di deskripsi produk.
    page = check_url(evidence.store_page_url)

    if page.problem or registry.find(page.host) is not entry:
        return rejected("badge_unverifiable", domain)

    if text(evidence.store_page_badge).casefold() not in labels:
        return rejected("no_official_badge", domain)

    if not name or name.casefold() != text(evidence.store_page_name).casefold():
        return rejected("badge_unverifiable", domain)

    proof = {"store_name": name, "badge_text": labels[badge], "domain": domain, "checked_at": now.isoformat()}
    return StoreVerdict(True, "marketplace", None, domain, None, proof)
