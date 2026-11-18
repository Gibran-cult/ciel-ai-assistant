// @vitest-environment node
import { ed25519 } from "@noble/curves/ed25519.js";
import { vi } from "vitest";
import vectors from "../src/shared/vectors/tickets.json";
import { normalizeHost } from "../src/hosts";
import { checkAction, Runner, type RunnerDeps } from "../src/runner";
import { canonical } from "../src/tickets";

const NOW = 1_795_000_000;
const SECRET = new Uint8Array(32).fill(7);
const KEYS = [{ kid: "testkey", alg: "Ed25519", key: b64url(ed25519.getPublicKey(SECRET)) }];

function b64url(bytes: Uint8Array): string {
  return Buffer.from(bytes).toString("base64url");
}

function sign(over: Record<string, unknown> = {}) {
  const ticket = { v: 1, task: "t1", device: "d1", seq: 3, tool: "tab_click", args: { ref: 5 }, host: "shopee.co.id", exp: NOW + 60, ...over };
  return { ticket, kid: "testkey", sig: b64url(ed25519.sign(canonical(ticket), SECRET)) };
}

function context(over: Partial<Parameters<typeof checkAction>[1]> = {}) {
  return { keys: KEYS, task: "t1", device: "d1", lastSeq: 2, now: NOW, tabHost: "shopee.co.id" as string | null | undefined,
    hasPermission: async () => true, ...over };
}

describe("checkAction", () => {
  test.each(vectors.cases.map((item) => [item.name, item]))("ticket vector: %s", async (_name, item) => {
    const { task, device, last_seq, now } = item.context;
    const reason = await checkAction(item.signed, { keys: item.keys, task, device, lastSeq: last_seq, now,
      tabHost: "shopee.co.id", hasPermission: async () => true });
    expect(reason).toBe(item.expect);
  });

  test("a tab that moved to another site is refused", async () => {
    expect(await checkAction(sign(), context({ tabHost: "evil.example" }))).toBe("host_changed");
    expect(await checkAction(sign(), context({ tabHost: null }))).toBe("host_changed");
    expect(await checkAction(sign(), context({ tabHost: "SHOPEE.co.id." }))).toBeNull();
  });

  test("a tab whose address cannot be seen is host_changed with permission, no_permission without", async () => {
    expect(await checkAction(sign(), context({ tabHost: undefined }))).toBe("host_changed");
    expect(await checkAction(sign(), context({ tabHost: undefined, hasPermission: async () => false }))).toBe("no_permission");
  });

  test("tab_open compares the host of the URL it opens", async () => {
    const open = (url: string) => sign({ tool: "tab_open", args: { url }, host: "shopee.co.id" });
    expect(await checkAction(open("https://shopee.co.id/cari?q=kaos"), context({ tabHost: "other.example" }))).toBeNull();
    expect(await checkAction(open("https://evil.example/"), context())).toBe("host_changed");
    expect(await checkAction(open("http://shopee.co.id/"), context())).toBe("host_changed");
  });

  test("blocked hosts are refused even with a valid ticket", async () => {
    for (const host of ["klikbca.com", "ib.klikbca.com"]) {
      expect(await checkAction(sign({ host }), context({ tabHost: host }))).toBe("blocked_host");
    }
  });

  test("no site permission, no action", async () => {
    expect(await checkAction(sign(), context({ hasPermission: async () => false }))).toBe("no_permission");
  });

  test("the ticket is checked first", async () => {
    const forged = { ...sign({ host: "klikbca.com" }), sig: b64url(new Uint8Array(64)) };
    expect(await checkAction(forged, context({ tabHost: "evil.example", hasPermission: async () => false }))).toBe("bad_signature");
  });
});

test("normalizeHost follows guard/domains.py", () => {
  expect(normalizeHost("Shopee.CO.id.")).toBe("shopee.co.id");
  expect(normalizeHost("toko.test:8443")).toBe("toko.test");
  for (const bad of ["localhost", "evil.com\\.toko.co.id", "a b.com", "x@y.com", "", "-a.com"]) expect(normalizeHost(bad)).toBeNull();
});

describe("Runner", () => {
  function setup(over: Partial<RunnerDeps> = {}) {
    const reading = { observation: { ok: true, source: "page", text: "Kaos", host: "shopee.co.id", controls: {} }, generation: 4 };
    const executeScript = vi.fn(async (details: { files?: string[]; func?: unknown; args?: unknown[] }): Promise<{ result?: unknown }[]> =>
      details.files ? [{ result: undefined }] : [{ result: reading }]);
    const result = vi.fn(() => true);
    const needPermission = vi.fn();
    const deps: RunnerDeps = {
      keys: async () => KEYS,
      device: async () => "d1",
      now: () => NOW,
      tabs: {
        get: vi.fn(async () => ({ id: 1, windowId: 9, url: "https://shopee.co.id/produk/1", status: "complete" })),
        create: vi.fn(async () => ({ id: 2, windowId: 9 })),
        remove: vi.fn(async () => undefined),
      },
      scripting: { executeScript },
      hasPermission: vi.fn(async () => true),
      waitForLoad: vi.fn(async () => undefined),
      result,
      needPermission,
      ...over,
    };
    const runner = new Runner(deps);
    runner.begin(1);
    return { runner, deps, executeScript, result, needPermission, reading };
  }

  test("a valid action runs in the task tab and the result carries task and seq", async () => {
    const { runner, executeScript, result, reading } = setup();
    await runner.onAction(sign());
    expect(executeScript).toHaveBeenCalledWith(expect.objectContaining({ target: { tabId: 1 }, args: ["tab_click", { ref: 5 }, 0] }));
    expect(result).toHaveBeenCalledWith("t1", 3, reading.observation);
  });

  test("without permission nothing is injected and the panel is asked to show the button", async () => {
    const { runner, executeScript, result, needPermission } = setup({ hasPermission: vi.fn(async () => false) });
    await runner.onAction(sign());
    expect(executeScript).not.toHaveBeenCalled();
    expect(needPermission).toHaveBeenCalledWith("shopee.co.id");
    expect(result).toHaveBeenCalledWith("t1", 3, expect.objectContaining({ ok: false, controls: {} }));
  });

  test("a replayed ticket is refused the second time", async () => {
    const { runner, executeScript, result } = setup();
    const ticket = sign();
    await runner.onAction(ticket);
    await runner.onAction(ticket);
    expect(executeScript).toHaveBeenCalledTimes(1);
    expect(result.mock.calls[1]).toEqual(["t1", 3, expect.objectContaining({ ok: false })]);
  });

  test("the first verified ticket binds the task; tickets for another task are refused", async () => {
    const { runner, executeScript } = setup();
    await runner.onAction(sign());
    await runner.onAction(sign({ task: "t2", seq: 4 }));
    expect(executeScript).toHaveBeenCalledTimes(1);
  });

  test("after the task ends the next task starts its own numbering", async () => {
    const { runner, executeScript } = setup();
    await runner.onAction(sign({ seq: 5 }));
    runner.end();
    runner.begin(1);
    await runner.onAction(sign({ task: "t2", seq: 1 }));
    expect(executeScript).toHaveBeenCalledTimes(2);
  });

  test("a rotated key is fetched again once before refusing", async () => {
    const keys = vi.fn().mockResolvedValueOnce([{ kid: "old", alg: "Ed25519", key: "AAAA" }]).mockResolvedValue(KEYS);
    const { runner, executeScript } = setup({ keys });
    await runner.onAction(sign());
    expect(keys).toHaveBeenCalledTimes(2);
    expect(executeScript).toHaveBeenCalledTimes(1);
  });

  test("tab_read injects the content script first when the page has none", async () => {
    const { runner, executeScript, result, reading } = setup();
    executeScript.mockImplementationOnce(async () => [{ result: null }]);
    await runner.onAction(sign({ tool: "tab_read", args: {} }));
    expect(executeScript.mock.calls.some(([details]) => details.files?.[0] === "content.js")).toBe(true);
    expect(result).toHaveBeenCalledWith("t1", 3, reading.observation);
  });

  test("a click on a page with no content script is refused, never retried on a new page", async () => {
    const { runner, executeScript, result } = setup();
    executeScript.mockImplementation(async () => [{ result: null }]);
    await runner.onAction(sign());
    expect(executeScript.mock.calls.every(([details]) => !details.files)).toBe(true);
    expect(result).toHaveBeenCalledWith("t1", 3, expect.objectContaining({ ok: false }));
  });

  test("a click that navigates waits for the new page and reads it", async () => {
    const { runner, deps, executeScript, result, reading } = setup();
    executeScript.mockImplementationOnce(async () => {
      throw new Error("Frame with ID 0 was removed.");
    });
    await runner.onAction(sign());
    expect(deps.waitForLoad).toHaveBeenCalledWith(1);
    expect(result).toHaveBeenCalledWith("t1", 3, reading.observation);
  });

  test("tab_open opens a new tab in the same window and makes it the task tab", async () => {
    const { runner, deps } = setup();
    await runner.onAction(sign({ tool: "tab_open", args: { url: "https://shopee.co.id/cari?q=kaos" } }));
    expect(deps.tabs.create).toHaveBeenCalledWith({ url: "https://shopee.co.id/cari?q=kaos", windowId: 9, active: true });
    expect(runner.taskTab).toBe(2);
  });

  test("a ticket without task or seq gets no reply", async () => {
    const { runner, result } = setup();
    await runner.onAction({ ticket: "x" });
    expect(result).not.toHaveBeenCalled();
  });
});

test("refuse answers a held or late action without touching the tab", async () => {
  const result = vi.fn(() => true);
  const executeScript = vi.fn();
  const runner = new Runner({
    keys: async () => KEYS, device: async () => "d1", now: () => NOW,
    tabs: { get: vi.fn(), create: vi.fn(), remove: vi.fn() }, scripting: { executeScript },
    hasPermission: async () => true, waitForLoad: async () => undefined, result, needPermission: vi.fn(),
  });
  runner.refuse(sign(), "stopped");
  runner.refuse(sign({ seq: 4 }), "handover");
  runner.refuse({ ticket: "x" }, "stopped");
  expect(result.mock.calls).toEqual([
    ["t1", 3, expect.objectContaining({ ok: false, text: expect.stringContaining("dihentikan") })],
    ["t1", 4, expect.objectContaining({ ok: false, text: expect.stringContaining("serah terima") })],
  ]);
  expect(executeScript).not.toHaveBeenCalled();
});
