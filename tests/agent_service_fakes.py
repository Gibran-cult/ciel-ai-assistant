"""Pengaturan dan tiruan bersama untuk uji layanan Ciel Agent API."""

from datetime import datetime, timezone

# Nilai uji palsu. Tidak ada satu pun yang berlaku di luar uji.
ENV = {
    "SUPABASE_URL": "https://contoh.supabase.co",
    "SUPABASE_SERVICE_KEY": "kunci-layanan-uji-0123456789",
    "ANTHROPIC_API_KEY": "kunci-anthropic-uji",
    "GEMINI_API_KEY": "kunci-gemini-uji",
    "GOOGLE_CLIENT_ID": "klien-uji.apps.googleusercontent.com",
    "GOOGLE_CLIENT_SECRET": "rahasia-klien-uji",
    "AGENT_GOOGLE_REDIRECT_URI": "https://agent.contoh.test/v1/device/callback",
    "AGENT_DEVICE_REDIRECTS": "https://abcdefghijklmnop.chromiumapp.org/,ciel://auth",
    "AGENT_WS_ORIGINS": "chrome-extension://abcdefghijklmnop",
    "AGENT_TICKET_KEY": "11" * 32,
    "AGENT_CHAIN_KEY": "22" * 32,
    "AGENT_STATE_KEY": "33" * 32,
    "AGENT_ENABLED": "1",
    "AGENT_DAILY_COST_CAP": "5000000",
    "AGENT_TASKS_PER_MONTH_FREE": "5",
    "AGENT_TASKS_PER_MONTH_PRO": "150",
}

NOW = datetime(2026, 11, 18, 3, 0, tzinfo=timezone.utc)


class Clock:
    """Jam uji yang bisa dimajukan."""

    def __init__(self, start=NOW):
        self.time = start

    def __call__(self):
        return self.time
