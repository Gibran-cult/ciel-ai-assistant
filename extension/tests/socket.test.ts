// @vitest-environment node
import { vi } from "vitest";
import { parseServerMessage, Socket, type SocketState } from "../src/socket";

class FakeWs {
  static made: FakeWs[] = [];
  sent: unknown[] = [];
  readyState = 0;
  closed: number | null = null;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(public url: string) {
    FakeWs.made.push(this);
  }

  send(text: string) {
    this.sent.push(JSON.parse(text));
  }

  close(code = 1000) {
    this.closed = code;
    this.readyState = 3;
  }

  open() {
    this.readyState = 1;
    this.onopen?.();
  }

  receive(message: unknown) {
    this.onmessage?.({ data: JSON.stringify(message) });
  }

  drop(code: number) {
    this.readyState = 3;
    this.onclose?.({ code });
  }
}

function setup(tokens: (string | null)[] = ["cat1.a.ONE", "cat1.a.TWO", "cat1.a.THREE"]) {
  FakeWs.made = [];
  const timers: { delay: number; run: () => void }[] = [];
  const states: SocketState[] = [];
  const messages: unknown[] = [];
  const token = vi.fn(async () => tokens.shift() ?? null);
  const socket = new Socket({
    base: async () => "https://agent.ciel-ai.web.id",
    token,
    version: "0.1.0",
    onMessage: (message) => messages.push(message),
    onState: (state) => states.push(state),
    WebSocket: FakeWs as unknown as typeof WebSocket,
    random: () => 0.5,
    later: (run, delay) => timers.push({ run, delay }),
  });
  return { socket, timers, states, messages, token };
}

const flush = () => new Promise((done) => setTimeout(done, 0));

test("connects to the ws URL and says hello with a token, never in the URL", async () => {
  const { socket } = setup();
  socket.start();
  await flush();
  const ws = FakeWs.made[0]!;
  expect(ws.url).toBe("wss://agent.ciel-ai.web.id/v1/ws");
  ws.open();
  expect(ws.sent[0]).toEqual({ type: "hello", token: "cat1.a.ONE", client: "extension", version: "0.1.0" });
});

test("server messages must have exactly the protocol keys", () => {
  expect(parseServerMessage(JSON.stringify({ type: "ready", device: "d1" }))).toEqual({ type: "ready", device: "d1" });
  expect(parseServerMessage(JSON.stringify({ type: "ready", device: "d1", extra: 1 }))).toBeNull();
  expect(parseServerMessage(JSON.stringify({ type: "confirm", id: 3, prompt: {} }))).not.toBeNull();
  expect(parseServerMessage(JSON.stringify({ type: "confirm", id: "3", prompt: {} }))).toBeNull();
  expect(parseServerMessage(JSON.stringify({ type: "action", ticket: {}, kid: "k", sig: "s" }))).not.toBeNull();
  expect(parseServerMessage(JSON.stringify({ type: "nuke" }))).toBeNull();
  expect(parseServerMessage("not json")).toBeNull();
  expect(parseServerMessage(JSON.stringify([1]))).toBeNull();
});

test("a message with an extra key closes the connection", async () => {
  const { socket, messages } = setup();
  socket.start();
  await flush();
  const ws = FakeWs.made[0]!;
  ws.open();
  ws.receive({ type: "ready", device: "d1", injected: "x" });
  expect(ws.closed).toBe(4400);
  expect(messages).toEqual([]);
});

test("reconnects with growing delays and a fresh token each time", async () => {
  const { socket, timers, token } = setup();
  socket.start();
  await flush();
  FakeWs.made[0]!.open();
  FakeWs.made[0]!.drop(1006);
  expect(timers.map((t) => t.delay)).toEqual([1000]);

  timers[0]!.run();
  await flush();
  FakeWs.made[1]!.open();
  expect(FakeWs.made[1]!.sent[0]).toMatchObject({ type: "hello", token: "cat1.a.TWO" });
  FakeWs.made[1]!.drop(1006);
  expect(timers.map((t) => t.delay)).toEqual([1000, 2000]);
  expect(token).toHaveBeenCalledTimes(2);
});

test("delays go 1, 2, 4, 8, 30 seconds with jitter, and reset after ready", async () => {
  const { socket, timers } = setup(Array(10).fill("cat1.a.X"));
  socket.start();
  await flush();

  for (let i = 0; i < 6; i++) {
    FakeWs.made.at(-1)!.drop(1006);
    timers.at(-1)!.run();
    await flush();
  }

  expect(timers.map((t) => t.delay)).toEqual([1000, 2000, 4000, 8000, 30000, 30000]);
  const ws = FakeWs.made.at(-1)!;
  ws.open();
  ws.receive({ type: "ready", device: "d1" });
  ws.drop(1006);
  expect(timers.at(-1)!.delay).toBe(1000);
});

test("jitter stays within 20 percent", async () => {
  for (const random of [0, 1]) {
    FakeWs.made = [];
    const timers: number[] = [];
    const socket = new Socket({
      base: async () => "https://agent.ciel-ai.web.id", token: async () => "cat1.a.X", version: "0.1.0",
      onMessage: () => undefined, onState: () => undefined, WebSocket: FakeWs as unknown as typeof WebSocket,
      random: () => random, later: (_run, delay) => timers.push(delay),
    });
    socket.start();
    await flush();
    FakeWs.made[0]!.drop(1006);
    expect(timers[0]).toBe(random === 0 ? 800 : 1200);
  }
});

test("4401 without a usable token signs out and stops reconnecting", async () => {
  const { socket, timers, states } = setup(["cat1.a.ONE", null]);
  socket.start();
  await flush();
  FakeWs.made[0]!.drop(4401);
  timers.at(-1)?.run();
  await flush();
  expect(states.at(-1)).toBe("signed_out");
  expect(FakeWs.made).toHaveLength(1);
});

test("4426 asks for an update and stops", async () => {
  const { socket, timers, states } = setup();
  socket.start();
  await flush();
  FakeWs.made[0]!.drop(4426);
  expect(states.at(-1)).toBe("update_required");
  expect(timers).toEqual([]);
});

test("result carries task and seq, answers carry the id", async () => {
  const { socket } = setup();
  socket.start();
  await flush();
  const ws = FakeWs.made[0]!;
  ws.open();
  ws.receive({ type: "ready", device: "d1" });
  const observation = { ok: true, source: "page" as const, text: "x", host: "toko.test", controls: {} };
  expect(socket.result("t9", 4, observation)).toBe(true);
  expect(socket.answer(7, true)).toBe(true);
  expect(ws.sent.slice(1)).toEqual([
    { type: "result", task: "t9", seq: 4, observation },
    { type: "answer", id: 7, value: true },
  ]);
});

test("ws:// is used only for a local development server", async () => {
  FakeWs.made = [];
  const socket = new Socket({
    base: async () => "http://localhost:8600", token: async () => "cat1.a.X", version: "0.1.0",
    onMessage: () => undefined, onState: () => undefined, WebSocket: FakeWs as unknown as typeof WebSocket,
    random: () => 0.5, later: () => undefined,
  });
  socket.start();
  await flush();
  expect(FakeWs.made[0]!.url).toBe("ws://localhost:8600/v1/ws");
});

test("stop while offline is sent as soon as the connection is ready again", async () => {
  const { socket, timers } = setup();
  socket.start();
  await flush();
  FakeWs.made[0]!.drop(1006);
  expect(socket.sendStop()).toBe(false);

  timers[0]!.run();
  await flush();
  const ws = FakeWs.made[1]!;
  ws.open();
  ws.receive({ type: "ready", device: "d1" });
  expect(ws.sent).toEqual([expect.objectContaining({ type: "hello" }), { type: "stop" }]);
});

test("task 3.27: start carries the page only when there is one", async () => {
  const { socket } = setup();
  socket.start();
  await flush();
  const ws = FakeWs.made[0]!;
  ws.open();
  ws.receive({ type: "ready", device: "d1" });
  const page = { ok: true, source: "page" as const, text: "x", host: "toko.test", controls: {} };
  socket.startTask("Isi nama", page);
  socket.startTask("Isi nama", null);
  expect(ws.sent.slice(1)).toEqual([
    { type: "start", instruction: "Isi nama", page },
    { type: "start", instruction: "Isi nama" },
  ]);
});
