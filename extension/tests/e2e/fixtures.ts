import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { type BrowserContext, chromium, expect, type Page, test as base, type Worker } from "@playwright/test";

export const API = "http://127.0.0.1:8611";
export const SHOP = "https://toko.test:8612";
const { id: EXTENSION_ID } = JSON.parse(readFileSync(new URL("./key.json", import.meta.url), "utf8"));
const DIST = fileURLToPath(new URL("../../dist-e2e", import.meta.url));

export interface Script {
  plan: { steps: string[]; hosts: string[]; kinds: string[]; spend_cap: number };
  calls: { tool: string; args: Record<string, unknown> }[];
}

async function worker(context: BrowserContext): Promise<Worker> {
  return context.serviceWorkers()[0] ?? context.waitForEvent("serviceworker");
}

function launch(profile: string): Promise<BrowserContext> {
  return chromium.launchPersistentContext(profile, {
    // E2E_BROWSER: browser Chromium lain (mis. Brave) kalau build Playwright tidak jalan di mesin ini.
    ...(process.env.E2E_BROWSER ? { executablePath: process.env.E2E_BROWSER } : { channel: "chromium" }),
    headless: !process.env.HEADED,
    ignoreHTTPSErrors: true,
    args: [`--disable-extensions-except=${DIST}`, `--load-extension=${DIST}`, "--host-resolver-rules=MAP toko.test 127.0.0.1",
      // Browser baru mematikan --load-extension secara bawaan; nyalakan lagi untuk profil uji sementara ini.
      "--disable-features=DisableLoadExtensionCommandLineSwitch"],
  });
}

export const test = base.extend<{ context: BrowserContext; agent: Agent }>({
  // Profil sementara yang sudah "masuk": token disimpan di sesi pertama, lalu
  // browser dibuka ulang supaya service worker mulai dari keadaan itu.
  context: async ({}, use) => {
    const profile = mkdtempSync(join(tmpdir(), "ciel-e2e-"));
    const tokens = await (await fetch(`${API}/test/device`, { method: "POST" })).json();
    const first = await launch(profile);
    await (await worker(first)).evaluate(async ({ api, refresh, device }) => {
      await chrome.storage.local.set({ apiBase: api, refreshToken: refresh, device });
    }, { api: API, refresh: tokens.refresh_token, device: tokens.device });
    await first.close();

    const context = await launch(profile);
    await use(context);
    await context.close();
    rmSync(profile, { recursive: true, force: true });
  },
  agent: async ({ context }, use) => {
    const panel = await context.newPage();
    await panel.goto(`chrome-extension://${EXTENSION_ID}/panel/index.html`);
    // Sudah masuk, dan pemberitahuan koneksi hilang setelah WebSocket siap.
    await panel.getByText("Siap").waitFor();
    await expect(panel.locator(".notice")).toHaveCount(0, { timeout: 20_000 });
    await use(new Agent(context, panel));
  },
});

/** Ekstensi yang sudah masuk sebagai akun uji, dengan panel terbuka di tab sendiri. */
export class Agent {
  constructor(public context: BrowserContext, public panel: Page) {}

  async script(script: Script): Promise<void> {
    await fetch(`${API}/test/script`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(script) });
  }

  async open(path: string): Promise<Page> {
    const page = await this.context.newPage();
    await page.goto(`${SHOP}${path}`);
    return page;
  }

  /** Mulai tugas di tab toko. Panel di uji ini adalah tab biasa, jadi tab tugasnya dipilih langsung. */
  async start(instruction: string): Promise<void> {
    await this.panel.evaluate(async (text) => {
      const [tab] = await chrome.tabs.query({ url: "https://toko.test/*" });
      chrome.runtime.connect({ name: "panel" }).postMessage({ type: "start", instruction: text, tabId: tab!.id });
    }, instruction);
  }
}

export { expect } from "@playwright/test";
