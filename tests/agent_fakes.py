"""Tiruan untuk uji loop agent: penyimpanan di memori dan klien yang mencatat."""

from agent_api.store import TASK_FIELDS
from agent_api.tools import Observation

ACTIVE = ("planning", "running")


class MemoryStore:
    """Tiruan AgentStore. `fail` berisi nama metode yang harus gagal."""

    def __init__(self):
        self.tasks = {}
        self.actions = []
        self.fail = set()
        self.cost_today = 0
        self.full = None     # nama kunci kuota yang penuh, kalau ada
        self.hits = []
        self.now = 0.0       # detik; waktu tiruan untuk updated_at dan token
        self.devices = {}
        self.tokens = {}

    def create_task(self, owner, task_id, device, instruction):
        if "create_task" in self.fail:
            return None

        if any(key[0] == owner and task["status"] in ACTIVE for key, task in self.tasks.items()):
            return "busy"

        self.tasks[(owner, task_id)] = {
            "owner": owner, "id": task_id, "device": device, "instruction": instruction, "plan": {}, "scope": {},
            "mode": "ask", "status": "planning", "reason": None, "steps": 0, "cost": 0, "head_hash": "",
            "stop_requested": False, "updated": self.now,
        }
        return "created"

    def load_task(self, owner, task_id):
        task = self.tasks.get((owner, task_id))
        return None if task is None or "load_task" in self.fail else dict(task)

    def update_task(self, owner, task_id, /, **fields):
        if "update_task" in self.fail or not fields or not set(fields) <= TASK_FIELDS or (owner, task_id) not in self.tasks:
            return False

        self.tasks[(owner, task_id)].update(fields, updated=self.now)
        return True

    def request_stop(self, owner, task_id):
        if "request_stop" in self.fail or (owner, task_id) not in self.tasks:
            return False

        self.tasks[(owner, task_id)]["stop_requested"] = True
        return True

    def stop_requested(self, owner, task_id):
        if "stop_requested" in self.fail or (owner, task_id) not in self.tasks:
            return None

        return self.tasks[(owner, task_id)]["stop_requested"]

    def append_action(self, row):
        if "append_action" in self.fail:
            return False

        self.actions.append(dict(row))
        return True

    def load_actions(self, owner, task_id):
        if "load_actions" in self.fail:
            return None

        return [dict(row) for row in self.actions if row["owner"] == owner and row["task"] == task_id]

    def cost_since(self, since_iso):
        return None if "cost_since" in self.fail else self.cost_today

    def rate_limit_hit(self, limits, now):
        if "rate_limit_hit" in self.fail:
            return False, None

        self.hits.append(limits)
        return True, self.full

    # Perangkat dan token -------------------------------------------------

    def create_device(self, owner, device, name, platform):
        if "create_device" in self.fail or (owner, device) in self.devices:
            return False

        self.devices[(owner, device)] = {"id": device, "name": name, "platform": platform, "created_at": self.now,
                                         "last_seen_at": None, "revoked_at": None}
        return True

    def load_devices(self, owner):
        if "load_devices" in self.fail:
            return None

        return [dict(row) for key, row in self.devices.items() if key[0] == owner]

    def device_active(self, owner, device):
        if "device_active" in self.fail:
            return None

        row = self.devices.get((owner, device))
        return row is not None and row["revoked_at"] is None

    def touch_device(self, owner, device):
        if (owner, device) not in self.devices:
            return False

        self.devices[(owner, device)]["last_seen_at"] = self.now
        return True

    def revoke_device(self, owner, device):
        if "revoke_device" in self.fail or (owner, device) not in self.devices:
            return False

        if self.devices[(owner, device)]["revoked_at"] is None:
            self.devices[(owner, device)]["revoked_at"] = self.now

        self.tokens = {key: row for key, row in self.tokens.items() if not (key[0] == owner and row["device"] == device)}
        return True

    def save_token(self, owner, hash_, kind, expires_at, device=None, challenge=None, redirect=None):
        if "save_token" in self.fail:
            return False

        self.tokens[(owner, hash_)] = {"hash": hash_, "kind": kind, "expires_at": expires_at, "device": device,
                                       "challenge": challenge, "redirect": redirect, "used_at": None}
        return True

    def find_token(self, owner, hash_):
        if "find_token" in self.fail:
            return None

        row = self.tokens.get((owner, hash_))
        return dict(row) if row else None

    def use_token(self, owner, hash_):
        if "use_token" in self.fail:
            return None

        row = self.tokens.get((owner, hash_))

        if row is None or row["used_at"] is not None:
            return None

        row["used_at"] = self.now
        return dict(row)

    def sweep(self, idle_seconds):
        if "sweep" in self.fail:
            return None

        swept = 0

        for task in self.tasks.values():
            if task["status"] in ACTIVE and self.now - task["updated"] > idle_seconds:
                task.update(stop_requested=True, status="failed", reason="swept", updated=self.now)
                swept += 1

        return swept


class FakeClient:
    """Tiruan klien (ekstensi atau desktop).

    `pages` memetakan nama tool ke Observation, atau ke fungsi(args) yang
    mengembalikannya. Tool yang tidak ada di `pages` mengembalikan `page`.
    """

    def __init__(self, mode="auto", approve=True, page=None, pages=None, answer="jawaban", alive=True):
        self.mode = mode
        self.approve = approve
        self.page = page if page is not None else Observation(True, "page", "Beranda toko", "shopee.co.id", {})
        self.pages = pages or {}
        self.answer = answer
        self.alive = alive
        self.on_run = None
        self.plans = []
        self.prompts = []
        self.handovers = []
        self.questions = []
        self.ran = []
        self.seqs = []
        self.hosts = []

    def active(self):
        return self.alive

    def show_plan(self, steps, scope):
        self.plans.append((steps, scope))
        return self.mode

    def confirm(self, prompt):
        self.prompts.append(prompt)
        return self.approve

    def handover(self, prompt):
        self.handovers.append(prompt)
        return self.approve

    def ask(self, question):
        self.questions.append(question)
        return self.answer

    def run(self, tool, args, seq, host):
        self.ran.append((tool, args))
        self.seqs.append(seq)
        self.hosts.append(host)

        if self.on_run:
            self.on_run(self)

        result = self.pages.get(tool, self.page)

        if isinstance(result, Exception):
            raise result

        return result(args) if callable(result) else result
