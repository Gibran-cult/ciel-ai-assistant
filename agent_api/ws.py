"""WebSocket Ciel Agent API dan jembatannya ke loop agent (rencana 2B, Task 8).

Loop 2A sinkron dan memanggil kontrak klien (show_plan, confirm, run, dan
lainnya) satu per satu. Setiap tugas berjalan di thread sendiri. WsClient
mengubah setiap panggilan menjadi satu pesan ke koneksi, lalu menunggu
balasan dengan `id` atau `seq` yang cocok. Batas waktu, koneksi putus, atau
pesan stop menghasilkan None, yang dibaca loop sebagai "tidak".

Protokolnya ditulis di docs/agent-protocol.md.
"""

import asyncio
import json
import logging
import os
import secrets
import threading
from collections.abc import Mapping
from dataclasses import asdict, fields
from datetime import timedelta

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agent_api.devices import authenticate
from guard.audit import AuditEvent, explain_chain
from agent_api.limits import CONFIRM_SECONDS, day_start
from agent_api.loop import Account, run_task
from agent_api.tickets import make_ticket
from agent_api.tools import Control, Observation
from guard.limits import SpendLimits

logger = logging.getLogger("ciel.agent_api.ws")

HELLO_SECONDS = 10
PLAN_SECONDS = 300        # rencana dan pertanyaan ask_user
DIALOG_SECONDS = CONFIRM_SECONDS + 10   # loop sendiri menolak jawaban setelah 120 detik
RUN_SECONDS = 60
SEND_SECONDS = 5
MAX_MESSAGE = 256 * 1024
ACTION_LIMIT = (30, 60)   # aksi per menit per akun
EVENT_FIELDS = tuple(item.name for item in fields(AuditEvent))

# Kunci persis setiap pesan dari klien.
CLIENT_MESSAGES = {
    "hello": {"type", "token", "client", "version"},
    "start": {"type", "instruction"},
    "answer": {"type", "id", "value"},
    "result": {"type", "task", "seq", "observation"},
    "stop": {"type"},
}
# Kunci yang boleh ada tetapi tidak wajib. Klien lama mengirim start tanpa page.
OPTIONAL_KEYS = {"start": frozenset({"page"})}
CLIENTS = frozenset({"extension", "desktop"})
OBSERVATION_KEYS = frozenset({"ok", "source", "text", "host", "controls"})
CONTROL_KEYS = frozenset({"field_type", "submits", "effect"})


def parse_message(text):
    """Pesan klien yang bentuknya sah, atau None."""

    if not isinstance(text, str) or len(text) > MAX_MESSAGE:
        return None

    try:
        message = json.loads(text)
    except ValueError:
        return None

    if not isinstance(message, dict) or message.get("type") not in CLIENT_MESSAGES:
        return None

    required = CLIENT_MESSAGES[message["type"]]
    allowed = required | OPTIONAL_KEYS.get(message["type"], frozenset())
    return message if required <= set(message) <= allowed else None


def optional_text(value):
    return value is None or isinstance(value, str)


def observation_from(data):
    """Observation dari balasan klien, atau None kalau bentuknya tidak sah."""

    if not isinstance(data, Mapping) or not set(data) <= OBSERVATION_KEYS or type(data.get("ok")) is not bool:
        return None

    if not all(optional_text(data.get(key)) for key in ("source", "text", "host")):
        return None

    raw = data.get("controls") or {}

    if not isinstance(raw, Mapping):
        return None

    controls = {}

    for ref, control in raw.items():
        if not isinstance(ref, str) or not ref.isdigit() or len(ref) > 6 or not isinstance(control, Mapping):
            return None

        if not set(control) <= CONTROL_KEYS or not optional_text(control.get("field_type")) or not optional_text(control.get("effect")):
            return None

        if control.get("submits") not in (None, True, False):
            return None

        controls[int(ref)] = Control(control.get("field_type"), control.get("submits"), control.get("effect"))

    return Observation(data["ok"], data.get("source") or "tool", data.get("text") or "", data.get("host"), controls)


def version_tuple(text):
    parts = text.split(".") if isinstance(text, str) else []

    if len(parts) != 3 or not all(part.isdigit() and len(part) <= 4 for part in parts):
        return None

    return tuple(int(part) for part in parts)


class Connection:
    """Satu koneksi WebSocket: kirim pesan dari thread mana pun, dan kotak balasan."""

    def __init__(self, websocket, loop):
        self.websocket = websocket
        self.loop = loop
        self.lock = asyncio.Lock()
        self.closed = False
        self.stopped = False
        self.guard = threading.Lock()
        self.waiting = {}         # (jenis, nomor) -> [threading.Event, nilai]
        self.counter = 0
        self.task_id = None       # tugas yang sedang berjalan di koneksi ini

    async def send(self, message, action=False):
        """Kirim satu pesan. Aksi tidak dikirim lagi setelah stop atau koneksi ditutup."""

        async with self.lock:
            # Pesan stop diproses di thread event loop yang sama, jadi
            # pemeriksaan ini dan penandaan stop tidak bisa saling menyalip.
            if action and (self.stopped or self.closed):
                return False

            await self.websocket.send_json(message)
            return True

    def send_from_thread(self, message, action=False):
        """Kirim dari thread tugas. False kalau pesan tidak terkirim."""

        if self.closed:
            return False

        try:
            future = asyncio.run_coroutine_threadsafe(self.send(message, action), self.loop)
            return future.result(timeout=SEND_SECONDS) is True
        except Exception:
            self.close()
            return False

    def next_id(self):
        with self.guard:
            self.counter += 1
            return self.counter

    def expect(self, key):
        with self.guard:
            self.waiting[key] = [threading.Event(), None]

    def deliver(self, key, value):
        """Serahkan balasan ke penunggunya.

        Balasan yang tidak sedang ditunggu diabaikan, dan hanya balasan
        pertama yang dihitung. Slot tetap ada sampai wait mengambilnya,
        supaya balasan yang datang lebih cepat dari wait tidak hilang.
        """

        with self.guard:
            slot = self.waiting.get(key)

            if slot is None or slot[0].is_set():
                return

            slot[1] = value
            slot[0].set()

    def wait(self, key, seconds):
        with self.guard:
            slot = self.waiting.get(key)

        if slot is None:
            return None

        if not (self.closed or self.stopped):
            slot[0].wait(seconds)

        with self.guard:
            self.waiting.pop(key, None)

        return None if self.closed or self.stopped else slot[1]

    def cancel_all(self):
        with self.guard:
            slots, self.waiting = list(self.waiting.values()), {}

        for slot in slots:
            slot[1] = None
            slot[0].set()

    def close(self):
        self.closed = True
        self.cancel_all()


class WsClient:
    """Kontrak klien 2A di atas satu koneksi WebSocket."""

    def __init__(self, conn, owner, device, task_id, signer, store, clock):
        self.conn = conn
        self.owner = owner
        self.device = device
        self.task_id = task_id
        self.signer = signer
        self.store = store
        self.clock = clock

    def now(self):
        return int(self.clock().timestamp())

    def dialog(self, kind, seconds, **fields):
        number = self.conn.next_id()
        self.conn.expect(("answer", number))

        if not self.conn.send_from_thread({"type": kind, "id": number, **fields}):
            return None

        return self.conn.wait(("answer", number), seconds)

    def active(self):
        # Stop tidak dihitung di sini: stop dilaporkan lewat stopped(),
        # supaya tugas berakhir "stopped", tidak "client_gone".
        if self.conn.closed:
            return False

        return self.store.device_active(self.owner, self.device) is True

    def stopped(self):
        return self.conn.stopped

    def show_plan(self, steps, scope):
        value = self.dialog("plan", PLAN_SECONDS, steps=list(steps), scope=scope)
        return value if isinstance(value, str) else None

    def confirm(self, prompt):
        return self.dialog("confirm", DIALOG_SECONDS, prompt=asdict(prompt)) is True

    def handover(self, prompt):
        return self.dialog("handover", DIALOG_SECONDS, prompt=asdict(prompt)) is True

    def ask(self, question):
        value = self.dialog("ask", PLAN_SECONDS, question=question)
        return value if isinstance(value, str) else None

    def run(self, tool, args, seq, host):
        reached, full = self.store.rate_limit_hit({f"agent-act:{self.owner}": ACTION_LIMIT}, self.now())

        # Batas aksi per menit: aksi ini tidak dikirim, dan loop menghitungnya gagal.
        if reached is not True or full:
            return Observation(False)

        if self.conn.stopped or self.conn.closed:
            return None

        # Nomor urut mulai dari 1 di setiap tugas, jadi penunggunya dikunci
        # dengan ID tugas juga: hasil terlambat dari tugas lama tidak pernah
        # dipakai untuk tugas berikutnya di koneksi yang sama.
        key = ("result", self.task_id, seq)
        signed = self.signer.sign(make_ticket(self.task_id, self.device, seq, tool, args, host, self.now()))
        self.conn.expect(key)

        if not self.conn.send_from_thread({"type": "action", **signed}, action=True):
            return None

        return observation_from(self.conn.wait(key, RUN_SECONDS))


class TaskRunner:
    """Thread tugas yang sedang berjalan di proses ini, dan pembersih tugas macet."""

    def __init__(self, store):
        self.store = store
        self.threads = set()
        self.guard = threading.Lock()

    def start(self, target):
        thread = threading.Thread(target=target, daemon=True)

        with self.guard:
            self.threads = {item for item in self.threads if item.is_alive()} | {thread}

        thread.start()
        return thread

    def join(self, timeout=None):
        with self.guard:
            threads = list(self.threads)

        for thread in threads:
            thread.join(timeout)

    def sweep_once(self):
        swept = self.store.sweep(900)

        if swept:
            logger.warning("tasks_swept count=%s", swept)

        return swept

    def check_chains(self, key, now, limit=200):
        """Periksa rantai log tugas yang sudah selesai dan simpan hasilnya (keputusan D14).

        Tugas diperiksa lagi sehari sekali, supaya catatan yang diubah
        setelah pemeriksaan pertama tetap ketahuan. Log yang tidak terbaca
        dilewati, tidak ditandai.
        """

        tasks = self.store.tasks_to_check((now - timedelta(hours=24)).isoformat(), limit)
        checked = 0

        for task in tasks or []:
            owner, task_id = task.get("owner"), task.get("id")
            rows = self.store.load_actions(owner, task_id)

            if rows is None:
                continue

            try:
                chain = [(AuditEvent(**{name: row[name] for name in EVENT_FIELDS}), row["hash"]) for row in rows]
                status, _ = explain_chain(chain, head=task.get("head_hash") or "", key=key)
            except (KeyError, TypeError, ValueError):
                status = "broken"

            if self.store.save_chain_status(owner, task_id, status, now.isoformat()):
                checked += 1

            if status != "ok":
                logger.warning("chain_problem owner=%s task=%s status=%s", owner, task_id, status)

        return checked

    def retain_once(self):
        removed = self.store.retention()

        if removed:
            logger.info("retention_removed tasks=%s", removed)

        return removed

    def run_job(self, name, job, *args):
        """Jalankan satu pekerjaan pemeliharaan. Galatnya dicatat, tidak menghentikan pekerjaan lain."""

        try:
            return job(*args)
        except Exception as error:
            logger.error("maintenance_failed job=%s type=%s", name, type(error).__name__)
            return None

    async def maintain_forever(self, key, clock):
        """Pembersih tugas macet tiap menit, pemeriksa rantai tiap 10 menit, masa simpan tiap hari."""

        minute = 0
        jobs = {"sweep": lambda: self.sweep_once(), "chains": lambda: self.check_chains(key, clock()),
                "retention": lambda: self.retain_once()}

        while True:
            await asyncio.sleep(60)
            minute += 1

            for name in due_jobs(minute):
                await asyncio.to_thread(self.run_job, name, jobs[name])


def due_jobs(minute):
    """Pekerjaan pemeliharaan untuk menit ke-sekian sejak proses mulai.

    Masa simpan jalan di menit pertama lalu sehari sekali, supaya layanan
    yang sering dimulai ulang (deploy) tetap menjalankannya.
    """

    jobs = ["sweep"]

    if minute % 10 == 0:
        jobs.append("chains")

    if minute % 1440 == 1:
        jobs.append("retention")

    return jobs


def ws_router(settings, store, model, signer, runner, clock):
    router = APIRouter()

    def still_allowed():
        if os.path.exists(settings.switch_file):
            return "agent_off"

        spent = store.cost_since(day_start(clock()))

        if type(spent) is not int or spent >= settings.agent.daily_cost_cap:
            return "cost_cap"

        return None

    def account(owner):
        until = store.load_pro_until(owner)
        plan = "pro" if isinstance(until, (int, float)) and until > clock().timestamp() else "free"
        return Account(plan, False, SpendLimits(), 0)

    def run_one(conn, owner, device, instruction, start_page=None):
        task_id = secrets.token_hex(8)
        conn.task_id = task_id
        end = {"type": "end", "task": task_id, "status": "failed", "reason": "internal_error", "steps": 0, "report": ""}

        # Apa pun yang gagal di sini tetap berakhir dengan pesan end, supaya
        # klien tidak menunggu tanpa batas.
        try:
            client = WsClient(conn, owner, device, task_id, signer, store, clock)
            result = run_task(
                owner, task_id, device, instruction, model=model, client=client, store=store, config=settings.agent,
                account=account(owner), clock=clock, chain_key=settings.chain_key, still_allowed=still_allowed,
                start_page=start_page,
            )
            end.update(status=result.status, reason=result.reason, steps=result.steps, report=result.report)
        except Exception as error:
            logger.error("task_crash owner=%s task=%s type=%s", owner, task_id, type(error).__name__)
        finally:
            logger.info("task_end owner=%s task=%s status=%s reason=%s", owner, task_id, end["status"], end["reason"])
            conn.send_from_thread(end)

    @router.websocket("/v1/ws")
    async def socket(websocket: WebSocket):
        origin = websocket.headers.get("origin")

        # Koneksi diterima dulu lalu ditutup dengan kode, supaya klien dan uji
        # asap melihat 4403. Menutup sebelum accept hanya menjadi HTTP 403.
        await websocket.accept()

        if origin is not None and origin not in settings.ws_origins:
            await websocket.close(code=4403)
            return

        conn = Connection(websocket, asyncio.get_running_loop())
        task = None

        try:
            try:
                hello = parse_message(await asyncio.wait_for(websocket.receive_text(), HELLO_SECONDS))
            except asyncio.TimeoutError:
                await websocket.close(code=4408)
                return

            if hello is None or hello["type"] != "hello" or hello["client"] not in CLIENTS:
                await websocket.close(code=4400)
                return

            found = await asyncio.to_thread(authenticate, store, hello["token"], int(clock().timestamp()))

            if found is None:
                await websocket.close(code=4401)
                return

            version = version_tuple(hello["version"])

            if version is None or version < settings.min_client_version:
                await websocket.close(code=4426)
                return

            owner, device = found
            token = hello["token"]
            await conn.send({"type": "ready", "device": device})

            while True:
                message = parse_message(await websocket.receive_text())

                if message is None or message["type"] == "hello":
                    await websocket.close(code=4400)
                    return

                if message["type"] == "start":
                    # Token dan perangkat diperiksa lagi di setiap start:
                    # perangkat yang sudah dicabut tidak boleh memakai
                    # kuota atau biaya model lewat koneksi lama.
                    again = await asyncio.to_thread(authenticate, store, token, int(clock().timestamp()))

                    if again != (owner, device):
                        await websocket.close(code=4401)
                        return

                    if task is not None and task.is_alive():
                        await conn.send({"type": "end", "task": None, "status": "refused", "reason": "busy", "steps": 0, "report": ""})
                        continue

                    # Persetujuan yang ditarik, atau versi teks persetujuan
                    # yang naik, menahan tugas baru di koneksi yang sudah terbuka.
                    consent = await asyncio.to_thread(store.agent_consent, owner)

                    if consent is not True:
                        reason = "unavailable" if consent is None else "consent_required"
                        await conn.send({"type": "end", "task": None, "status": "refused", "reason": reason, "steps": 0, "report": ""})
                        continue

                    if not isinstance(message["instruction"], str):
                        await websocket.close(code=4400)
                        return

                    # Bacaan tab yang sedang dibuka (task 3.27). Bentuknya sama
                    # dengan observation di result; yang rusak menutup koneksi.
                    start_page = None

                    if message.get("page") is not None:
                        start_page = observation_from(message["page"])

                        if start_page is None:
                            await websocket.close(code=4400)
                            return

                    conn.stopped = False
                    instruction = message["instruction"]
                    task = runner.start(lambda instruction=instruction, page=start_page: run_one(conn, owner, device, instruction, page))
                elif message["type"] == "answer":
                    if type(message["id"]) is int:
                        conn.deliver(("answer", message["id"]), message["value"])
                elif message["type"] == "result":
                    if isinstance(message["task"], str) and type(message["seq"]) is int:
                        conn.deliver(("result", message["task"], message["seq"]), message["observation"])
                else:
                    # Stop: penantian dihentikan dulu, lalu server menolak
                    # semua aksi berikutnya lewat stop_requested.
                    conn.stopped = True
                    conn.cancel_all()

                    if conn.task_id is not None:
                        await asyncio.to_thread(store.request_stop, owner, conn.task_id)
        except WebSocketDisconnect:
            pass
        finally:
            conn.close()

    return router

