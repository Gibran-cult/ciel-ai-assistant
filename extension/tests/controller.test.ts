// @vitest-environment node
import { vi } from "vitest";
import { Controller, type ControllerDeps, type PanelState } from "../src/controller";
import type { Observation } from "../src/shared/protocol";

function setup(over: Partial<ControllerDeps> = {}) {
  let ready = true;
  const states: PanelState[] = [];
  const deps = {
    login: vi.fn(async () => ({ kind: "ok" as const, device: "d1" })),
    logout: vi.fn(async () => undefined),
    hasToken: vi.fn(async () => true),
    socket: {
      start: vi.fn(),
      close: vi.fn(),
      startTask: vi.fn(() => ready),
      answer: vi.fn(() => true),
      sendStop: vi.fn(() => ready),
      get isReady() {
        return ready;
      },
    },
    runner: { begin: vi.fn(), end: vi.fn(), onAction: vi.fn(async () => undefined), refuse: vi.fn(), taskTab: 7 as number | null,
      currentTask: null as string | null,
      readStart: vi.fn(async (): Promise<Observation | null> => null) },
    banner: vi.fn(),
    badge: vi.fn(),
    now: () => new Date(2026, 10, 18, 10, 42),
    broadcast: (state: PanelState) => states.push(state),
    ...over,
  } satisfies ControllerDeps;
  const controller = new Controller(deps);
  return { controller, deps, states, last: () => states.at(-1)!, offline: () => (ready = false) };
}

test("without a token the panel shows sign in; signing in connects", async () => {
  const { controller, deps, last } = setup({ hasToken: vi.fn(async () => false) });
  await controller.init();
  expect(last().auth).toBe("signed_out");
  expect(deps.socket.start).not.toHaveBeenCalled();

  await controller.command({ type: "login" });
  expect(last().auth).toBe("signed_in");
  expect(deps.socket.start).toHaveBeenCalled();
});

test("consent_required sends the user to the web settings", async () => {
  const { controller, last } = setup({
    hasToken: vi.fn(async () => false),
    login: vi.fn(async () => ({ kind: "consent_required" as const })),
  });
  await controller.init();
  await controller.command({ type: "login" });
  expect(last().auth).toBe("consent_required");
});

test("starting a task binds the tab and sends start", async () => {
  const { controller, deps, last } = setup();
  await controller.init();
  await controller.command({ type: "start", instruction: "Cari kaos polos", tabId: 7 });
  expect(deps.runner.begin).toHaveBeenCalledWith(7);
  expect(deps.socket.startTask).toHaveBeenCalledWith("Cari kaos polos", null);
  expect(last()).toMatchObject({ phase: "running", instruction: "Cari kaos polos" });
  expect(deps.banner).toHaveBeenLastCalledWith(7, "active");
  expect(deps.badge).toHaveBeenLastCalledWith("running", false);
});

test("offline, a task does not start and the panel says why", async () => {
  const { controller, deps, last, offline } = setup();
  await controller.init();
  offline();
  controller.onSocketState("closed");
  await controller.command({ type: "start", instruction: "x", tabId: 7 });
  expect(deps.runner.begin).not.toHaveBeenCalled();
  expect(last().phase).toBe("idle");
  expect(last().connection).toBe("closed");
});

test("plan, confirm and ask become dialogs, answered once", async () => {
  const { controller, deps, last } = setup();
  await controller.init();
  await controller.command({ type: "start", instruction: "x", tabId: 7 });

  controller.onServer({ type: "plan", id: 1, steps: ["Buka toko"], scope: { hosts: ["toko.test"], kinds: ["tab_read"], spend_cap: null } });
  expect(last().dialog).toMatchObject({ kind: "plan", id: 1 });
  expect(deps.banner).toHaveBeenLastCalledWith(7, "waiting");
  expect(deps.badge).toHaveBeenLastCalledWith("running", true);
  await controller.command({ type: "answer", id: 1, value: "ask" });
  expect(deps.socket.answer).toHaveBeenCalledWith(1, "ask");
  expect(last().dialog).toBeNull();

  await controller.command({ type: "answer", id: 1, value: "auto" });
  expect(deps.socket.answer).toHaveBeenCalledTimes(1);

  controller.onServer({ type: "confirm", id: 2, prompt: { tool: "tab_click" } });
  await controller.command({ type: "answer", id: 2, value: false });
  expect(deps.socket.answer).toHaveBeenLastCalledWith(2, false);
  expect(last().log.at(-1)).toMatchObject({ result: "Kamu tolak" });
});

test("a handover turns the reader off until Lanjutkan", async () => {
  const { controller, deps, last } = setup();
  await controller.init();
  await controller.command({ type: "start", instruction: "x", tabId: 7 });
  controller.onServer({ type: "handover", id: 4, prompt: { tool: "tab_type", reason: "secret_field" } });
  expect(last()).toMatchObject({ phase: "handover", dialog: { kind: "handover", id: 4 } });
  expect(deps.banner).toHaveBeenLastCalledWith(7, "handover");

  await controller.command({ type: "handover_done", done: true });
  expect(deps.socket.answer).toHaveBeenCalledWith(4, true);
  expect(last()).toMatchObject({ phase: "running", dialog: null });
});

test("stop works offline, clears the dialog and shows Dihentikan", async () => {
  const { controller, deps, last, offline } = setup();
  await controller.init();
  await controller.command({ type: "start", instruction: "x", tabId: 7 });
  controller.onServer({ type: "confirm", id: 2, prompt: { tool: "tab_click" } });
  offline();
  await controller.command({ type: "stop" });
  expect(deps.runner.end).toHaveBeenCalled();
  expect(deps.socket.sendStop).toHaveBeenCalled();
  expect(last()).toMatchObject({ phase: "stopped", dialog: null });
  expect(deps.banner).toHaveBeenLastCalledWith(7, "stopped");
});

test("end shows the report and frees the tab", async () => {
  const { controller, deps, last } = setup();
  await controller.init();
  await controller.command({ type: "start", instruction: "x", tabId: 7 });
  controller.onServer({ type: "end", task: "t1", status: "done", reason: null, steps: 3, report: "Kaos ada di keranjang." });
  expect(last()).toMatchObject({ phase: "idle", dialog: null, ended: { status: "done", report: "Kaos ada di keranjang." } });
  expect(deps.banner).toHaveBeenLastCalledWith(7, null);
  expect(deps.badge).toHaveBeenLastCalledWith("idle", false);
});

test("the user taking over pauses, and Lanjutkan resumes", async () => {
  const { controller, last } = setup();
  await controller.init();
  await controller.command({ type: "start", instruction: "x", tabId: 7 });
  controller.onTakeover(7);
  expect(last().phase).toBe("paused");
  await controller.command({ type: "resume" });
  expect(last().phase).toBe("running");
});

test("actions are logged with the same phrases as the web log", async () => {
  const { controller, last } = setup();
  await controller.init();
  controller.onLog({ tool: "tab_type", host: "toko.test", outcome: "ok" });
  controller.onLog({ tool: "tab_click", host: "toko.test", outcome: "refused" });
  controller.onLog({ tool: "aneh", host: "toko.test", outcome: "failed" });
  expect(last().log).toEqual([
    { time: "10.42", action: "Mengetik di kolom", target: "toko.test", result: "Selesai" },
    { time: "10.42", action: "Mengklik", target: "toko.test", result: "Diblokir" },
    { time: "10.42", action: "Aksi lain (aneh)", target: "toko.test", result: "Gagal" },
  ]);
});

test("a site without permission shows the permission button until granted", async () => {
  const { controller, last } = setup();
  await controller.init();
  controller.onNeedPermission("toko.test");
  expect(last().needPermission).toBe("toko.test");
  await controller.command({ type: "permission_granted" });
  expect(last().needPermission).toBeNull();
});

test("a signed-out socket signs the panel out", async () => {
  const { controller, last } = setup();
  await controller.init();
  controller.onSocketState("signed_out");
  expect(last().auth).toBe("signed_out");
});

test("unknown panel commands are ignored", async () => {
  const { controller, deps } = setup();
  await controller.init();
  await controller.command({ type: "pay" } as never);
  await controller.command(null as never);
  expect(deps.socket.answer).not.toHaveBeenCalled();
});

test("the banner follows the task tab and comes back after a page loads", async () => {
  const { controller, deps } = setup();
  await controller.init();
  await controller.command({ type: "start", instruction: "x", tabId: 7 });
  (deps.runner as { taskTab: number | null }).taskTab = 9;
  controller.onPage();
  expect(deps.banner).toHaveBeenLastCalledWith(9, "active");
});

test("after Stop the stopped banner stays when the server confirms the end", async () => {
  const { controller, deps } = setup();
  await controller.init();
  await controller.command({ type: "start", instruction: "x", tabId: 7 });
  await controller.command({ type: "stop" });
  vi.mocked(deps.banner).mockClear();
  controller.onServer({ type: "end", task: "t1", status: "stopped", reason: "stop", steps: 1, report: "" });
  expect(deps.banner).not.toHaveBeenCalledWith(7, null);
});

test("review: a dropped connection ends the task here too, and held actions never run", async () => {
  const { controller, deps, last } = setup();
  await controller.init();
  await controller.command({ type: "start", instruction: "x", tabId: 7 });
  controller.onTakeover(7);
  controller.onServer({ type: "action", ticket: { task: "t1", seq: 3 }, kid: "k", sig: "s" });
  controller.onServer({ type: "confirm", id: 2, prompt: { tool: "tab_click" } });

  controller.onSocketState("closed");
  expect(last()).toMatchObject({ phase: "idle", dialog: null, ended: { status: "failed", reason: "client_gone" } });
  expect(deps.banner).toHaveBeenLastCalledWith(7, null);
  await controller.command({ type: "resume" });
  await controller.session.idle();
  expect(deps.runner.onAction).not.toHaveBeenCalled();
});

test("review: a drop after Stop keeps the stopped result", async () => {
  const { controller, last } = setup();
  await controller.init();
  await controller.command({ type: "start", instruction: "x", tabId: 7 });
  await controller.command({ type: "stop" });
  controller.onSocketState("closed");
  expect(last()).toMatchObject({ phase: "idle", ended: { status: "stopped", reason: "stop" } });
});

test("review: a drop with no task changes nothing but the connection", async () => {
  const { controller, last } = setup();
  await controller.init();
  controller.onSocketState("connecting");
  expect(last()).toMatchObject({ phase: "idle", ended: null, connection: "connecting" });
});

test("task 3.27: start sends the reading of the open tab", async () => {
  const { controller, deps } = setup();
  const page: Observation = { ok: true, source: "page", text: "Daftar", host: "toko.test", controls: {} };
  vi.mocked(deps.runner.readStart).mockResolvedValue(page);
  await controller.init();
  await controller.command({ type: "start", instruction: "Isi nama", tabId: 7 });
  expect(vi.mocked(deps.runner.begin).mock.invocationCallOrder[0]!).toBeLessThan(vi.mocked(deps.runner.readStart).mock.invocationCallOrder[0]!);
  expect(deps.socket.startTask).toHaveBeenCalledWith("Isi nama", page);
});

test("task 3.27: without a readable tab, start goes without a page", async () => {
  const { controller, deps } = setup();
  await controller.init();
  await controller.command({ type: "start", instruction: "Isi nama", tabId: 7 });
  expect(deps.socket.startTask).toHaveBeenCalledWith("Isi nama", null);
});

test("review: a late end of the stopped task does not close the new task", async () => {
  const { controller, deps, last } = setup();
  await controller.init();
  await controller.command({ type: "start", instruction: "lama", tabId: 7 });
  // Tiket pertama tugas lama mengikat "t1".
  (deps.runner as { currentTask: string | null }).currentTask = "t1";
  await controller.command({ type: "stop" });
  (deps.runner as { currentTask: string | null }).currentTask = null;
  await controller.command({ type: "start", instruction: "baru", tabId: 7 });
  controller.onServer({ type: "end", task: "t1", status: "stopped", reason: "stop", steps: 1, report: "" });
  expect(last()).toMatchObject({ phase: "running", ended: null, instruction: "baru" });

  // Penolakan sebelum tugas dibuat (task null) tetap sampai.
  controller.onServer({ type: "end", task: null, status: "refused", reason: "busy", steps: 0, report: "" });
  expect(last()).toMatchObject({ phase: "idle", ended: { reason: "busy" } });
});

test("review: the end of a stopped task still shows when no new task started", async () => {
  const { controller, deps, last } = setup();
  await controller.init();
  await controller.command({ type: "start", instruction: "lama", tabId: 7 });
  (deps.runner as { currentTask: string | null }).currentTask = "t1";
  await controller.command({ type: "stop" });
  controller.onServer({ type: "end", task: "t1", status: "stopped", reason: "stop", steps: 1, report: "" });
  expect(last()).toMatchObject({ phase: "idle", ended: { status: "stopped" } });
});
