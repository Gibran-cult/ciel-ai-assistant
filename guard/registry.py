"""Daftar toko resmi (docs/security.md bagian 4).

Datanya ada di official_stores.json. Entri dengan "approved": false tetap
dimuat supaya domainnya ikut dipakai untuk deteksi domain mirip, tetapi
tidak pernah dianggap resmi (lihat guard/stores.py).

Berkas yang rusak menggagalkan pemuatan dengan ValueError. Itu kesalahan
saat layanan mulai, jadi lebih baik berhenti daripada berjalan dengan
daftar yang salah.
"""

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from guard.domains import HostCheck, check_url, match_allowed

DEFAULT_PATH = Path(__file__).with_name("official_stores.json")
AUTOMATION = ("forbidden", "unknown", "allowed")
STALE_AFTER_DAYS = 90


@dataclass(frozen=True)
class Marketplace:
    id: str
    name: str
    domains: tuple[str, ...]
    official_labels: tuple[str, ...]
    automation: str
    approved: bool
    tos_url: str
    checked: str


@dataclass(frozen=True)
class BrandSite:
    brand: str
    domain: str
    automation: str
    approved: bool
    evidence: tuple[str, ...]
    checked: str


@dataclass(frozen=True)
class Registry:
    marketplaces: tuple[Marketplace, ...]
    brand_sites: tuple[BrandSite, ...]

    def allowed_domains(self):
        """Semua domain terdaftar, termasuk yang belum disetujui."""

        domains = [domain for market in self.marketplaces for domain in market.domains]
        domains += [site.domain for site in self.brand_sites]
        return tuple(domains)

    def find(self, host):
        for market in self.marketplaces:
            if match_allowed(host, market.domains):
                return market

        for site in self.brand_sites:
            if match_allowed(host, (site.domain,)):
                return site

        return None


def is_stale(checked, today):
    """Benar kalau pengecekan lebih dari 90 hari lalu atau tanggalnya tidak terbaca."""

    try:
        return (today - date.fromisoformat(checked)).days > STALE_AFTER_DAYS
    except (TypeError, ValueError):
        return True


def texts(value, what):
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{what} harus daftar teks")

    return tuple(value)


def checked_common(entry, domains, seen):
    """Validasi kolom yang sama di marketplace dan situs brand."""

    for domain in domains:
        if check_url("https://" + domain) != HostCheck(domain, None):
            raise ValueError(f"domain tidak sah: {domain!r}")

        if domain in seen:
            raise ValueError(f"domain ganda: {domain}")

        seen.add(domain)

    if entry["automation"] not in AUTOMATION:
        raise ValueError(f"automation tidak dikenal: {entry['automation']!r}")

    if not isinstance(entry["approved"], bool):
        raise ValueError("approved harus true atau false")

    date.fromisoformat(entry["checked"])


def load_registry(path=DEFAULT_PATH):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        seen = set()
        marketplaces = []
        brand_sites = []

        for entry in data["marketplaces"]:
            domains = texts(entry["domains"], "domains")

            if not domains:
                raise ValueError("marketplace tanpa domain")

            checked_common(entry, domains, seen)
            marketplaces.append(Marketplace(
                id=entry["id"],
                name=entry["name"],
                domains=domains,
                official_labels=texts(entry["official_labels"], "official_labels"),
                automation=entry["automation"],
                approved=entry["approved"],
                tos_url=entry["tos_url"],
                checked=entry["checked"],
            ))

        for entry in data["brand_sites"]:
            evidence = texts(entry["evidence"], "evidence")
            checked_common(entry, texts([entry["domain"]], "domain"), seen)

            if entry["approved"] and len(evidence) < 2:
                raise ValueError(f"situs brand disetujui tanpa dua bukti: {entry['domain']}")

            brand_sites.append(BrandSite(
                brand=entry["brand"],
                domain=entry["domain"],
                automation=entry["automation"],
                approved=entry["approved"],
                evidence=evidence,
                checked=entry["checked"],
            ))
    except (KeyError, TypeError, OSError) as error:
        raise ValueError(f"daftar toko resmi rusak: {error!r}") from error

    return Registry(tuple(marketplaces), tuple(brand_sites))
