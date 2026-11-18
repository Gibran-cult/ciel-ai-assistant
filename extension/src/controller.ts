// Pengendali di service worker: menggabungkan login, koneksi, tugas, dan
// dialog menjadi satu PanelState yang dikirim ke side panel. Panel hanya
// menampilkan keadaan ini dan mengirim perintah; semua keputusan ada di sini.
import type { LoginResult } from "./auth";
import type { Observation } from "./shared/protocol";
import logText from "./shared/vectors/log_text.json";
import type { ServerMessage, SocketState } from "./socket";
import { type Phase, Session } from "./stop";

export type Dialog =
  | { kind: "plan"; id: number; steps: string[]; scope: PlanScope }
  | { kind: "confirm"; id: number; prompt: Record<string, unknown> }
  | { kind: "handover"; id: number; prompt: Record<string, unknown> }
  | { kind: "ask"; id: number; question: string };

export interface PlanScope {
  hosts: string[];
  kinds: string[];
  spend_cap: number | null;
  /** Situs tab awal yang masuk lingkup (keputusan D20), atau null. */
  start_host?: string | null;
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function planScope(raw: unknown): PlanScope {
  const scope = typeof raw === "object" && raw !== null ? (raw as Record<string, unknown>) : {};
  return {
    hosts: strings(scope.hosts), kinds: strings(scope.kinds), spend_cap: typeof scope.spend_cap === "number" ? scope.spend_cap : null,
    start_host: typeof scope.start_host === "string" ? scope.start_host : null,
  };
}

export interface PanelLogLine {
  time: string;
  action: string;
  target: string;
  result: string;
}

export interface PanelState {
  auth: "unknown" | "signed_out" | "consent_required" | "signed_in";
  loginFailed: boolean;
  connection: SocketState;
  phase: Phase;
  dialog: Dialog | null;
  log: PanelLogLine[];
  needPermission: string | null;
  ended: { status: string; reason: string | null; steps: number; report: string } | null;
  instruction: string;
}

export type PanelCommand =
  | { type: "login" }
  | { type: "logout" }
  | { type: "start"; instruction: string; tabId: number }
  | { type: "answer"; id: number; value: unknown }
  | { type: "stop" }
  | { type: "resume" }
  | { type: "handover_done"; done: boolean }
  | { type: "permission_granted" }
  | { type: "dismiss" }
  | { type: "keepalive" };

export interface ActionLog {
  tool: string;
  host: string | null;
  outcome: "ok" | "failed" | "refused";
}

export type BannerMode = "active" | "waiting" | "handover" | "paused" | "stopped";

export interface ControllerDeps {
  login(): Promise<LoginResult>;
  logout(): Promise<void>;
  hasToken(): Promise<boolean>;
  socket: {
    start(): void;
    close(): void;
    startTask(instruction: string, page: Observation | null): boolean;
    answer(id: number, value: unknown): boolean;
    sendStop(): boolean;
    readonly isReady: boolean;
  };
  runner: {
    begin(tabId: number): void;
    end(): void;
    onAction(signed: unknown): Promise<void>;
    refuse(signed: unknown, reason: "stopped" | "handover"): void;
    readStart(): Promise<Observation | null>;
    readonly taskTab: number | null;
    readonly currentTask: string | null;
  };
  banner(tabId: number, mode: BannerMode | null): void;
  badge(phase: Phase, waiting: boolean): void;
  now(): Date;
  broadcast(state: PanelState): void;
}

const MAX_LOG = 200;
const ACTIONS = logText.actions as Record<string, string>;
const OUTCOME_TEXT = { ok: "Selesai", failed: "Gagal", refused: "Diblokir" } as const;

function clock(date: Date): string {
  return `${String(date.getHours()).padStart(2, "0")}.${String(date.getMinutes()).padStart(2, "0")}`;
}

export class Controller {
  private state: PanelState = {
    auth: "unknown", loginFailed: false, connection: "closed", phase: "idle", dialog: null, log: [],
    needPermission: null, ended: null, instruction: "",
  };

  readonly session: Session;
  // Tab tempat banner sedang terpasang, dan apakah banner "berhenti" dibiarkan menghilang sendiri.
  private bannerTab: number | null = null;
  private keepStopped = false;
  // Tugas yang sudah ditinggalkan (Stop atau tugas baru). end-nya yang datang
  // terlambat tidak boleh menutup tugas yang sedang berjalan.
  private leftTasks = new Set<string>();

  constructor(private deps: ControllerDeps) {
    this.session = new Session({
      socket: deps.socket,
      runner: deps.runner,
      refuse: (signed, reason) => deps.runner.refuse(signed, reason),
      show: ({ phase }) => this.update({ phase }),
    });
  }

  get view(): PanelState {
    return this.state;
  }

  private update(change: Partial<PanelState>): void {
    this.state = { ...this.state, ...change };
    const waiting = this.state.dialog !== null && this.state.dialog.kind !== "handover";
    this.deps.badge(this.state.phase, waiting && this.state.phase === "running");

    this.applyBanner(waiting);
    this.deps.broadcast(this.state);
  }

  // Banner ada di tab tugas yang sekarang (tab_open memindahkannya ke tab baru).
  private applyBanner(waiting: boolean): void {
    const tab = this.deps.runner.taskTab;
    const mode = this.bannerMode(waiting);

    if (this.bannerTab !== null && this.bannerTab !== tab) {
      this.deps.banner(this.bannerTab, null);
      this.bannerTab = null;
    }

    if (tab === null) return;

    if (mode === null) {
      // Banner "Ciel sudah berhenti" menghilang sendiri setelah beberapa detik.
      if (this.keepStopped || this.bannerTab === null) return;
      this.deps.banner(tab, null);
      this.bannerTab = null;
      return;
    }

    this.deps.banner(tab, mode);
    this.bannerTab = tab;
  }

  private leave(): void {
    const task = this.deps.runner.currentTask;
    if (task) this.leftTasks.add(task);
  }

  /** Halaman baru dimuat di tab tugas: pasang banner lagi. */
  onPage(): void {
    this.bannerTab = null;
    const waiting = this.state.dialog !== null && this.state.dialog.kind !== "handover";
    this.applyBanner(waiting && this.state.phase === "running");
  }

  private bannerMode(waiting: boolean): BannerMode | null {
    switch (this.state.phase) {
      case "running":
        return waiting ? "waiting" : "active";
      case "paused":
        return "paused";
      case "handover":
        return "handover";
      case "stopped":
        return "stopped";
      default:
        return null;
    }
  }

  async init(): Promise<void> {
    if (await this.deps.hasToken()) {
      this.update({ auth: "signed_in" });
      this.deps.socket.start();
    } else {
      this.update({ auth: "signed_out" });
    }
  }

  onSocketState(connection: SocketState): void {
    // Koneksi putus di tengah tugas: layanan mengakhiri tugas itu (client_gone)
    // tanpa bisa memberi tahu panel. Akhiri juga di sini, supaya dialog lama
    // dan aksi yang ditahan tidak tersisa.
    if (connection !== "ready" && this.state.phase !== "idle") {
      const stopped = this.state.phase === "stopped";
      const steps = this.state.log.length;
      this.state = {
        ...this.state, dialog: null, needPermission: null,
        ended: stopped ? { status: "stopped", reason: "stop", steps, report: "" } : { status: "failed", reason: "client_gone", steps, report: "" },
      };
      this.session.onEnd();
    }

    if (connection === "signed_out") {
      this.update({ connection, auth: "signed_out" });
      return;
    }

    this.update({ connection });
  }

  onServer(message: ServerMessage): void {
    switch (message.type) {
      case "plan":
        this.update({ dialog: { kind: "plan", id: message.id, steps: (message.steps as unknown[]).map(String), scope: planScope(message.scope) } });
        return;
      case "confirm":
        this.update({ dialog: { kind: "confirm", id: message.id, prompt: message.prompt } });
        return;
      case "ask":
        this.update({ dialog: { kind: "ask", id: message.id, question: message.question } });
        return;
      case "handover":
        this.state = { ...this.state, dialog: { kind: "handover", id: message.id, prompt: message.prompt } };
        this.session.onHandover(message.id);
        return;
      case "action":
        this.session.onAction({ ticket: message.ticket, kid: message.kid, sig: message.sig });
        return;
      case "end":
        if (message.task !== null && this.leftTasks.has(message.task) && this.state.phase !== "stopped") return;
        this.session.onEnd();
        this.update({ dialog: null, needPermission: null, ended: { status: message.status, reason: message.reason, steps: message.steps, report: message.report } });
        return;
      default:
        return;
    }
  }

  onTakeover(tabId: number): void {
    this.session.takeover(tabId);
  }

  onNeedPermission(host: string): void {
    this.update({ needPermission: host });
  }

  onLog(entry: ActionLog): void {
    const action = ACTIONS[entry.tool] ?? logText.unknown_action.replace("{kind}", entry.tool || "?");
    this.addLog({ action, target: entry.host ?? "", result: OUTCOME_TEXT[entry.outcome] });
  }

  private addLog(line: Omit<PanelLogLine, "time">): void {
    this.update({ log: [...this.state.log, { time: clock(this.deps.now()), ...line }].slice(-MAX_LOG) });
  }

  async command(command: PanelCommand): Promise<void> {
    if (typeof command !== "object" || command === null) return;

    switch (command.type) {
      case "login": {
        const result = await this.deps.login();
        if (result.kind === "ok") {
          this.update({ auth: "signed_in", loginFailed: false });
          this.deps.socket.start();
        } else if (result.kind === "consent_required") {
          this.update({ auth: "consent_required", loginFailed: false });
        } else {
          this.update({ loginFailed: result.kind === "failed" });
        }
        return;
      }

      case "logout":
        this.session.stop();
        this.deps.socket.close();
        await this.deps.logout();
        this.update({ auth: "signed_out", dialog: null, log: [], ended: null });
        return;

      case "start": {
        const instruction = typeof command.instruction === "string" ? command.instruction.trim() : "";
        if (!instruction || instruction.length > 2000 || !Number.isInteger(command.tabId)) return;
        if (this.state.phase !== "idle" && this.state.phase !== "stopped") return;
        if (!this.deps.socket.isReady) {
          this.update({ instruction });
          return;
        }

        this.keepStopped = false;
        this.leave();
        this.deps.runner.begin(command.tabId);
        this.state = { ...this.state, instruction, ended: null, log: [], dialog: null, needPermission: null };
        this.session.begin();
        // Tab yang sedang dibuka ikut dikirim sebagai halaman awal (task 3.27).
        const page = await this.deps.runner.readStart();
        if (this.state.phase !== "running") return;
        this.deps.socket.startTask(instruction, page);
        return;
      }

      case "answer": {
        const dialog = this.state.dialog;
        if (!dialog || dialog.kind === "handover" || dialog.id !== command.id) return;
        this.deps.socket.answer(command.id, command.value);
        if (dialog.kind === "confirm" && command.value !== true) {
          this.state = { ...this.state, dialog: null };
          this.addLog({ action: ACTIONS[String(dialog.prompt.tool)] ?? "Aksi", target: String(dialog.prompt.target ?? ""), result: "Kamu tolak" });
          return;
        }
        this.update({ dialog: null });
        return;
      }

      case "handover_done": {
        if (this.state.dialog?.kind !== "handover") return;
        this.state = { ...this.state, dialog: null };
        this.session.finishHandover(command.done === true);
        return;
      }

      case "stop":
        this.leave();
        this.keepStopped = true;
        this.state = { ...this.state, dialog: null };
        this.session.stop();
        return;

      case "resume":
        this.session.resume();
        return;

      case "permission_granted":
        this.update({ needPermission: null });
        return;

      case "dismiss":
        this.update({ ended: null });
        return;

      // Pesan dari panel menjaga service worker tetap hidup selama dialog menunggu.
      case "keepalive":
        return;

      default:
        return;
    }
  }
}
