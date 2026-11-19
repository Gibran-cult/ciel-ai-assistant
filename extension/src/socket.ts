// Klien WebSocket untuk docs/agent-protocol.md bagian 2. Token dikirim di
// pesan hello, tidak pernah di URL. Setiap pesan server harus punya kunci
// persis sesuai daftar; pesan lain menutup koneksi.
import type { Observation } from "./shared/protocol";

export type ServerMessage =
  | { type: "ready"; device: string }
  | { type: "plan"; task: string; id: number; steps: unknown; scope: unknown }
  | { type: "confirm"; id: number; prompt: Record<string, unknown> }
  | { type: "handover"; id: number; prompt: Record<string, unknown> }
  | { type: "ask"; id: number; question: string }
  | { type: "action"; ticket: unknown; kid: unknown; sig: unknown }
  | { type: "end"; task: string | null; status: string; reason: string | null; steps: number; report: string };

export type SocketState = "connecting" | "ready" | "closed" | "signed_out" | "update_required" | "origin_refused";

// Kunci persis setiap pesan dari server (agent_api/ws.py).
const SERVER_KEYS: Record<string, string[]> = {
  ready: ["device", "type"],
  plan: ["id", "scope", "steps", "task", "type"],
  confirm: ["id", "prompt", "type"],
  handover: ["id", "prompt", "type"],
  ask: ["id", "question", "type"],
  action: ["kid", "sig", "ticket", "type"],
  end: ["reason", "report", "status", "steps", "task", "type"],
};

const DELAYS = [1000, 2000, 4000, 8000, 30000];
const JITTER = 0.2;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function shaped(message: Record<string, unknown>): boolean {
  const isId = (value: unknown) => typeof value === "number" && Number.isSafeInteger(value);

  switch (message.type) {
    case "ready":
      return typeof message.device === "string";
    case "plan":
      return typeof message.task === "string" && isId(message.id) && Array.isArray(message.steps);
    case "confirm":
    case "handover":
      return isId(message.id) && isObject(message.prompt);
    case "ask":
      return isId(message.id) && typeof message.question === "string";
    case "action":
      return true; // Tiketnya diperiksa runner.ts.
    case "end":
      return (message.task === null || typeof message.task === "string") && typeof message.status === "string" && (message.reason === null || typeof message.reason === "string")
        && typeof message.steps === "number" && typeof message.report === "string";
    default:
      return false;
  }
}

/** Pesan server yang bentuknya sah, atau null. */
export function parseServerMessage(raw: unknown): ServerMessage | null {
  if (typeof raw !== "string") return null;
  let message: unknown;

  try {
    message = JSON.parse(raw);
  } catch {
    return null;
  }

  if (!isObject(message) || typeof message.type !== "string") return null;
  const keys = SERVER_KEYS[message.type];
  if (!keys || Object.keys(message).sort().join() !== keys.join()) return null;
  return shaped(message) ? (message as unknown as ServerMessage) : null;
}

export interface SocketOptions {
  base: () => Promise<string>;
  token: () => Promise<string | null>;
  /** Paksa token akses baru (setelah layanan menolak token dengan 4401). */
  refresh?: () => Promise<string | null>;
  version: string;
  onMessage: (message: ServerMessage) => void;
  onState: (state: SocketState) => void;
  WebSocket?: typeof WebSocket;
  random?: () => number;
  later?: (run: () => void, delay: number) => void;
}

function wsUrl(base: string): string {
  const url = new URL("/v1/ws", base);
  url.protocol = url.protocol === "http:" ? "ws:" : "wss:";
  return url.toString();
}

export class Socket {
  private ws: WebSocket | null = null;
  private attempt = 0;
  private running = false;
  private ready = false;
  private stopPending = false;
  // 4401 sejak terakhir "ready". Yang pertama memaksa token baru; perangkat
  // yang benar-benar dicabut berakhir di refresh() -> null (signed_out).
  private unauthorized = 0;
  private forceFresh = false;

  constructor(private options: SocketOptions) {}

  start(): void {
    if (this.running) return;
    this.running = true;
    this.unauthorized = 0;
    void this.connect();
  }

  /** Putus dan berhenti menyambung ulang. */
  close(): void {
    this.running = false;
    this.ready = false;
    this.ws?.close(1000);
    this.ws = null;
    this.options.onState("closed");
  }

  get isReady(): boolean {
    return this.ready;
  }

  private async connect(): Promise<void> {
    if (!this.running) return;
    this.options.onState("connecting");
    // Token baru di setiap sambungan: token akses berlaku 15 menit.
    const fresh = this.forceFresh && this.options.refresh;
    this.forceFresh = false;
    const token = fresh ? await this.options.refresh!() : await this.options.token();

    if (token === null) {
      this.running = false;
      this.options.onState("signed_out");
      return;
    }

    const Impl = this.options.WebSocket ?? WebSocket;
    const ws = new Impl(wsUrl(await this.options.base()));
    this.ws = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "hello", token, client: "extension", version: this.options.version }));
    };

    ws.onmessage = (event: MessageEvent) => {
      const message = parseServerMessage(event.data);

      if (message === null) {
        // Pesan di luar protokol: jangan percaya koneksi ini lagi.
        ws.close(4400);
        this.dropped(ws, 4400);
        return;
      }

      if (message.type === "ready") {
        this.ready = true;
        this.attempt = 0;
        this.unauthorized = 0;
        this.options.onState("ready");
        if (this.stopPending) this.sendStop();
      }

      this.options.onMessage(message);
    };

    ws.onclose = (event: CloseEvent) => this.dropped(ws, event.code);
  }

  private dropped(ws: WebSocket, code: number): void {
    if (this.ws !== ws) return;
    this.ws = null;
    this.ready = false;
    if (!this.running) return;

    if (code === 4426 || code === 4403) {
      this.running = false;
      this.options.onState(code === 4426 ? "update_required" : "origin_refused");
      return;
    }

    // Token ditolak: coba sekali dengan token baru. Perangkat yang dicabut
    // membuat penyegaran gagal (401), jadi connect() berakhir signed_out.
    // Kalau token baru pun ditolak lagi, layanan sedang bermasalah: tunggu
    // dan coba lagi seperti putus biasa, jangan keluarkan pengguna.
    if (code === 4401 && this.unauthorized === 0) {
      this.unauthorized = 1;
      this.forceFresh = true;
      void this.connect();
      return;
    }

    this.options.onState("closed");
    const base = DELAYS[Math.min(this.attempt, DELAYS.length - 1)]!;
    this.attempt += 1;
    const random = this.options.random ?? Math.random;
    const delay = Math.round(base * (1 - JITTER + 2 * JITTER * random()));
    const later = this.options.later ?? ((run, wait) => void setTimeout(run, wait));
    later(() => void this.connect(), delay);
  }

  private send(message: object): boolean {
    if (!this.ready || !this.ws) return false;

    try {
      this.ws.send(JSON.stringify(message));
      return true;
    } catch {
      return false;
    }
  }

  /** Mulai tugas. `page` adalah bacaan tab yang sedang dibuka, kalau ada (task 3.27). */
  startTask(instruction: string, page: Observation | null = null): boolean {
    this.stopPending = false;
    return this.send(page ? { type: "start", instruction, page } : { type: "start", instruction });
  }

  answer(id: number, value: unknown): boolean {
    return this.send({ type: "answer", id, value });
  }

  result(task: string, seq: number, observation: Observation): boolean {
    return this.send({ type: "result", task, seq, observation });
  }

  /** Stop selalu sampai: kalau sedang putus, dikirim begitu tersambung lagi. */
  sendStop(): boolean {
    this.stopPending = !this.send({ type: "stop" });
    return !this.stopPending;
  }
}
