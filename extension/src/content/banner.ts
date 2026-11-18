// Banner di tab tugas. Hidup di Shadow DOM tertutup, jadi skrip halaman
// tidak bisa membaca, mengubah, atau menekan tombolnya. Kalau dihapus atau
// diberi gaya oleh halaman, banner dipasang ulang. Halaman didorong ke bawah
// supaya isinya tidak tertutup.
//
// Huruf memakai huruf sistem: memuat Geist dari paket ekstensi ke halaman
// butuh web_accessible_resources, yang sengaja tidak ada di manifest.
import tokens from "../../../design/tokens.json";

export type BannerMode = "active" | "waiting" | "handover" | "paused" | "stopped";

export const BANNER_TEXT: Record<BannerMode, string> = {
  active: "Tab ini sedang dikontrol Ciel",
  waiting: "Ciel menunggu persetujuanmu di panel",
  handover: "Giliranmu. Ciel tidak melihat tab ini.",
  paused: "Dijeda karena kamu memakai tab ini. Lanjutkan atau stop di panel Ciel.",
  stopped: "Ciel sudah berhenti. Tab ini kembali sepenuhnya milikmu.",
};

const EDGE: Record<BannerMode, string> = {
  active: "agent-active",
  waiting: "agent-wait",
  handover: "agent-wait",
  paused: "muted",
  stopped: "muted",
};

const TAG = "ciel-agent-banner";
const HEIGHT = 52;
const STOPPED_MS = 5000;

type Theme = Record<string, string>;

function color(theme: Theme, name: string): string {
  const raw = theme[name] ?? "";
  const alias = /^\{([a-z-]+)\}$/.exec(raw);
  return alias ? color(theme, alias[1]!) : raw;
}

function palette(theme: Theme, mode: BannerMode): string {
  return `--bg:${color(theme, "surface")};--ink:${color(theme, "text")};--edge:${color(theme, EDGE[mode])};`
    + `--stop-bg:${color(theme, "stop-bg")};--stop-ink:${color(theme, "stop-ink")};--focus:${color(theme, "accent")};`;
}

function css(mode: BannerMode): string {
  return `
:host { all: initial !important; position: fixed !important; inset: 0 0 auto 0 !important; display: block !important;
  height: ${HEIGHT}px !important; z-index: 2147483647 !important; visibility: visible !important; opacity: 1 !important; }
.bar { ${palette(tokens.light, mode)} box-sizing: border-box; height: ${HEIGHT}px; display: flex; align-items: center; gap: 12px;
  padding: 0 4px 0 16px; background: var(--bg); color: var(--ink); border-bottom: 3px solid var(--edge);
  font: 400 14px/1.4 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
@media (prefers-color-scheme: dark) { .bar { ${palette(tokens.dark, mode)} } }
.text { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.name { font-weight: 600; }
button { all: unset; box-sizing: border-box; display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  min-width: 88px; min-height: 44px; padding: 0 16px; border-radius: 8px; cursor: pointer;
  background: var(--stop-bg); color: var(--stop-ink); font: 600 14px/1.2 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
button:hover { box-shadow: inset 0 0 0 999px rgb(0 0 0 / 0.12); }
button:active { box-shadow: inset 0 0 0 999px rgb(0 0 0 / 0.22); }
button:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.square { width: 10px; height: 10px; background: currentColor; border-radius: 2px; }
`;
}

export function onStopClick(event: Event, send: (message: { type: "stop" }) => unknown): void {
  // Klik buatan skrip tidak dihitung. Halaman juga tidak bisa menjangkau
  // tombol ini, tapi pemeriksaan ini menjaga kalau suatu saat bisa.
  if (event.isTrusted) send({ type: "stop" });
}

function sendToWorker(message: { type: "stop" }): void {
  void chrome.runtime.sendMessage(message).catch(() => undefined);
}

interface Mounted {
  host: HTMLElement;
  root: ShadowRoot;
  observer: MutationObserver;
  marginValue: string;
  marginPriority: string;
  timer: ReturnType<typeof setTimeout> | null;
}

const mounted = new WeakMap<Document, Mounted>();

function render(state: Mounted, mode: BannerMode): void {
  const doc = state.host.ownerDocument;
  const style = doc.createElement("style");
  style.textContent = css(mode);

  const bar = doc.createElement("div");
  bar.className = "bar";
  bar.setAttribute("role", "status");

  const text = doc.createElement("span");
  text.className = "text";
  text.textContent = BANNER_TEXT[mode];
  bar.append(text);

  if (mode !== "stopped") {
    const stop = doc.createElement("button");
    stop.type = "button";
    stop.title = "Stop (Alt+Shift+S)";
    const square = doc.createElement("span");
    square.className = "square";
    square.setAttribute("aria-hidden", "true");
    stop.append(square, "Stop");
    stop.addEventListener("click", (event) => onStopClick(event, sendToWorker));
    bar.append(stop);
  }

  state.root.replaceChildren(style, bar);
}

export function mountBanner(doc: Document, mode: BannerMode): void {
  let state = mounted.get(doc);

  if (!state) {
    const host = doc.createElement(TAG);
    const root = host.attachShadow({ mode: "closed" });
    const html = doc.documentElement;
    const View = doc.defaultView?.MutationObserver ?? MutationObserver;
    const observer = new View(() => {
      // Halaman tidak boleh menyembunyikan atau menghapus banner.
      for (const name of host.getAttributeNames()) host.removeAttribute(name);
      if (!host.isConnected) doc.documentElement.append(host);
    });

    state = {
      host, root, observer, timer: null,
      marginValue: html.style.getPropertyValue("margin-top"),
      marginPriority: html.style.getPropertyPriority("margin-top"),
    };
    mounted.set(doc, state);
    html.append(host);
    html.style.setProperty("margin-top", `${HEIGHT}px`, "important");
    observer.observe(html, { childList: true });
    observer.observe(host, { attributes: true });
  }

  if (state.timer !== null) clearTimeout(state.timer);
  state.timer = mode === "stopped" ? setTimeout(() => unmountBanner(doc), STOPPED_MS) : null;
  render(state, mode);
}

export function unmountBanner(doc: Document): void {
  const state = mounted.get(doc);
  if (!state) return;
  mounted.delete(doc);
  if (state.timer !== null) clearTimeout(state.timer);
  state.observer.disconnect();
  state.host.remove();
  doc.documentElement.style.setProperty("margin-top", state.marginValue, state.marginPriority);
}
