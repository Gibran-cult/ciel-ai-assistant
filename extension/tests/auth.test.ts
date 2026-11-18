// @vitest-environment node
import { afterEach, beforeEach, vi } from "vitest";
import { accessToken, challengeFor, login, logout, newVerifier, REFRESH_ALARM } from "../src/auth";
import { apiBase, PRODUCTION_API } from "../src/config";
import { fakeChrome, type FakeChrome, json } from "./fake_chrome";

const NOW = 1_795_000_000_000;
const TOKENS = { device: "dev1", access_token: "cat1.owner.ACCESS", refresh_token: "crt1.owner.REFRESH", expires_in: 900 };
let chrome: FakeChrome;
let fetchMock: ReturnType<typeof vi.fn>;
const logged: unknown[] = [];

beforeEach(() => {
  chrome = fakeChrome();
  vi.stubGlobal("chrome", chrome);
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  logged.length = 0;
  for (const level of ["log", "info", "warn", "error", "debug"] as const) {
    vi.spyOn(console, level).mockImplementation((...args: unknown[]) => {
      logged.push(...args);
    });
  }
});

afterEach(() => {
  // Token tidak pernah masuk console.
  expect(JSON.stringify(logged.map(String))).not.toMatch(/ACCESS|REFRESH|cat1\.|crt1\./);
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function redirectWith(params: Record<string, string>) {
  chrome.identity.launchWebAuthFlow.mockImplementation(async ({ url }) => {
    const state = new URL(url).searchParams.get("state")!;
    return `https://abcdefghijklmnop.chromiumapp.org/?${new URLSearchParams({ state, ...params })}`;
  });
}

test("PKCE challenge matches RFC 7636 appendix B", async () => {
  expect(await challengeFor("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")).toBe("E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM");
});

test("verifiers are 64 unreserved characters and differ each time", () => {
  const first = newVerifier();
  expect(first).toMatch(/^[A-Za-z0-9._~-]{64}$/);
  expect(newVerifier()).not.toBe(first);
});

test("login opens the device login page and trades the code", async () => {
  redirectWith({ code: "cdc1.owner.CODE" });
  fetchMock.mockResolvedValue(json(200, TOKENS));

  expect(await login(NOW)).toEqual({ kind: "ok", device: "dev1" });

  const details = chrome.identity.launchWebAuthFlow.mock.calls[0]![0];
  const opened = new URL(details.url);
  expect(opened.origin + opened.pathname).toBe(`${PRODUCTION_API}/v1/device/login`);
  expect(opened.searchParams.get("redirect")).toBe("https://abcdefghijklmnop.chromiumapp.org/");
  expect(opened.searchParams.get("challenge")).toMatch(/^[A-Za-z0-9_-]{43}$/);
  expect(opened.searchParams.get("state")).toMatch(/^[A-Za-z0-9_-]{32}$/);
  expect(details.interactive).toBe(true);

  const [url, init] = fetchMock.mock.calls[0]!;
  expect(url).toBe(`${PRODUCTION_API}/v1/device/token`);
  const body = JSON.parse(init.body);
  expect(body).toMatchObject({ code: "cdc1.owner.CODE", platform: "extension" });
  expect(await challengeFor(body.verifier)).toBe(opened.searchParams.get("challenge"));
  expect(body.name.length).toBeGreaterThan(0);
  expect(body.name.length).toBeLessThanOrEqual(60);

  // Token akses hanya di sesi, token pembaruan di local.
  expect(chrome.storage.session.data).toEqual({ accessToken: TOKENS.access_token, accessExpires: NOW + 900_000 });
  expect(chrome.storage.local.data).toEqual({ refreshToken: TOKENS.refresh_token, device: "dev1" });
  expect(chrome.alarms.create).toHaveBeenCalledWith(REFRESH_ALARM, { when: NOW + 840_000 });
});

test("a different state is refused and no code is traded", async () => {
  chrome.identity.launchWebAuthFlow.mockResolvedValue("https://abcdefghijklmnop.chromiumapp.org/?code=cdc1.x.y&state=other");
  expect(await login(NOW)).toEqual({ kind: "failed", reason: "state_mismatch" });
  expect(fetchMock).not.toHaveBeenCalled();
});

test("consent_required from the redirect or the token exchange is recognised", async () => {
  redirectWith({ error: "consent_required" });
  expect(await login(NOW)).toEqual({ kind: "consent_required" });
  expect(fetchMock).not.toHaveBeenCalled();

  redirectWith({ code: "cdc1.owner.CODE" });
  fetchMock.mockResolvedValue(json(403, { error: "consent_required" }));
  expect(await login(NOW)).toEqual({ kind: "consent_required" });
  expect(chrome.storage.local.data).toEqual({});
});

test("closing the login window is a cancel, not an error", async () => {
  chrome.identity.launchWebAuthFlow.mockRejectedValue(new Error("The user did not approve access."));
  expect(await login(NOW)).toEqual({ kind: "cancelled" });
});

test("a broken token answer stores nothing", async () => {
  redirectWith({ code: "cdc1.owner.CODE" });
  fetchMock.mockResolvedValue(json(200, { device: "dev1", access_token: 5 }));
  expect(await login(NOW)).toEqual({ kind: "failed", reason: "bad_response" });
  expect(chrome.storage.session.data).toEqual({});
  expect(chrome.storage.local.data).toEqual({});
});

test("a fresh access token is returned without a request", async () => {
  chrome.storage.session.data.accessToken = TOKENS.access_token;
  chrome.storage.session.data.accessExpires = NOW + 120_000;
  expect(await accessToken(NOW)).toBe(TOKENS.access_token);
  expect(fetchMock).not.toHaveBeenCalled();
});

test("an access token close to expiry is refreshed once, even when asked twice", async () => {
  chrome.storage.session.data.accessToken = "cat1.owner.OLDACCESS";
  chrome.storage.session.data.accessExpires = NOW + 30_000;
  chrome.storage.local.data.refreshToken = "crt1.owner.OLDREFRESH";
  fetchMock.mockResolvedValue(json(200, TOKENS));

  const [first, second] = await Promise.all([accessToken(NOW), accessToken(NOW)]);
  expect([first, second]).toEqual([TOKENS.access_token, TOKENS.access_token]);
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(fetchMock.mock.calls[0]![0]).toBe(`${PRODUCTION_API}/v1/device/refresh`);
  expect(JSON.parse(fetchMock.mock.calls[0]![1].body)).toEqual({ refresh_token: "crt1.owner.OLDREFRESH" });
  expect(chrome.storage.local.data.refreshToken).toBe(TOKENS.refresh_token);
});

test("a refresh answered 401 removes every token", async () => {
  chrome.storage.session.data.accessToken = "cat1.owner.OLDACCESS";
  chrome.storage.session.data.accessExpires = NOW - 1;
  chrome.storage.local.data.refreshToken = "crt1.owner.OLDREFRESH";
  chrome.storage.local.data.device = "dev1";
  fetchMock.mockResolvedValue(json(401, { error: "invalid_grant" }));

  expect(await accessToken(NOW)).toBeNull();
  expect(chrome.storage.session.data).toEqual({});
  expect(chrome.storage.local.data).toEqual({});
  expect(chrome.alarms.clear).toHaveBeenCalledWith(REFRESH_ALARM);
});

test("a network error keeps the tokens and returns a still-valid access token", async () => {
  chrome.storage.session.data.accessToken = TOKENS.access_token;
  chrome.storage.session.data.accessExpires = NOW + 30_000;
  chrome.storage.local.data.refreshToken = "crt1.owner.OLDREFRESH";
  fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

  expect(await accessToken(NOW)).toBe(TOKENS.access_token);
  expect(chrome.storage.local.data.refreshToken).toBe("crt1.owner.OLDREFRESH");
  expect(await accessToken(NOW + 31_000)).toBeNull();
});

test("logout removes local tokens", async () => {
  chrome.storage.session.data.accessToken = TOKENS.access_token;
  chrome.storage.local.data.refreshToken = TOKENS.refresh_token;
  chrome.storage.local.data.device = "dev1";
  await logout();
  expect(chrome.storage.session.data).toEqual({});
  expect(chrome.storage.local.data).toEqual({});
});

test("the API base changes only in a development build, and only to a safe address", async () => {
  chrome.storage.local.data.apiBase = "https://agent-staging.ciel-ai.web.id";
  expect(await apiBase(false)).toBe(PRODUCTION_API);
  expect(await apiBase(true)).toBe("https://agent-staging.ciel-ai.web.id");
  chrome.storage.local.data.apiBase = "http://localhost:8600";
  expect(await apiBase(true)).toBe("http://localhost:8600");
  for (const unsafe of ["http://evil.example", "https://x.example/path", "javascript:alert(1)", 7]) {
    chrome.storage.local.data.apiBase = unsafe;
    expect(await apiBase(true)).toBe(PRODUCTION_API);
  }
});

test("review: the rotated refresh token is saved before the access token", async () => {
  chrome.storage.session.data.accessToken = "cat1.owner.OLDACCESS";
  chrome.storage.session.data.accessExpires = NOW - 1;
  chrome.storage.local.data.refreshToken = "crt1.owner.OLDREFRESH";
  fetchMock.mockResolvedValue(json(200, TOKENS));
  await accessToken(NOW);
  const local = chrome.storage.local.set.mock.invocationCallOrder[0]!;
  const session = chrome.storage.session.set.mock.invocationCallOrder[0]!;
  expect(local).toBeLessThan(session);
});
