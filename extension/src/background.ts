// Service worker Ciel Agent: menyambungkan login, WebSocket, pemeriksa aksi,
// dan panel. Satu-satunya tempat token disegarkan (lihat auth.ts).
import { accessToken, handleAlarm, login, logout, refresh } from "./auth";
import { showBadge } from "./badge";
import { apiBase } from "./config";
import { Controller, type PanelCommand, type PanelState } from "./controller";
import { hasPermission } from "./permissions";
import { Runner } from "./runner";
import { Socket } from "./socket";

// Token pembaruan ada di storage.local, yang bawaannya terbaca content script.
// Content script Ciel berjalan di halaman toko, jadi aksesnya ditutup.
void chrome.storage.local.setAccessLevel({ accessLevel: "TRUSTED_CONTEXTS" }).catch(() => undefined);

const panels = new Set<chrome.runtime.Port>();
const PANEL_URL = chrome.runtime.getURL("panel/index.html");

function broadcast(state: PanelState): void {
  for (const port of panels) port.postMessage({ type: "state", state });
}

// Tunggu tab selesai memuat halaman, paling lama 15 detik.
function waitForLoad(tabId: number): Promise<void> {
  return new Promise((resolve) => {
    let finished = false;
    const done = () => {
      if (finished) return;
      finished = true;
      chrome.tabs.onUpdated.removeListener(listener);
      clearTimeout(timer);
      resolve();
    };
    const listener = (id: number, info: { status?: string }) => {
      if (id === tabId && info.status === "complete") done();
    };
    const timer = setTimeout(done, 15_000);
    chrome.tabs.onUpdated.addListener(listener);
    chrome.tabs.get(tabId).then((tab) => tab.status === "complete" && done(), done);
  });
}

async function ticketKeys(): Promise<unknown> {
  const response = await fetch(`${await apiBase()}/v1/ticket-keys`, { cache: "no-store", credentials: "omit" });
  if (!response.ok) return [];
  // Jawaban layanan: {"keys": [{kid, alg, key}, ...]}.
  const body = await response.json();
  return Array.isArray(body?.keys) ? body.keys : [];
}

// eslint-disable-next-line prefer-const
let controller: Controller;

const socket = new Socket({
  base: () => apiBase(),
  token: () => accessToken(),
  refresh: () => refresh(),
  version: chrome.runtime.getManifest().version,
  onMessage: (message) => controller.onServer(message),
  onState: (state) => controller?.onSocketState(state),
});

const runner = new Runner({
  keys: ticketKeys,
  device: async () => {
    const { device } = await chrome.storage.local.get("device");
    return typeof device === "string" ? device : null;
  },
  now: () => Math.floor(Date.now() / 1000),
  tabs: {
    get: (tabId) => chrome.tabs.get(tabId),
    create: (details) => chrome.tabs.create(details),
    remove: (tabId) => chrome.tabs.remove(tabId),
  },
  scripting: { executeScript: (details) => chrome.scripting.executeScript(details as chrome.scripting.ScriptInjection<unknown[], unknown>) },
  hasPermission,
  waitForLoad,
  result: (task, seq, observation) => socket.result(task, seq, observation),
  needPermission: (host) => controller.onNeedPermission(host),
  log: (entry) => controller.onLog(entry),
  onPage: () => controller.onPage(),
});

controller = new Controller({
  login: () => login(),
  logout: () => logout(),
  hasToken: async () => (await chrome.storage.local.get("refreshToken")).refreshToken !== undefined,
  socket,
  runner,
  banner: (tabId, mode) => {
    // Banner hanya bisa dipasang di tab yang sudah diizinkan; kalau belum, diam saja.
    chrome.scripting.executeScript({
      target: { tabId },
      func: (value: string | null) => (globalThis as { cielAgent?: { banner: (mode: string | null) => void } }).cielAgent?.banner(value),
      args: [mode],
    }).catch(() => undefined);
  },
  badge: (phase, waiting) => void showBadge(phase, waiting).catch(() => undefined),
  now: () => new Date(),
  broadcast,
});

chrome.runtime.onConnect.addListener((port) => {
  // Hanya halaman panel milik ekstensi ini, bukan content script.
  if (port.name !== "panel" || port.sender?.id !== chrome.runtime.id || port.sender.url !== PANEL_URL) {
    port.disconnect();
    return;
  }

  panels.add(port);
  port.postMessage({ type: "state", state: controller.view });
  port.onMessage.addListener((command: PanelCommand) => void controller.command(command));
  port.onDisconnect.addListener(() => panels.delete(port));
});

chrome.runtime.onMessage.addListener((message: { type?: string }, sender) => {
  if (sender.id !== chrome.runtime.id || sender.tab?.id === undefined) return;
  // Pesan dari content script hanya dihitung kalau datang dari tab tugas.
  if (sender.tab.id !== runner.taskTab) return;
  if (message?.type === "takeover") controller.onTakeover(sender.tab.id);
  if (message?.type === "stop") void controller.command({ type: "stop" });
});

chrome.commands.onCommand.addListener((command) => {
  if (command === "stop-agent") void controller.command({ type: "stop" });
});

chrome.alarms.onAlarm.addListener(handleAlarm);
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => undefined);
void controller.init();
