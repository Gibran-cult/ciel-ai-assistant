from langflow.custom import Component
from langflow.io import MessageTextInput, IntInput, Output

import chromadb
import requests
from pathlib import Path


LOGIN_REQUIRED = (
    "Long-term memory hanya tersedia untuk pengguna yang login. "
    "Tidak ada memory yang dicari."
)


class CielMemorySearch(Component):
    display_name = "Ciel Memory Search"
    description = (
        "Mencari long-term memory milik pengguna aktif secara semantic "
        "menggunakan Ollama dan Chroma."
    )
    icon = "search"

    inputs = [
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
            info=(
                "Pertanyaan atau konteks yang ingin dicari "
                "dari long-term memory."
            ),
            tool_mode=True,
        ),
        IntInput(
            name="top_k",
            display_name="Top K",
            info="Jumlah memory paling relevan yang dikembalikan.",
            value=5,
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

    # IMPORTANT:
    # Return a primitive string from the tool action.
    # This avoids the current ToolMessage/content serialization problem
    # observed in the Langflow Agent trace, where a returned Message object
    # appears to the Agent as results.content == null.
    outputs = [
        Output(
            name="result",
            display_name="Memory Results",
            method="search_memory",
            types=["str"],
        ),
    ]

    def search_memory(self) -> str:
        query = (self.search_query or "").strip()

        if not query:
            raise ValueError("Search Query tidak boleh kosong.")

        user_id = str(self.memory_owner or "").strip()

        if not user_id:
            return LOGIN_REQUIRED

        ollama_url = "http://127.0.0.1:11434/api/embed"
        embedding_model = "nomic-embed-text-v2-moe:latest"

        db_path = Path.home() / ".ciel_ai" / "long_term_memory"
        collection_name = "ciel_long_term_memory"

        # ------------------------------------------------------
        # 1. Open Chroma and count this user's memories first,
        #    so users without memories skip the embedding call.
        # ------------------------------------------------------
        try:
            client = chromadb.PersistentClient(path=str(db_path))
            collection = client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            owned = collection.get(where={"user_id": user_id}, include=[])
        except Exception as exc:
            raise RuntimeError(
                f"Gagal membuka memory collection:\n{exc}"
            ) from exc

        total = len(owned.get("ids") or [])

        if total == 0:
            return "Belum ada memory yang tersimpan untuk pengguna ini."

        k = max(1, min(int(self.top_k), total))

        # ------------------------------------------------------
        # 2. Embed query
        # ------------------------------------------------------
        try:
            response = requests.post(
                ollama_url,
                json={
                    "model": embedding_model,
                    "input": query,
                },
                timeout=120,
            )
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Gagal menghubungi Ollama: {exc}"
            ) from exc

        if response.status_code != 200:
            raise RuntimeError(
                "Ollama embedding gagal.\n"
                f"Status: {response.status_code}\n"
                f"Response: {response.text}"
            )

        try:
            data = response.json()
            query_embedding = data["embeddings"][0]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"Response embedding Ollama tidak sesuai:\n{response.text}"
            ) from exc

        # ------------------------------------------------------
        # 3. Semantic search, restricted to this user
        # ------------------------------------------------------
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                where={"user_id": user_id},
                include=["documents"],
            )
        except Exception as exc:
            raise RuntimeError(
                f"Gagal melakukan pencarian memory:\n{exc}"
            ) from exc

        documents = results.get("documents", [[]])[0]

        # ------------------------------------------------------
        # 4. Tool-facing result
        #
        # Keep the output compact and plain-text. Do not expose
        # distance, metadata, DB path, or internal IDs to the Agent.
        # ------------------------------------------------------
        lines = [
            "HASIL LONG-TERM MEMORY",
            f"Jumlah hasil: {len(documents)}",
            "",
        ]

        for i, document in enumerate(documents, start=1):
            text = str(document).strip()

            if not text:
                continue

            lines.append(f"[Memory {i}]")
            lines.append(text)
            lines.append("")

        result_text = "\n".join(lines).strip()

        if not result_text:
            return "Tidak ditemukan memory yang relevan."

        return result_text
