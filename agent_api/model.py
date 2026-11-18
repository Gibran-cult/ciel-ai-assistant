"""Antarmuka model untuk loop agent (docs/agent-architecture.md bagian 3).

Loop hanya butuh dua hal dari model: rencana untuk satu perintah, dan satu
usulan aksi per putaran. Adaptor model yang sebenarnya (rencana 2B) cukup
punya dua metode itu. Keluaran model selalu diperlakukan sebagai data yang
belum diperiksa.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelReply:
    output: object   # keluaran mentah model, belum diperiksa
    cost: int        # satuan biaya yang dilaporkan adaptor model


@dataclass(frozen=True)
class Step:
    """Ringkasan satu langkah yang sudah lewat, untuk putaran berikutnya."""

    tool: str
    outcome: str            # "allow" | "confirm" | "block" | "handover"
    reason: str | None
    result: str | None      # "ok", "failed", "declined", "handed_over", atau None


@dataclass(frozen=True)
class TaskView:
    """Semua yang dilihat model di satu putaran."""

    instruction: str                 # perintah pengguna, satu-satunya saluran perintah
    steps: tuple[str, ...]           # rencana yang disetujui pengguna
    history: tuple[Step, ...]
    notes: tuple[str, ...]           # jawaban pengguna untuk ask_user
    observation: str                 # hasil envelope.wrap, atau "" kalau belum ada


FINISH = {"tool": "finish", "args": {"report": "selesai"}}


class ScriptedModel:
    """Model tiruan untuk uji dan uji asap: memutar naskah yang sudah ditulis."""

    def __init__(self, plan, calls, cost=1):
        self._plan = plan
        self._calls = list(calls)
        self.cost = cost
        self.instructions = []
        self.views = []

    def plan(self, instruction):
        self.instructions.append(instruction)

        if isinstance(self._plan, Exception):
            raise self._plan

        return ModelReply(self._plan, self.cost)

    def act(self, view):
        self.views.append(view)
        call = self._calls.pop(0) if self._calls else FINISH

        if isinstance(call, Exception):
            raise call

        return ModelReply(call, self.cost)


# Adaptor model sungguhan (rencana 2B) ------------------------------------

# Harga per token dalam nano-dolar AS. Sumber: docs/agent-architecture.md
# bagian 3 (dicek 14 dan 15 November 2026) dan panduan resmi Anthropic per
# 3 November 2026. Tarif "/long" Haiku berlaku untuk prompt di atas 100.000 token.
PRICES_NANO_USD = {
    "claude-haiku-5-5": {"input": 100, "output": 500, "cache_read": 10, "cache_write": 125},
    "claude-haiku-5-5/long": {"input": 500, "output": 2500, "cache_read": 50, "cache_write": 625},
    "gemini-3.5-flash-lite": {"input": 300, "output": 2500, "cache_read": 300, "cache_write": 300},
}
LONG_PROMPT = 100_000


class ModelError(Exception):
    """Model gagal menjawab. `cost` adalah biaya yang tetap tertagih, kalau ada."""

    def __init__(self, reason, cost=0):
        super().__init__(reason)
        self.cost = cost


def cost_micro_usd(model, input_tokens, output_tokens, cache_read=0, cache_write=0):
    """Biaya satu panggilan dalam mikro-dolar AS, dibulatkan ke atas."""

    prompt = input_tokens + cache_read + cache_write
    prices = PRICES_NANO_USD.get(f"{model}/long") if prompt > LONG_PROMPT else None
    prices = prices or PRICES_NANO_USD[model]
    nano = (input_tokens * prices["input"] + output_tokens * prices["output"]
            + cache_read * prices["cache_read"] + cache_write * prices["cache_write"])
    return -(-nano // 1000)


class FallbackModel:
    """Model utama, lalu cadangan kalau model utama melempar exception apa pun."""

    def __init__(self, primary, backup):
        self.primary = primary
        self.backup = backup

    def call(self, name, argument):
        try:
            return getattr(self.primary, name)(argument)
        except Exception as error:
            spent = error.cost if isinstance(error, ModelError) else 0

        reply = getattr(self.backup, name)(argument)
        return ModelReply(reply.output, reply.cost + spent)

    def plan(self, instruction):
        return self.call("plan", instruction)

    def act(self, view):
        return self.call("act", view)
