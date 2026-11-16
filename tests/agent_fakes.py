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

    def create_task(self, owner, task_id, device, instruction):
        if "create_task" in self.fail:
            return None

        if any(key[0] == owner and task["status"] in ACTIVE for key, task in self.tasks.items()):
            return "busy"

        self.tasks[(owner, task_id)] = {
            "owner": owner, "id": task_id, "device": device, "instruction": instruction, "plan": {}, "scope": {},
            "mode": "ask", "status": "planning", "reason": None, "steps": 0, "cost": 0, "head_hash": "",
            "stop_requested": False,
        }
        return "created"

    def load_task(self, owner, task_id):
        task = self.tasks.get((owner, task_id))
        return None if task is None or "load_task" in self.fail else dict(task)

    def update_task(self, owner, task_id, /, **fields):
        if "update_task" in self.fail or not fields or not set(fields) <= TASK_FIELDS or (owner, task_id) not in self.tasks:
            return False

        self.tasks[(owner, task_id)].update(fields)
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
