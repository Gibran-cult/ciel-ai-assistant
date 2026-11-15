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
