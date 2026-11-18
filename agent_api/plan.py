"""Rencana tugas dan lingkup yang diturunkan darinya (docs/agent-architecture.md bagian 2).

Model mengusulkan rencana: langkah-langkah, situs, jenis aksi, dan batas
belanja. Kode di sini memeriksa usulan itu dan mengubahnya menjadi TaskScope.
Setelah pengguna menyetujuinya, lingkup hanya bisa melebar lewat persetujuan
pengguna, satu situs atau satu jenis aksi setiap kali.

Rencana yang meminta sesuatu yang tidak boleh ditolak seluruhnya. Membuang
bagian yang salah lalu melanjutkan akan menghasilkan rencana yang tidak
pernah dilihat pengguna.
"""

import re

from dataclasses import dataclass, replace

from guard.domains import match_allowed, normalize_host
from guard.risk import ACTION_LEVELS, BLOCKED_HOSTS, R3
from guard.scope import TaskScope

MAX_PLAN_STEPS = 12
MAX_HOSTS = 10
MAX_STEP_CHARS = 200
PLAN_KEYS = frozenset({"steps", "hosts", "kinds", "spend_cap"})


@dataclass(frozen=True)
class Plan:
    steps: tuple[str, ...]
    scope: TaskScope


def plannable(kind):
    """Benar untuk jenis aksi yang dikenal dan bukan R3."""

    return isinstance(kind, str) and ACTION_LEVELS.get(kind, R3) != R3


# Akhiran yang dipakai banyak pemilik berbeda. Host persis seperti ini
# di lingkup tugas akan cocok dengan semua situs di bawahnya.
PUBLIC_SUFFIXES = frozenset({
    "co.id", "ac.id", "or.id", "go.id", "web.id", "my.id", "biz.id", "sch.id", "net.id", "mil.id", "desa.id", "ponpes.id",
    "github.io", "vercel.app", "netlify.app", "pages.dev", "web.app", "firebaseapp.com", "blogspot.com", "herokuapp.com",
})
TLD_RE = re.compile(r"[a-z]{2,63}")


def allowed_host(host):
    """Host yang sudah dirapikan, atau None kalau tidak sah atau selalu ditolak.

    Yang ditolak: akhiran publik, alamat IP dalam bentuk apa pun (label
    terakhir harus huruf), dan nama punycode (tab_open juga menolaknya).
    """

    host = normalize_host(host)

    if host is None or match_allowed(host, BLOCKED_HOSTS) or host in PUBLIC_SUFFIXES:
        return None

    labels = host.split(".")

    if not TLD_RE.fullmatch(labels[-1]) or any(label.startswith("xn--") for label in labels):
        return None

    return host


def parse_plan(output, per_tx):
    """Plan dari keluaran model, atau None kalau ada bagian yang tidak sah."""

    if not isinstance(output, dict) or not set(output) <= PLAN_KEYS or not {"steps", "kinds"} <= set(output):
        return None

    steps = output["steps"]

    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_PLAN_STEPS:
        return None

    if not all(isinstance(step, str) and 0 < len(step.strip()) <= MAX_STEP_CHARS for step in steps):
        return None

    hosts = output.get("hosts", [])

    if not isinstance(hosts, list) or len(hosts) > MAX_HOSTS:
        return None

    hosts = [allowed_host(host) for host in hosts]

    if None in hosts:
        return None

    kinds = output["kinds"]

    if not isinstance(kinds, list) or not kinds or not all(plannable(kind) for kind in kinds):
        return None

    # Batas belanja tugas tidak boleh melebihi batas per transaksi pengguna.
    ceiling = per_tx if type(per_tx) is int and per_tx > 0 else 0
    spend_cap = output.get("spend_cap", 0)

    if type(spend_cap) is not int or not 0 <= spend_cap <= ceiling:
        return None

    scope = TaskScope(hosts=frozenset(hosts), kinds=frozenset(kinds), spend_cap=spend_cap)
    return Plan(tuple(step.strip() for step in steps), scope)


def widened(scope, action, reason):
    """Lingkup setelah pengguna menyetujui perluasan untuk aksi ini, atau None.

    Yang bisa ditambah hanya satu situs atau jenis aksi dari aksi itu sendiri.
    Aplikasi dan folder belum bisa (menunggu klien desktop), dan batas belanja
    tidak pernah berubah di tengah tugas.
    """

    if reason == "scope_host":
        host = allowed_host(action.host)
        return replace(scope, hosts=scope.hosts | {host}) if host else None

    if reason == "scope_kind":
        kinds = [action.kind] if action.effect is None else [action.kind, action.effect]

        if not all(plannable(kind) for kind in kinds):
            return None

        return replace(scope, kinds=scope.kinds | set(kinds))

    return None


def scope_to_json(scope):
    """Lingkup dalam bentuk yang bisa disimpan dan ditampilkan."""

    return {"hosts": sorted(scope.hosts), "kinds": sorted(scope.kinds), "spend_cap": scope.spend_cap}
