// Penjalan aksi di service worker. Setiap pesan action dari server diperiksa
// di sini sebelum menyentuh tab: tiket, host tab, daftar blokir, izin situs,
// dengan urutan tetap. Aksi yang ditolak dijawab {ok: false} dan tidak
// pernah dijalankan.
import { httpsHost, isBlockedHost, normalizeHost } from "./hosts";
import type { Observation } from "./shared/protocol";
import { type TicketReason, verifyTicket } from "./tickets";

export type RefuseReason = TicketReason | "host_changed" | "blocked_host" | "no_permission";

export interface CheckContext {
  keys: unknown;
  task: string;
  device: string;
  lastSeq: number;
  now: number;
  /** Host tab tugas: null kalau tidak ada tab, undefined kalau alamatnya tidak terlihat (tanpa izin). */
  tabHost: string | null | undefined;
  hasPermission: (host: string) => Promise<boolean>;
}

const PASSED_TICKET = new Set<RefuseReason | null>([null, "host_changed", "blocked_host", "no_permission"]);

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Alasan pertama aksi ini ditolak, atau null kalau boleh dijalankan. */
export async function checkAction(signed: unknown, context: CheckContext): Promise<RefuseReason | null> {
  const reason = await verifyTicket(signed, context.keys, context);
  if (reason !== null) return reason;

  const ticket = (signed as { ticket: Record<string, unknown> }).ticket;
  const host = normalizeHost(ticket.host);
  if (host === null) return "host_changed";

  if (ticket.tool === "tab_open") {
    const args = isObject(ticket.args) ? ticket.args : {};
    if (httpsHost(args.url) !== host) return "host_changed";
  } else if (context.tabHost === undefined) {
    // Alamat tab tidak terlihat karena ekstensi tidak punya izin di situs
    // tab itu. Kalau izin untuk host tiket ada, berarti tab sudah pindah.
    if (!isBlockedHost(host) && (await context.hasPermission(host))) return "host_changed";
  } else if (normalizeHost(context.tabHost) !== host) {
    return "host_changed";
  }

  if (isBlockedHost(host)) return "blocked_host";
  if (!(await context.hasPermission(host))) return "no_permission";
  return null;
}

const REFUSE_TEXT: Record<string, string> = {
  host_changed: "Tab tugas sudah pindah ke situs lain, jadi aksi ini tidak dijalankan.",
  blocked_host: "Situs ini selalu diblokir untuk agent.",
  no_permission: "Ciel belum diberi izin untuk situs ini. Izin bisa diberikan dari panel Ciel.",
  no_tab: "Tab tugas sudah ditutup.",
  no_script: "Halaman sudah berubah sejak dibaca. Baca ulang dulu.",
  unknown_tool: "Aksi ini tidak dikenal ekstensi.",
  failed: "Aksi gagal dijalankan di tab.",
};

function refusal(reason: string): Observation {
  const text = REFUSE_TEXT[reason] ?? `Tiket aksi tidak sah (${reason}), jadi aksi ini tidak dijalankan.`;
  return { ok: false, source: "tool", text, host: null, controls: {} };
}

interface Reading {
  observation: Observation;
  generation: number;
}

interface TabInfo {
  id?: number;
  windowId?: number;
  url?: string;
}

export interface RunnerDeps {
  keys: () => Promise<unknown>;
  device: () => Promise<string | null>;
  /** Detik Unix, sama dengan exp di tiket. */
  now: () => number;
  tabs: {
    get: (tabId: number) => Promise<TabInfo>;
    create: (details: { url: string; windowId?: number; active: boolean }) => Promise<TabInfo>;
    remove: (tabId: number) => Promise<void>;
  };
  scripting: {
    executeScript: (details: {
      target: { tabId: number };
      files?: string[];
      func?: (...args: never[]) => unknown;
      args?: unknown[];
    }) => Promise<{ result?: unknown }[]>;
  };
  hasPermission: (host: string) => Promise<boolean>;
  waitForLoad: (tabId: number) => Promise<void>;
  result: (task: string, seq: number, observation: Observation) => boolean;
  needPermission: (host: string) => void;
}

// Fungsi ini disalin Chrome ke tab, jadi tidak boleh memakai apa pun dari luar.
function callInPage(tool: string, args: unknown, generation: number): unknown {
  const agent = (globalThis as { cielAgent?: { act: (...values: unknown[]) => unknown; observe: () => unknown } }).cielAgent;
  if (!agent) return null;
  return tool === "tab_read" ? agent.observe() : agent.act(tool, args, generation);
}

const PAGE_TOOLS = new Set(["tab_read", "tab_click", "form_submit", "tab_type", "tab_select", "tab_scroll"]);

export class Runner {
  private tabId: number | null = null;
  private windowId: number | undefined;
  private task: string | null = null;
  private lastSeq = 0;
  private generation = 0;
  private cachedKeys: unknown = null;

  constructor(private deps: RunnerDeps) {}

  get taskTab(): number | null {
    return this.tabId;
  }

  /** Tugas baru dimulai di tab ini (tab aktif saat pengguna menekan Mulai). */
  begin(tabId: number): void {
    this.tabId = tabId;
    this.windowId = undefined;
    this.task = null;
    this.lastSeq = 0;
    this.generation = 0;
  }

  end(): void {
    this.task = null;
    this.lastSeq = 0;
  }

  private async keys(fresh: boolean): Promise<unknown> {
    if (fresh || this.cachedKeys === null) this.cachedKeys = await this.deps.keys();
    return this.cachedKeys;
  }

  private async tabHost(): Promise<string | null | undefined> {
    if (this.tabId === null) return null;

    try {
      const tab = await this.deps.tabs.get(this.tabId);
      this.windowId = tab.windowId;
      return tab.url === undefined ? undefined : httpsHost(tab.url);
    } catch {
      return null;
    }
  }

  async onAction(signed: unknown): Promise<void> {
    const ticket = isObject(signed) && isObject(signed.ticket) ? signed.ticket : null;
    const replyTo = ticket && typeof ticket.task === "string" && typeof ticket.seq === "number" && Number.isSafeInteger(ticket.seq)
      ? { task: ticket.task, seq: ticket.seq }
      : null;

    const device = await this.deps.device();
    const context = async (fresh: boolean): Promise<CheckContext> => ({
      keys: await this.keys(fresh),
      // Server tidak mengirim nomor tugas sebelum aksi pertama, jadi tiket
      // pertama yang sah sesudah begin() menentukan tugasnya.
      task: this.task ?? (typeof ticket?.task === "string" ? ticket.task : ""),
      device: device ?? "",
      lastSeq: this.lastSeq,
      now: this.deps.now(),
      tabHost: await this.tabHost(),
      hasPermission: this.deps.hasPermission,
    });

    let reason = device === null ? "wrong_device" : await checkAction(signed, await context(false));
    // Kunci baru setelah rotasi: ambil daftar kunci sekali lagi.
    if (reason === "unknown_key") reason = await checkAction(signed, await context(true));

    if (PASSED_TICKET.has(reason as RefuseReason | null) && ticket) {
      this.task = ticket.task as string;
      this.lastSeq = ticket.seq as number;
    }

    if (reason === "no_permission") this.deps.needPermission(normalizeHost(ticket?.host) ?? "");

    const observation = reason === null ? await this.run(ticket!.tool as string, ticket!.args) : refusal(reason);
    if (replyTo) this.deps.result(replyTo.task, replyTo.seq, observation);
  }

  private async call(tool: string, args: unknown): Promise<Reading | null> {
    const [frame] = await this.deps.scripting.executeScript({
      target: { tabId: this.tabId! },
      func: callInPage as (...values: never[]) => unknown,
      args: [tool, args, this.generation],
    });
    const reading = frame?.result as Reading | null | undefined;
    if (!reading || !isObject(reading.observation)) return null;
    this.generation = reading.generation;
    return reading;
  }

  private async inject(): Promise<void> {
    await this.deps.scripting.executeScript({ target: { tabId: this.tabId! }, files: ["content.js"] });
  }

  private async readFresh(): Promise<Observation> {
    await this.deps.waitForLoad(this.tabId!);
    await this.inject();
    return (await this.call("tab_read", {}))?.observation ?? refusal("failed");
  }

  private async run(tool: string, args: unknown): Promise<Observation> {
    try {
      if (tool === "tab_open") {
        const url = (args as { url: string }).url;
        const tab = await this.deps.tabs.create({ url, windowId: this.windowId, active: true });
        this.tabId = tab.id ?? null;
        this.generation = 0;
        return this.tabId === null ? refusal("no_tab") : await this.readFresh();
      }

      if (tool === "tab_close") {
        if (this.tabId !== null) await this.deps.tabs.remove(this.tabId);
        this.tabId = null;
        return { ok: true, source: "tool", text: "Tab ditutup.", host: null, controls: {} };
      }

      if (!PAGE_TOOLS.has(tool)) return refusal("unknown_tool");
      if (this.tabId === null) return refusal("no_tab");

      if (tool === "tab_read") {
        const reading = await this.call(tool, args);
        if (reading) return reading.observation;
        await this.inject();
        return (await this.call(tool, args))?.observation ?? refusal("failed");
      }

      // Aksi dengan nomor rujukan hanya berlaku di halaman yang dibaca terakhir.
      // Tanpa content script, halamannya sudah baru: jangan diulang di sana.
      let reading: Reading | null;

      try {
        reading = await this.call(tool, args);
      } catch {
        // Aksinya membuat tab berpindah halaman di tengah jalan.
        return await this.readFresh();
      }

      return reading?.observation ?? refusal("no_script");
    } catch {
      return refusal("failed");
    }
  }
}
