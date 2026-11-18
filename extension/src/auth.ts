// Login perangkat dengan PKCE (docs/agent-protocol.md bagian 1).
//
// Token akses hanya di chrome.storage.session (hilang saat browser ditutup,
// tidak terbaca content script). Token pembaruan di chrome.storage.local.
// Modul ini hanya dipakai service worker: token pembaruan sekali pakai, jadi
// dua konteks yang menyegarkan bersamaan akan membuat perangkat dicabut.
// Token tidak pernah ditulis ke console, pesan galat, URL, atau panel.
import { apiBase } from "./config";

export type LoginResult =
  | { kind: "ok"; device: string }
  | { kind: "consent_required" }
  | { kind: "cancelled" }
  | { kind: "failed"; reason: "state_mismatch" | "bad_redirect" | "network" | "bad_response" | "refused" };

interface Tokens {
  device: string;
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

export const REFRESH_ALARM = "ciel-refresh";
// Disegarkan satu menit sebelum token akses habis.
const MARGIN_MS = 60_000;

function b64url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function randomText(bytes: number): string {
  return b64url(crypto.getRandomValues(new Uint8Array(bytes)));
}

/** Verifier PKCE: 48 byte acak menjadi 64 karakter base64url. */
export function newVerifier(): string {
  return randomText(48);
}

export async function challengeFor(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return b64url(new Uint8Array(digest));
}

function deviceName(): string {
  const platform = (navigator as Navigator & { userAgentData?: { platform?: string } }).userAgentData?.platform;
  return (platform ? `Chrome di ${platform}` : "Chrome").slice(0, 60);
}

function isTokens(value: unknown): value is Tokens {
  const body = value as Partial<Tokens> | null;
  return typeof body === "object" && body !== null && typeof body.device === "string"
    && typeof body.access_token === "string" && typeof body.refresh_token === "string"
    && typeof body.expires_in === "number" && body.expires_in > 0;
}

async function errorCode(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return typeof body?.error === "string" ? body.error : "";
  } catch {
    return "";
  }
}

async function post(path: string, body: object): Promise<Response> {
  return fetch(`${await apiBase()}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
    credentials: "omit",
  });
}

async function save(tokens: Tokens, now: number): Promise<void> {
  const expires = now + tokens.expires_in * 1000;
  await chrome.storage.session.set({ accessToken: tokens.access_token, accessExpires: expires });
  await chrome.storage.local.set({ refreshToken: tokens.refresh_token, device: tokens.device });
  await chrome.alarms.create(REFRESH_ALARM, { when: expires - MARGIN_MS });
}

export async function login(now: number = Date.now()): Promise<LoginResult> {
  const verifier = newVerifier();
  const state = randomText(24);
  const redirect = chrome.identity.getRedirectURL();
  const query = new URLSearchParams({ challenge: await challengeFor(verifier), redirect, state });
  let returned: string | undefined;

  try {
    returned = await chrome.identity.launchWebAuthFlow({ url: `${await apiBase()}/v1/device/login?${query}`, interactive: true });
  } catch {
    // Jendela login ditutup, atau Google dibatalkan.
    return { kind: "cancelled" };
  }

  let params: URLSearchParams;

  try {
    const url = new URL(returned ?? "");
    if (url.origin !== new URL(redirect).origin) return { kind: "failed", reason: "bad_redirect" };
    params = url.searchParams;
  } catch {
    return { kind: "failed", reason: "bad_redirect" };
  }

  if (params.get("state") !== state) return { kind: "failed", reason: "state_mismatch" };
  if (params.get("error") === "consent_required") return { kind: "consent_required" };

  const code = params.get("code");
  if (!code) return { kind: "failed", reason: "refused" };

  let response: Response;

  try {
    response = await post("/v1/device/token", { code, verifier, name: deviceName(), platform: "extension" });
  } catch {
    return { kind: "failed", reason: "network" };
  }

  if (response.status === 403 && (await errorCode(response)) === "consent_required") return { kind: "consent_required" };
  if (!response.ok) return { kind: "failed", reason: "refused" };

  let body: unknown;

  try {
    body = await response.json();
  } catch {
    return { kind: "failed", reason: "bad_response" };
  }

  if (!isTokens(body)) return { kind: "failed", reason: "bad_response" };
  await save(body, now);
  return { kind: "ok", device: body.device };
}

async function stillValid(now: number): Promise<string | null> {
  const { accessToken: token, accessExpires } = await chrome.storage.session.get(["accessToken", "accessExpires"]);
  return typeof token === "string" && typeof accessExpires === "number" && accessExpires > now ? token : null;
}

async function refreshNow(now: number): Promise<string | null> {
  const { refreshToken } = await chrome.storage.local.get("refreshToken");
  if (typeof refreshToken !== "string") return stillValid(now);

  let response: Response;

  try {
    response = await post("/v1/device/refresh", { refresh_token: refreshToken });
  } catch {
    return stillValid(now);
  }

  // Token pembaruan ditolak: perangkat dicabut, dipakai ulang, atau habis.
  if (response.status === 401) {
    await logout();
    return null;
  }

  if (!response.ok) return stillValid(now);

  let body: unknown;

  try {
    body = await response.json();
  } catch {
    return stillValid(now);
  }

  if (!isTokens(body)) return stillValid(now);
  await save(body, now);
  return body.access_token;
}

let refreshing: Promise<string | null> | null = null;

/** Satu penyegaran pada satu waktu, supaya token pembaruan tidak terpakai dua kali. */
export function refresh(now: number = Date.now()): Promise<string | null> {
  refreshing ??= refreshNow(now).finally(() => {
    refreshing = null;
  });
  return refreshing;
}

/** Token akses yang masih berlaku lebih dari satu menit, disegarkan kalau perlu. null kalau belum login. */
export async function accessToken(now: number = Date.now()): Promise<string | null> {
  const { accessToken: token, accessExpires } = await chrome.storage.session.get(["accessToken", "accessExpires"]);
  if (typeof token === "string" && typeof accessExpires === "number" && accessExpires - now > MARGIN_MS) return token;
  return refresh(now);
}

/** Hapus token di perangkat ini. Mencabut perangkat di server dilakukan dari web. */
export async function logout(): Promise<void> {
  await chrome.storage.session.remove(["accessToken", "accessExpires"]);
  await chrome.storage.local.remove(["refreshToken", "device"]);
  await chrome.alarms.clear(REFRESH_ALARM);
}

export function handleAlarm(alarm: { name: string }): void {
  if (alarm.name === REFRESH_ALARM) void refresh();
}
