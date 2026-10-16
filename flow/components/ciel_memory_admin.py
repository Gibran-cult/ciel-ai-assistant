from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Message

import chromadb
import json
import re
from datetime import datetime
from pathlib import Path


ACTIONS = ("list", "delete", "delete_all")
DATASET_ACTIONS = ("list_datasets", "export_dataset", "delete_dataset", "delete_all_datasets")
MAX_LISTED = 200


# Dataset tersimpan: sama persis di Dataset Store, Table Analyst, ML Analyst
# dan Memory Admin (tests/test_personal_datasets.py).

def owner_dir(owner):
    """
    Folder of the signed-in user's saved datasets, or None. The owner is the
    app's hash of the account (sent through tweaks, never by the Agent); the
    pattern also keeps it from being used as a path.
    """
    owner = str(owner or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", owner):
        return None
    return Path.home() / ".ciel_ai" / "user_datasets" / owner


def saved_tables(owner):
    """The owner's saved datasets as {name: {"text", "truncated": False}}."""
    folder = owner_dir(owner)
    if folder is None or not folder.is_dir():
        return {}
    return {
        path.stem: {"text": path.read_text(encoding="utf-8"), "truncated": False}
        for path in sorted(folder.glob("*.csv"))
    }


class CielMemoryAdmin(Component):
    """
    Lets a signed-in user see and delete their own long-term memories, and
    list, download and delete their saved datasets.

    Runs in its own flow, called directly by the app, never as an Agent tool,
    so the model cannot list or delete memories. Every input is set by the app
    through tweaks; the owner is the app's hash of the signed-in account.
    The result is JSON in the message text.
    """

    display_name = "Ciel Memory Admin"
    description = "Daftar dan hapus long-term memory dan dataset milik pengguna yang login."
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
            info="list, delete, delete_all, list_datasets, export_dataset, delete_dataset, atau delete_all_datasets.",
            advanced=True,
        ),
        MessageTextInput(
            name="memory_id",
            display_name="Memory ID",
            info="ID memory untuk action delete.",
            advanced=True,
        ),
        MessageTextInput(
            name="dataset_name",
            display_name="Dataset Name",
            info="Nama dataset untuk export_dataset dan delete_dataset.",
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
        if action in DATASET_ACTIONS:
            return self.handle_datasets(owner, action)
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

    def handle_datasets(self, owner, action):
        folder = owner_dir(owner)
        if folder is None:
            return {"ok": False, "error": "login_required"}
        saved = saved_tables(owner)

        if action == "list_datasets":
            items = []
            for name, entry in saved.items():
                lines = [line for line in entry["text"].splitlines() if line.strip()]
                items.append({
                    "name": name,
                    "rows": max(len(lines) - 1, 0),
                    "columns": lines[0] if lines else "",
                    "updated_at": datetime.fromtimestamp((folder / f"{name}.csv").stat().st_mtime).isoformat(timespec="minutes"),
                })
            return {"ok": True, "total": len(items), "datasets": items}

        if action == "delete_all_datasets":
            for name in saved:
                (folder / f"{name}.csv").unlink()
            return {"ok": True, "deleted": len(saved)}

        # Only a dataset that belongs to this owner can be read or deleted.
        name = str(self.dataset_name or "").strip()
        if name not in saved:
            return {"ok": False, "error": "not_found"}
        if action == "export_dataset":
            return {"ok": True, "name": name, "text": saved[name]["text"]}
        (folder / f"{name}.csv").unlink()
        return {"ok": True, "deleted": 1}
