from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Message

import chromadb
import requests
import uuid
from pathlib import Path
from datetime import datetime, timezone


LOGIN_REQUIRED = (
    "Long-term memory hanya tersedia untuk pengguna yang login. "
    "Informasi ini TIDAK disimpan."
)


class CielMemoryStore(Component):
    display_name = "Ciel Memory Store"
    description = (
        "Menyimpan informasi jangka panjang milik pengguna aktif ke Chroma "
        "lokal menggunakan embedding Ollama."
    )
    icon = "database"

    inputs = [
        MessageTextInput(
            name="memory_text",
            display_name="Memory Text",
            info="Informasi yang ingin disimpan ke long-term memory.",
            tool_mode=True,
        ),
        # Diisi oleh app lewat tweaks, bukan oleh Agent (tool_mode=False).
        # Jangan dinamai `user_id`: Component Langflow sudah punya atribut
        # bawaan `user_id` (akun Langflow pemilik flow) yang menimpa input ini.
        MessageTextInput(
            name="memory_owner",
            display_name="Memory Owner",
            info=(
                "ID pemilik memory, dikirim app lewat tweaks. "
                "Kosong = pengguna anonim, memory dinonaktifkan."
            ),
            advanced=True,
            tool_mode=False,
        ),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Memory Result",
            method="save_memory",
        ),
    ]

    def save_memory(self) -> Message:
        text = (self.memory_text or "").strip()

        if not text:
            raise ValueError("Memory Text tidak boleh kosong.")

        user_id = str(self.memory_owner or "").strip()

        if not user_id:
            return Message(text=LOGIN_REQUIRED)

        # ==============================
        # KONFIGURASI
        # ==============================
        ollama_url = "http://127.0.0.1:11434/api/embed"
        embedding_model = "nomic-embed-text-v2-moe:latest"

        db_path = Path.home() / ".ciel_ai" / "long_term_memory"
        db_path.mkdir(parents=True, exist_ok=True)

        collection_name = "ciel_long_term_memory"

        # ==============================
        # 1. EMBEDDING OLLAMA
        # ==============================
        try:
            response = requests.post(
                ollama_url,
                json={
                    "model": embedding_model,
                    "input": text,
                    # Ollama unloads a model after 5 idle minutes; reloading
                    # this one took 14 s on the Langflow PC (2026-10-17).
                    "keep_alive": "1h",
                },
                timeout=120,
            )
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Gagal menghubungi Ollama: {exc}"
            ) from exc

        if response.status_code != 200:
            raise RuntimeError(
                f"Ollama embedding gagal.\n"
                f"Status: {response.status_code}\n"
                f"Response: {response.text}"
            )

        data = response.json()

        try:
            embedding = data["embeddings"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"Response embedding Ollama tidak sesuai:\n{data}"
            ) from exc

        # ==============================
        # 2. CHROMA PERSISTENT
        # ==============================
        try:
            client = chromadb.PersistentClient(
                path=str(db_path)
            )

            collection = client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            raise RuntimeError(
                f"Gagal membuka Chroma:\n{exc}"
            ) from exc

        # ==============================
        # 3. SIMPAN MEMORY
        # ==============================
        memory_id = f"memory_{uuid.uuid4().hex}"
        timestamp = datetime.now(timezone.utc).isoformat()

        try:
            collection.add(
                ids=[memory_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[
                    {
                        "created_at": timestamp,
                        "source": "ciel_memory_engine",
                        "user_id": user_id,
                    }
                ],
            )
        except Exception as exc:
            raise RuntimeError(
                f"Gagal menyimpan memory ke Chroma:\n{exc}"
            ) from exc

        # ==============================
        # 4. OUTPUT MESSAGE
        # ==============================
        # Tanpa ID, jumlah total, atau path DB: Agent tidak butuh itu dan
        # jumlah total lintas pengguna tidak boleh terlihat.
        return Message(text="Memory berhasil disimpan.")
