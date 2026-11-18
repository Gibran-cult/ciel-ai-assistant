"""Adaptor cadangan Gemini lewat HTTP biasa (keputusan D2 dan D12).

Endpoint, header kunci, bentuk functionCall, finishReason, dan usageMetadata
dicocokkan dengan referensi generateContent di dokumentasi Gemini API pada
18 November 2026. systemInstruction, toolConfig, dan responseJsonSchema
mengikuti bentuk yang lazim dipakai, tetapi belum terbaca langsung di halaman
itu [PERLU DICEK sebelum staging]. Token "thoughts" dihitung sebagai keluaran,
supaya plafon biaya tidak meremehkan pemakaian.
"""

import json

from agent_api.model import ModelError, ModelReply, cost_micro_usd
from agent_api.prompts import ACT_SYSTEM, PLAN_SCHEMA, PLAN_SYSTEM, render_view, tool_specs

BASE = "https://generativelanguage.googleapis.com/v1beta/models"
TIMEOUT = 60
GOOD_FINISH = frozenset({"STOP", "MAX_TOKENS"})


class GeminiModel:

    def __init__(self, session, api_key, model="gemini-3.5-flash-lite"):
        self.session = session
        self.api_key = api_key
        self.model = model
        self.declarations = [
            {"name": spec["name"], "description": spec["description"], "parametersJsonSchema": spec["input_schema"]}
            for spec in tool_specs()
        ]

    def generate(self, system, text, **extra):
        """(bagian jawaban, biaya). Kunci hanya dikirim di header."""

        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            **extra,
        }

        try:
            response = self.session.post(
                f"{BASE}/{self.model}:generateContent",
                headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                json=body, timeout=TIMEOUT,
            )

            if response.status_code >= 400:
                raise ModelError(f"http_{response.status_code}")

            data = response.json()
            usage = data.get("usageMetadata") or {}
            cost = cost_micro_usd(
                self.model, int(usage.get("promptTokenCount") or 0),
                int(usage.get("candidatesTokenCount") or 0) + int(usage.get("thoughtsTokenCount") or 0),
            )
            candidate = data["candidates"][0]
        except ModelError:
            raise
        except Exception as error:
            raise ModelError(type(error).__name__) from None

        if candidate.get("finishReason") not in GOOD_FINISH:
            raise ModelError(f"finish_{candidate.get('finishReason')}", cost)

        return (candidate.get("content") or {}).get("parts") or [], cost, candidate.get("finishReason")

    def plan(self, instruction):
        parts, cost, _ = self.generate(
            PLAN_SYSTEM, instruction, generationConfig={"responseMimeType": "application/json", "responseJsonSchema": PLAN_SCHEMA},
        )

        try:
            plan = json.loads("".join(part.get("text", "") for part in parts))
        except ValueError:
            plan = None

        if not isinstance(plan, dict):
            raise ModelError("bad_plan", cost)

        return ModelReply(plan, cost)

    def act(self, view):
        parts, cost, finish = self.generate(
            ACT_SYSTEM, render_view(view), tools=[{"functionDeclarations": self.declarations}],
            toolConfig={"functionCallingConfig": {"mode": "AUTO"}},
        )
        calls = [part["functionCall"] for part in parts if isinstance(part.get("functionCall"), dict)]

        if len(calls) != 1 or finish == "MAX_TOKENS" or not isinstance(calls[0].get("args", {}), dict):
            return ModelReply({}, cost)

        return ModelReply({"tool": calls[0].get("name"), "args": dict(calls[0].get("args") or {})}, cost)
