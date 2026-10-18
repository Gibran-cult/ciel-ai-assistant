"""Ciel Vision Router (Langflow custom component).

Menggantikan node Ollama "Vision Preprocessor" yang sebelumnya berada
di antara Chat Input dan Agent.

Masalah desain lama:
- Seluruh teks pesan (termasuk konteks file proyek) dikirim ke model
  vision lokal yang konteksnya hanya 4096 token, sehingga pesan panjang
  gagal dengan "request exceeds the available context size".
- Agent hanya menerima output model vision, bukan pertanyaan asli.
- Pesan tanpa gambar tetap diproses model vision di CPU.

Perilaku baru:
- Tanpa gambar: teks diteruskan apa adanya, tanpa memanggil model vision.
- Ada gambar: model vision hanya menerima gambar + instruksi pendek, lalu
  hasil bacaannya digabung dengan pertanyaan asli untuk Agent.
- Jika model vision gagal, Agent tetap menerima pertanyaan beserta
  keterangan bahwa gambar tidak terbaca (tidak menjatuhkan seluruh flow).

Sejak v1.10.0: jika Vision API Key diisi, gambar dibaca lewat Gemini API
(cepat), dan model lokal hanya dipakai bila API gagal atau terlalu lama.
Sejak v1.10.2: gemini-3.5-flash-lite dulu (1,3-2,7 dtk), lalu
gemini-3.1-flash-lite, masing-masing dibatasi 8 dtk.
Model lokal di CPU laptop butuh ~66 dtk per foto baru (uji 2026-10-18).
"""

import asyncio

import requests
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langflow.custom import Component
from langflow.io import IntInput, MessageInput, MessageTextInput, MultilineInput, Output, SecretStrInput
from langflow.schema.message import Message

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def gemini_parts(images):
    """Gemini inline_data parts from Langflow image dicts ({"image_url": {"url": "data:<mime>;base64,<data>"}})."""
    parts = []
    for item in images:
        url = (item.get("image_url") or {}).get("url") or item.get("url") or ""
        header, _, data = url.partition(",")
        if not header.startswith("data:") or ";base64" not in header or not data:
            raise ValueError("gambar bukan data URL base64")
        parts.append({"inline_data": {"mime_type": header[5:].split(";")[0], "data": data}})
    return parts


def gemini_text(response_json):
    parts = ((response_json.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts if not part.get("thought")).strip()
    if not text:
        raise ValueError("Gemini tidak mengembalikan teks")
    return text

DEFAULT_SYSTEM_PROMPT = """Kamu adalah Vision Preprocessor universal.

TUGAS:
Baca dan ekstrak informasi yang terlihat pada gambar.
Kamu hanya membaca isi gambar.
Jangan menyelesaikan soal.
Jangan memberikan jawaban atau analisis.

ATURAN OUTPUT:
1. Gunakan teks biasa.
2. Jangan gunakan LaTeX.
3. Jangan menggunakan karakter backslash "\\".
4. Jangan menggunakan $, $$, \\frac, \\lim, \\sqrt, \\boxed, \\text, \\begin, atau \\end.
5. Pertahankan angka, simbol, rumus, tabel, dan struktur informasi.
6. Gunakan Unicode seperti → × ÷ √ ≤ ≥ ≠ ∪ ∩ ∈.
7. Untuk pecahan gunakan format (pembilang) / (penyebut).
8. Jangan menebak informasi yang tidak terlihat.
9. Jangan menyelesaikan soal.
10. Jika bagian gambar tidak terbaca, nyatakan secara eksplisit."""

IMAGE_HEADER = "### Isi gambar terlampir (dibaca otomatis oleh model vision)"


class CielVisionRouter(Component):
    display_name = "Ciel Vision Router"
    description = (
        "Meneruskan pesan teks langsung ke Agent. Jika ada gambar, gambar "
        "dibaca model vision lalu hasilnya digabung dengan pertanyaan asli."
    )
    icon = "eye"
    name = "CielVisionRouter"

    inputs = [
        MessageInput(name="message", display_name="Message", required=True),
        MessageTextInput(
            name="model_name",
            display_name="Vision Model",
            value="qwen2.5vl:3b",
        ),
        MessageTextInput(
            name="base_url",
            display_name="Ollama Base URL",
            value="http://127.0.0.1:11434",
            advanced=True,
        ),
        MultilineInput(
            name="system_prompt",
            display_name="Vision System Prompt",
            value=DEFAULT_SYSTEM_PROMPT,
            advanced=True,
        ),
        MessageTextInput(
            name="instruction",
            display_name="Vision Instruction",
            value="Baca dan ekstrak semua informasi yang terlihat pada gambar ini.",
            advanced=True,
        ),
        IntInput(
            name="num_ctx",
            display_name="Vision Context Window",
            value=4096,
            advanced=True,
            info="Cukup untuk gambar + instruksi; teks pesan tidak dikirim ke model vision.",
        ),
        SecretStrInput(
            name="vision_api_key",
            display_name="Vision API Key (Gemini)",
            value="",
            required=False,
            info="Kosong = selalu pakai model lokal. Pakai key dari project berbayar: tier gratis memakai data untuk melatih model.",
        ),
        MessageTextInput(
            name="api_model",
            display_name="Vision API Model",
            value="gemini-3.5-flash-lite",
            advanced=True,
        ),
        MessageTextInput(
            name="api_fallback_model",
            display_name="Vision API Model Cadangan",
            value="gemini-3.1-flash-lite",
            advanced=True,
            info="Dicoba jika model utama gagal (misalnya HTTP 503), sebelum model lokal.",
        ),
        IntInput(
            name="api_timeout",
            display_name="Vision API Timeout (detik)",
            value=8,
            advanced=True,
            info="Batas per model API; setelah semua gagal, gambar dibaca model lokal.",
        ),
    ]

    outputs = [
        Output(display_name="Message", name="routed_message", method="route"),
    ]

    def _image_contents(self, message: Message) -> list[dict]:
        if not message.files:
            return []

        probe = Message(
            text=self.instruction,
            sender="User",
            files=list(message.files),
            flow_id=message.flow_id,
        )
        contents = probe.get_file_content_dicts(self.model_name)
        return [item for item in contents if item.get("type") in ("image", "image_url")]

    async def route(self) -> Message:
        message = self.message
        text = message.text if isinstance(message.text, str) else ""

        images = self._image_contents(message)

        if not images:
            self.status = "Tanpa gambar: pesan diteruskan langsung."
            return Message(text=text)

        # Production 2026-10-18: gemini-3.1-flash-lite answered HTTP 503 for a
        # while; the local model then took 136 s. Another Gemini model usually
        # still works, so try it before the local model. In 8 timed photos,
        # gemini-3.5-flash-lite read every one in 1.3-2.7 s, while
        # gemini-3.1-flash-lite took up to 10 s and timed out 3 times.
        api_errors = []
        if self.vision_api_key:
            models = [m for m in dict.fromkeys((self.api_model, self.api_fallback_model)) if m]
            for model in models:
                try:
                    reading = await asyncio.to_thread(self._read_with_api, images, model)
                    self.status = f"{len(images)} gambar dibaca lewat {model}."
                    return Message(text=f"{text}\n\n{IMAGE_HEADER}\n{reading}")
                except Exception as error:  # noqa: BLE001 - coba model berikutnya
                    api_errors.append(f"{model}: {type(error).__name__}: {error}"[:200])

        reading = await self._read_locally(images)
        if api_errors:
            self.status = f"Vision API gagal ({'; '.join(api_errors)}); {self.status}"
        return Message(text=f"{text}\n\n{IMAGE_HEADER}\n{reading}")

    def _read_with_api(self, images, model) -> str:
        response = requests.post(
            GEMINI_URL.format(model=model),
            headers={"x-goog-api-key": str(self.vision_api_key)},
            json={
                "system_instruction": {"parts": [{"text": self.system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": self.instruction}, *gemini_parts(images)]}],
                "generationConfig": {"temperature": 0.1},
            },
            timeout=self.api_timeout,
        )
        if response.status_code != 200:
            # Isi error tanpa key; status cukup untuk melacak masalah billing/kuota.
            raise RuntimeError(f"HTTP {response.status_code}")
        return gemini_text(response.json())

    async def _read_locally(self, images) -> str:
        llm = ChatOllama(
            base_url=self.base_url,
            model=self.model_name,
            num_ctx=self.num_ctx,
            temperature=0.1,
        )

        try:
            result = await llm.ainvoke(
                [
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=[{"type": "text", "text": self.instruction}, *images]),
                ]
            )
            reading = result.content if isinstance(result.content, str) else str(result.content)
            reading = reading.strip() or "(Model vision tidak menemukan teks atau informasi pada gambar.)"
            self.status = f"{len(images)} gambar dibaca."
        except Exception as error:  # noqa: BLE001 - lanjutkan tanpa gambar daripada menggagalkan flow
            reading = f"(Gambar tidak dapat dibaca oleh model vision: {type(error).__name__}: {error})"
            self.status = reading

        return reading
