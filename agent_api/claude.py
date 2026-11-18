"""Adaptor model Claude untuk loop agent (keputusan D2 dan D12).

Satu putaran adalah satu permintaan baru ke Messages API: prompt sistem yang
dibekukan dan di-cache, lalu satu pesan pengguna berisi render_view. Riwayat
blok thinking tidak dikirim ulang, jadi aturan Haiku 5.5 tentang pengeditan
riwayat tidak berlaku. Yang tidak dikirim karena 400 di Haiku 5.5:
temperature, top_p, top_k, prefill, dan budget_tokens.
"""

import json

from agent_api.model import ModelError, ModelReply, cost_micro_usd
from agent_api.prompts import ACT_SYSTEM, PLAN_SCHEMA, PLAN_SYSTEM, render_view, tool_specs


class ClaudeModel:

    def __init__(self, client, model="claude-haiku-5-5", effort="medium", max_tokens=8000):
        self.client = client
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.tools = tool_specs()

    def cost(self, response):
        usage = response.usage
        return cost_micro_usd(
            self.model, usage.input_tokens or 0, usage.output_tokens or 0,
            getattr(usage, "cache_read_input_tokens", 0) or 0, getattr(usage, "cache_creation_input_tokens", 0) or 0,
        )

    def create(self, system, **request):
        try:
            response = self.client.messages.create(
                model=self.model, max_tokens=self.max_tokens,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                **request,
            )
        except Exception as error:
            raise ModelError(type(error).__name__) from None

        # Penolakan keamanan tetap tertagih. Haiku 5.5 tidak punya fallback
        # di sisi server, jadi cadangan dipanggil oleh FallbackModel.
        if response.stop_reason == "refusal":
            raise ModelError("refusal", self.cost(response))

        return response

    def plan(self, instruction):
        response = self.create(
            PLAN_SYSTEM, messages=[{"role": "user", "content": instruction}],
            output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": PLAN_SCHEMA}},
        )
        texts = [block.text for block in response.content if block.type == "text"]

        try:
            plan = json.loads(texts[0]) if len(texts) == 1 else None
        except ValueError:
            plan = None

        if not isinstance(plan, dict):
            raise ModelError("bad_plan", self.cost(response))

        return ModelReply(plan, self.cost(response))

    def act(self, view):
        response = self.create(
            ACT_SYSTEM, messages=[{"role": "user", "content": render_view(view)}], tools=self.tools,
            tool_choice={"type": "auto", "disable_parallel_tool_use": True}, output_config={"effort": self.effort},
        )
        calls = [block for block in response.content if block.type == "tool_use"]

        # Tanpa panggilan, lebih dari satu, atau jawaban terpotong: usulan
        # kosong, yang ditolak bind sebagai bad_call dan dihitung langkah gagal.
        if len(calls) != 1 or response.stop_reason == "max_tokens":
            return ModelReply({}, self.cost(response))

        return ModelReply({"tool": calls[0].name, "args": dict(calls[0].input)}, self.cost(response))
