"""Batas tugas agent, kuota, plafon biaya harian, dan sakelar fitur.

Angka langkah dan waktu berasal dari docs/agent-architecture.md bagian 2.
Kuota per paket dan plafon biaya tidak ditulis di sini: keduanya dibaca dari
konfigurasi server, dan nilai yang kosong atau rusak berarti menolak tugas
baru.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from guard.limits import JAKARTA

MAX_STEPS = 40      # usulan model per tugas
MAX_SECONDS = 900   # 15 menit
MAX_REPAIRS = 2     # langkah gagal berturut-turut yang masih boleh dicoba ulang
DAY = 86400


@dataclass(frozen=True)
class AgentConfig:
    enabled: bool = False
    daily_cost_cap: int = 0                                  # satuan biaya model, semua pengguna
    tasks_per_day: Mapping = field(default_factory=dict)     # nama paket -> jumlah tugas per hari


def whole(text):
    """Angka bulat tidak negatif dari teks konfigurasi, atau 0."""

    return int(text) if isinstance(text, str) and text.isascii() and text.isdigit() else 0


def load_config(env):
    """Konfigurasi agent dari environment server. Tidak pernah melempar exception."""

    quotas = {
        name: whole(env[key])
        for name, key in (("free", "AGENT_TASKS_PER_DAY_FREE"), ("pro", "AGENT_TASKS_PER_DAY_PRO"))
        if key in env
    }
    return AgentConfig(
        enabled=env.get("AGENT_ENABLED") == "1",
        daily_cost_cap=whole(env.get("AGENT_DAILY_COST_CAP")),
        tasks_per_day=quotas,
    )


def positive(value):
    return type(value) is int and value > 0


def start_refusal(config, plan_name, cost_today):
    """Alasan tugas baru ditolak, atau None kalau boleh mulai."""

    if config.enabled is not True:
        return "agent_off"

    cap = config.daily_cost_cap

    # Biaya hari ini yang tidak terbaca dihitung sebagai plafon terlewati.
    if not positive(cap) or type(cost_today) is not int or not 0 <= cost_today < cap:
        return "cost_cap"

    if not positive(config.tasks_per_day.get(plan_name)):
        return "no_quota"

    return None


def task_rate_limits(owner, plan_name, config):
    """Batas tugas per hari, dalam bentuk yang diterima ChatStore.rate_limit_hit."""

    return {f"agent:{owner}": (config.tasks_per_day[plan_name], DAY)}


def day_start(now):
    """Pukul 00.00 hari ini di Asia/Jakarta, ISO 8601."""

    return now.astimezone(JAKARTA).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def over_limit(steps, started, now, repairs):
    """Alasan tugas harus berhenti, atau None."""

    if steps >= MAX_STEPS:
        return "limit_steps"

    if (now - started).total_seconds() > MAX_SECONDS:
        return "limit_time"

    if repairs > MAX_REPAIRS:
        return "stuck"

    return None
