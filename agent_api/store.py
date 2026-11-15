"""Penyimpanan tugas dan log aksi agent di Supabase (docs/agent-architecture.md bagian 6).

Memakai cara yang sama dengan chat_store.ChatStore: service key dari secrets
server, dan setiap permintaan difilter dengan pemilik. Semua metode
mengembalikan None atau False saat gagal dan tidak pernah melempar exception,
supaya loop agent bisa berhenti dengan rapi.
"""

import logging

import requests

from chat_store import OWNER_PATTERN, ROW_ID_PATTERN, TIMEOUT, ChatStore

logger = logging.getLogger("ciel.agent_store")

# Kolom tugas yang boleh diubah loop. stop_requested sengaja tidak ada di
# sini: hanya request_stop yang menyalakannya, dan tidak ada yang mematikannya.
TASK_FIELDS = frozenset({"plan", "scope", "mode", "status", "reason", "steps", "cost", "head_hash"})

ACTION_LIMIT = 500


def valid_id(value):
    return isinstance(value, str) and ROW_ID_PATTERN.match(value) is not None


def valid_owner(value):
    return isinstance(value, str) and OWNER_PATTERN.match(value) is not None


class AgentStore(ChatStore):

    def _post(self, action, path, body):
        """Kirim satu POST. Kembalikan response, atau None kalau jaringan gagal."""

        try:
            return requests.post(
                f"{self.base}/{path}",
                headers={**self.headers, "Prefer": "return=minimal"},
                json=body,
                timeout=TIMEOUT,
            )
        except requests.exceptions.RequestException as error:
            logger.error("agent_store_error action=%s type=%s error=%s", action, type(error).__name__, error)
            return None

    def _rows(self, action, owner, table, row_id=None, **params):
        """Baris milik pemilik ini, atau None kalau gagal atau jawabannya bukan daftar."""

        response = self._request("GET", action, owner, table, row_id, params=params)

        if response is None:
            return None

        try:
            rows = response.json()
        except ValueError as error:
            logger.error("agent_store_error action=%s type=%s error=%s", action, type(error).__name__, error)
            return None

        return rows if isinstance(rows, list) else None

    def create_task(self, owner, task_id, device, instruction):
        """ "created", "busy" kalau akun ini masih punya tugas aktif, atau None kalau gagal."""

        if not valid_owner(owner) or not valid_id(task_id) or not valid_id(device):
            logger.error("agent_store_rejected action=create_task")
            return None

        if not isinstance(instruction, str) or not instruction:
            return None

        row = {"owner": owner, "id": task_id, "device": device, "instruction": instruction, "status": "planning"}
        response = self._post("create_task", "agent_tasks", row)

        if response is None:
            return None

        # 409: indeks agent_tasks_one_active menolak tugas aktif kedua.
        if response.status_code == 409:
            return "busy"

        if response.status_code >= 400:
            logger.error("agent_store_error action=create_task status=%s", response.status_code)
            return None

        return "created"

    def load_task(self, owner, task_id):
        if not valid_id(task_id):
            return None

        rows = self._rows("load_task", owner, "agent_tasks", task_id, select="*")

        if not rows or not isinstance(rows[0], dict):
            return None

        return rows[0]

    def _patch_task(self, action, owner, task_id, body):
        if not valid_id(task_id):
            return False

        response = self._request(
            "PATCH", action, owner, "agent_tasks", task_id, json=body, headers={"Prefer": "return=minimal"},
        )
        return response is not None

    def update_task(self, owner, task_id, /, **fields):
        if not fields or not set(fields) <= TASK_FIELDS:
            logger.error("agent_store_rejected action=update_task")
            return False

        return self._patch_task("update_task", owner, task_id, fields)

    def request_stop(self, owner, task_id):
        return self._patch_task("request_stop", owner, task_id, {"stop_requested": True})

    def stop_requested(self, owner, task_id):
        """True atau False, atau None kalau statusnya tidak terbaca."""

        if not valid_id(task_id):
            return None

        rows = self._rows("stop_requested", owner, "agent_tasks", task_id, select="stop_requested")

        if not rows or not isinstance(rows[0], dict):
            return None

        value = rows[0].get("stop_requested")
        return value if isinstance(value, bool) else None

    def append_action(self, row):
        """Tambah satu baris log aksi. Baris yang sudah ada tidak pernah diubah."""

        if not isinstance(row, dict) or not valid_owner(row.get("owner")) or not valid_id(row.get("task")):
            logger.error("agent_store_rejected action=append_action")
            return False

        if type(row.get("seq")) is not int or row["seq"] < 1:
            return False

        response = self._post("append_action", "agent_actions", row)

        if response is None or response.status_code >= 400:
            return False

        return True

    def load_actions(self, owner, task_id):
        if not valid_id(task_id):
            return None

        return self._rows(
            "load_actions", owner, "agent_actions",
            task=f"eq.{task_id}", select="*", order="seq.asc", limit=str(ACTION_LIMIT),
        )

    def cost_since(self, since_iso):
        """Jumlah biaya model semua tugas sejak waktu itu, atau None kalau tidak terbaca."""

        if not isinstance(since_iso, str) or not since_iso:
            return None

        response = self._post("cost_since", "rpc/ciel_agent_cost_since", {"p_since": since_iso})

        if response is None or response.status_code >= 400:
            return None

        try:
            total = response.json()
        except ValueError:
            return None

        return total if type(total) is int and total >= 0 else None
