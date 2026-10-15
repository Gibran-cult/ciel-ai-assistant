from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Message

import chromadb
import json
from pathlib import Path


ACTIONS = ("list", "delete", "delete_all")
MAX_LISTED = 200


class CielMemoryAdmin(Component):
    """
    Lets a signed-in user see and delete their own long-term memories.

    Runs in its own flow, called directly by the app, never as an Agent tool,
    so the model cannot list or delete memories. Every input is set by the app
    through tweaks; the owner is the app's hash of the signed-in account.
    The result is JSON in the message text.
    """

    display_name = "Ciel Memory Admin"
    description = "Daftar dan hapus long-term memory milik pengguna yang login."
    icon = "shield"

    inputs = [
        # Jangan dinamai `user_id`: Component Langflow sudah punya atribut
        # bawaan `user_id` (akun Langflow pemilik flow) yang menimpa input ini.
        MessageTextInput(
            name="memory_owner",
            display_name="Memory Owner",
            info="ID pemilik memory, dikirim app lewat tweaks.",
            advanced=True,
        ),
        MessageTextInput(
            name="memory_action",
            display_name="Action",
            info="list, delete, atau delete_all.",
            advanced=True,
        ),
        MessageTextInput(
            name="memory_id",
            display_name="Memory ID",
            info="ID memory untuk action delete.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="run_action"),
    ]

    def run_action(self) -> Message:
        return Message(text=json.dumps(self.handle(), ensure_ascii=False))

    def handle(self) -> dict:
        owner = str(self.memory_owner or "").strip()
        action = str(self.memory_action or "").strip().lower()

        if not owner:
            return {"ok": False, "error": "login_required"}
        if action not in ACTIONS:
            return {"ok": False, "error": "unknown_action"}

        collection = chromadb.PersistentClient(
            path=str(Path.home() / ".ciel_ai" / "long_term_memory")
        ).get_or_create_collection(
            name="ciel_long_term_memory",
            metadata={"hnsw:space": "cosine"},
        )
        owned = collection.get(where={"user_id": owner}, include=["documents", "metadatas"])
        ids = owned.get("ids") or []

        if action == "list":
            items = [
                {
                    "id": memory_id,
                    "text": str(document or ""),
                    "created_at": str((metadata or {}).get("created_at") or ""),
                }
                for memory_id, document, metadata in zip(
                    ids, owned.get("documents") or [], owned.get("metadatas") or []
                )
            ]
            items.sort(key=lambda item: item["created_at"], reverse=True)
            return {"ok": True, "total": len(items), "memories": items[:MAX_LISTED]}

        if action == "delete":
            memory_id = str(self.memory_id or "").strip()
            # Only an ID that belongs to this owner can be deleted.
            if memory_id not in ids:
                return {"ok": False, "error": "not_found"}
            collection.delete(ids=[memory_id])
            return {"ok": True, "deleted": 1}

        if ids:
            collection.delete(ids=ids)
        return {"ok": True, "deleted": len(ids)}
