"""Loop agent: satu tugas dari perintah sampai laporan (docs/agent-architecture.md bagian 2).

Urutan setiap putaran selalu sama: model mengusulkan satu tool, usulan itu
diikat ke aksi guard memakai fakta dari klien (agent_api.tools.bind), guard
memutuskan (guard.decide.decide), baris log ditulis, baru aksi dikirim ke
klien. Tidak ada jalur lain menuju klien, dan run_task tidak pernah melempar
exception: apa pun yang tidak terduga mengakhiri tugas.

Kontrak klien (ekstensi atau desktop, lewat adaptor di rencana 2B):
    active() -> bool                    perangkat masih tersambung dan belum dicabut
    show_plan(steps, scope) -> str      "ask" atau "auto" kalau disetujui, selain itu ditolak
    confirm(prompt) -> bool             pengguna menyetujui satu aksi
    handover(prompt) -> bool            pengguna mengerjakan sendiri langkah itu
    ask(question) -> str | None         jawaban pengguna
    run(tool, args, seq) -> Observation hasil aksi

Pembelian belum bisa di fase ini: toko tidak diverifikasi (store=None), jadi
gerbang belanja di guard selalu menolak.
"""

import re
from dataclasses import dataclass, replace

from agent_api.envelope import flags_injection, wrap
from agent_api.journal import Journal
from agent_api.limits import day_start, over_limit, start_refusal, task_rate_limits
from agent_api.model import ModelReply, Step, TaskView
from agent_api.plan import parse_plan, scope_to_json, widened
from agent_api.tools import Observation, Rejected, bind
from guard.audit import target_of
from guard.decide import Context, Decision, decide
from guard.limits import SpendLimits
from guard.risk import R3, Action

URL_RE = re.compile(r"https?://[^\s\"'<>()]+", re.IGNORECASE)
MAX_NOTE = 2000


@dataclass(frozen=True)
class Account:
    plan: str                    # nama paket, misalnya "free" atau "pro"
    adult_verified: bool
    limits: SpendLimits
    spent_this_month: int


@dataclass(frozen=True)
class ConfirmPrompt:
    """Isi dialog konfirmasi. Dihitung kode, tidak pernah dari ringkasan model."""

    tool: str
    target: str
    level: str
    reason: str
    widens: str | None      # situs atau jenis aksi yang ditambahkan ke lingkup, kalau ada
    from_page: bool         # tujuan aksi berasal dari isi halaman, tidak dari perintah pengguna


@dataclass(frozen=True)
class TaskResult:
    status: str             # "done" | "stopped" | "failed" | "refused"
    reason: str | None
    steps: int
    report: str


class End(Exception):
    """Tugas berakhir dengan status dan alasan ini."""

    def __init__(self, status, reason, report=""):
        super().__init__(status, reason)
        self.status = status
        self.reason = reason
        self.report = report


def urls_in(text):
    return {url.rstrip(".,;:!?").casefold() for url in URL_RE.findall(text)}


def run_task(owner, task_id, device, instruction, *, model, client, store, config, account, clock, chain_key):
    """Jalankan satu tugas. Selalu mengembalikan TaskResult."""

    run = None

    try:
        run = Run(owner, task_id, device, instruction, model, client, store, config, account, clock, chain_key)
        refusal = run.start()

        if refusal:
            return TaskResult("refused", refusal, 0, "")

        try:
            run.plan()

            while True:
                run.turn()
        except End as end:
            status, reason, report = end.status, end.reason, end.report

        run.close(status, reason)
        return TaskResult(status, reason, run.steps, report)
    except Exception:
        # Gagal berarti berhenti. Baris tugas ditutup supaya akun tidak terkunci.
        steps = 0

        if run is not None and run.created:
            steps = run.steps

            try:
                run.close("failed", "internal_error")
            except Exception:
                pass

        return TaskResult("failed", "internal_error", steps, "")


class Run:

    def __init__(self, owner, task_id, device, instruction, model, client, store, config, account, clock, chain_key):
        self.owner = owner
        self.task_id = task_id
        self.device = device
        self.instruction = instruction
        self.model = model
        self.client = client
        self.store = store
        self.config = config
        self.account = account
        self.clock = clock
        self.journal = Journal(store, chain_key, owner, device, task_id)

        self.created = False
        self.steps = 0
        self.cost = 0
        self.repairs = 0
        self.mode = "ask"
        self.scope = None
        self.plan_steps = ()
        self.started = None
        self.page = None            # pengamatan terakhir yang berhasil, sumber fakta untuk bind
        self.observation = ""       # amplop yang dilihat model di putaran berikutnya
        self.untrusted = []         # semua isi tidak tepercaya yang sudah dilihat tugas ini
        self.history = []
        self.notes = []

    # Awal dan akhir -----------------------------------------------------

    def start(self):
        """Alasan tugas ditolak, atau None kalau tugas sudah dibuat."""

        now = self.clock()
        refusal = start_refusal(self.config, self.account.plan, self.store.cost_since(day_start(now)))

        if refusal:
            return refusal

        created = self.store.create_task(self.owner, self.task_id, self.device, self.instruction)

        if created != "created":
            return "busy" if created == "busy" else "unavailable"

        self.created = True

        # Kuota dihitung setelah tugas dibuat, supaya permintaan ganda yang
        # ditolak "busy" tidak ikut memakan kuota.
        limits = task_rate_limits(self.owner, self.account.plan, self.config)
        reached, full = self.store.rate_limit_hit(limits, now.timestamp())
        refusal = "unavailable" if reached is not True else "rate_limited" if full else None

        if refusal:
            self.close("failed", refusal)

        return refusal

    def close(self, status, reason):
        self.store.update_task(self.owner, self.task_id, status=status, reason=reason, steps=self.steps, cost=self.cost)

    def save(self, **fields):
        if not self.store.update_task(self.owner, self.task_id, **fields):
            raise End("failed", "unavailable")

    # Model dan klien ----------------------------------------------------

    def ask_model(self, method, argument):
        try:
            reply = method(argument)
        except Exception:
            raise End("failed", "model_error") from None

        if not isinstance(reply, ModelReply) or type(reply.cost) is not int or reply.cost < 0:
            raise End("failed", "model_error")

        self.cost += reply.cost
        return reply.output

    def from_client(self, method, *args):
        """Jawaban klien, atau None kalau panggilannya gagal."""

        try:
            return method(*args)
        except Exception:
            return None

    # Rencana ------------------------------------------------------------

    def plan(self):
        plan = parse_plan(self.ask_model(self.model.plan, self.instruction), self.account.limits.per_tx)

        if plan is None:
            raise End("failed", "bad_plan")

        choice = self.from_client(self.client.show_plan, plan.steps, scope_to_json(plan.scope))

        if not isinstance(choice, str) or choice not in ("ask", "auto"):
            raise End("stopped", "plan_rejected")

        self.mode = choice
        self.scope = plan.scope
        self.plan_steps = plan.steps
        self.save(plan={"steps": list(plan.steps)}, scope=scope_to_json(plan.scope), mode=choice, status="running")
        self.started = self.clock()

    # Satu putaran -------------------------------------------------------

    def turn(self):
        reason = over_limit(self.steps, self.started, self.clock(), self.repairs)

        if reason:
            raise End("failed", reason)

        view = TaskView(self.instruction, self.plan_steps, tuple(self.history), tuple(self.notes), self.observation)
        output = self.ask_model(self.model.act, view)
        self.steps += 1

        try:
            self.act(output)
        finally:
            # Hitungan langkah dan biaya disimpan sebisanya. Kalau database
            # mati, penulisan log berikutnya yang menghentikan tugas.
            self.store.update_task(self.owner, self.task_id, steps=self.steps, cost=self.cost)

    def act(self, output):
        bound = bind(output, self.page)

        if isinstance(bound, Rejected):
            self.log(Action(kind=bound.tool), Decision("block", R3, bound.reason))
            self.missed(bound.tool, "block", bound.reason, None)
            return

        tool, args, action = bound.tool, bound.args, bound.action
        from_page = False

        # Alamat yang muncul di isi halaman dan tidak disebut pengguna adalah
        # tujuan dari isi tidak tepercaya (docs/security.md bagian 5, lapis 4).
        if tool == "tab_open" and self.seen_url(args["url"]):
            action = replace(action, tainted=True)
            from_page = True

        decision = self.decide(action)
        approved_by = None

        while decision.outcome == "confirm":
            scoped = decision.reason.startswith("scope_")

            # Aksi ini sudah disetujui pengguna di putaran sebelumnya. Yang
            # masih harus ditanyakan hanya perluasan lingkup berikutnya.
            if approved_by and not scoped:
                break

            wider = widened(self.scope, action, decision.reason) if scoped else None

            if scoped and wider is None:
                decision = Decision("block", decision.level, decision.reason)
                break

            widens = self.added(wider)
            shown = from_page or (wider is not None and widens in wider.hosts and self.seen_text(widens))
            prompt = ConfirmPrompt(tool, target_of(action), decision.level, decision.reason, widens, shown)

            if self.from_client(self.client.confirm, prompt) is not True:
                self.log(action, decision, result="declined")
                self.missed(tool, "confirm", decision.reason, "declined")
                return

            approved_by = "user"

            if not scoped:
                break

            # Persetujuan perluasan tidak melewati gerbang lain: aksi yang sama
            # diputuskan lagi dengan lingkup baru. Setiap perluasan (jenis
            # aksi, lalu situs) ditanyakan sendiri-sendiri.
            self.log(action, decision, approved_by, "widened")
            self.scope = wider
            self.save(scope=scope_to_json(wider))
            decision = self.decide(action)

        if decision.outcome == "block":
            self.log(action, decision)
            self.missed(tool, "block", decision.reason, None)
            return

        if decision.outcome == "handover":
            prompt = ConfirmPrompt(tool, target_of(action), decision.level, decision.reason, None, from_page)
            done = self.from_client(self.client.handover, prompt) is True
            self.log(action, decision, result="handed_over" if done else "declined")

            if done:
                # Pengguna baru saja mengerjakan sesuatu di halaman itu, jadi
                # yang terakhir dibaca agent sudah tidak berlaku.
                self.page = None
                self.observation = ""
                self.repairs = 0
                self.history.append(Step(tool, "handover", decision.reason, "handed_over"))
            else:
                self.missed(tool, "handover", decision.reason, "declined")

            return

        if tool == "finish":
            self.log(action, decision, approved_by, "ok")
            raise End("done", None, args["report"])

        if tool == "ask_user":
            answer = self.from_client(self.client.ask, args["question"])
            answered = isinstance(answer, str) and answer != ""
            self.log(action, decision, approved_by, "ok" if answered else "failed")

            if answered:
                self.notes.append(answer[:MAX_NOTE])
                self.repairs = 0
                self.history.append(Step(tool, decision.outcome, decision.reason, "ok"))
            else:
                self.missed(tool, decision.outcome, decision.reason, "failed")

            return

        self.send(tool, args, action, decision, approved_by)

    def send(self, tool, args, action, decision, approved_by):
        # Baris log ditulis sebelum aksi dikirim. Kalau log tidak bisa
        # ditulis, self.log mengakhiri tugas dan klien tidak pernah dipanggil.
        self.log(action, decision, approved_by)
        result = self.from_client(self.client.run, tool, dict(args), self.journal.seq)
        ok = isinstance(result, Observation) and result.ok is True
        self.log(action, decision, approved_by, "ok" if ok else "failed")

        if not ok:
            self.page = None
            self.observation = ""
            self.missed(tool, decision.outcome, decision.reason, "failed")
            return

        text = result.text if isinstance(result.text, str) else ""
        self.page = result
        self.observation = wrap(result.source, text)
        self.untrusted.append(text)
        self.repairs = 0
        self.history.append(Step(tool, decision.outcome, decision.reason, "ok"))

        # Isi yang memuat perintah untuk AI: sisa tugas berjalan di "Tanya dulu".
        if self.mode != "ask" and flags_injection(text):
            self.mode = "ask"
            self.save(mode="ask")

    # Pembantu -----------------------------------------------------------

    def decide(self, action):
        """Keputusan guard. Stop dan klien yang hilang langsung mengakhiri tugas."""

        context = Context(
            stopped=self.store.stop_requested(self.owner, self.task_id) is not False,
            ticket_ok=self.from_client(self.client.active) is True,
            mode=self.mode,
            scope=self.scope,
            adult_verified=self.account.adult_verified,
            limits=self.account.limits,
            spent_this_month=self.account.spent_this_month,
            store=None,
            purchase_total=None,
        )
        decision = decide(action, context)

        if decision.outcome == "block" and decision.reason in ("stopped", "bad_ticket"):
            self.log(action, decision)
            raise End("stopped", "stop") if decision.reason == "stopped" else End("failed", "client_gone")

        return decision

    def log(self, action, decision, approved_by=None, result=None):
        if not self.journal.record(action, decision, self.clock(), approved_by, result):
            raise End("failed", "log_error")

    def missed(self, tool, outcome, reason, result):
        """Catat langkah yang tidak berhasil untuk model, dan hitung percobaannya."""

        self.repairs += 1
        self.history.append(Step(tool, outcome, reason, result))

    def added(self, wider):
        """Yang akan ditambahkan ke lingkup, sebagai teks untuk dialog."""

        if wider is None:
            return None

        new = (wider.hosts - self.scope.hosts) or (wider.kinds - self.scope.kinds)
        return ", ".join(sorted(new)) or None

    def seen_url(self, url):
        url = url.rstrip(".,;:!?").casefold()

        if url in urls_in(self.instruction):
            return False

        return any(url in urls_in(text) for text in self.untrusted)

    def seen_text(self, value):
        value = value.casefold()

        if value in self.instruction.casefold():
            return False

        return any(value in text.casefold() for text in self.untrusted)
