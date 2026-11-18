// Pemeriksa tiket aksi. Acuannya verify_ticket di agent_api/tickets.py, dan
// tests/tickets.test.ts menjalankan vektor yang dibuat dari kode Python itu.
// Setiap aksi dari server harus lolos di sini sebelum menyentuh halaman.
import { ed25519 } from "@noble/curves/ed25519.js";

export type TicketReason =
  | "bad_form" | "unknown_key" | "bad_signature" | "wrong_task" | "wrong_device" | "old_seq" | "expired";

export interface PublicKeyEntry {
  kid: string;
  alg: string;
  key: string;
}

export interface TicketContext {
  task: string;
  device: string;
  lastSeq: number;
  now: number;
}

const SIGNED_KEYS = ["kid", "sig", "ticket"];
const B64URL = /^[A-Za-z0-9_-]*$/;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isInt(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value);
}

// Python mengurutkan kunci menurut code point, JavaScript menurut unit UTF-16.
// Keduanya berbeda untuk karakter di luar BMP, misalnya emoji.
function byCodePoint(a: string, b: string): number {
  const left = [...a];
  const right = [...b];

  for (let i = 0; i < Math.min(left.length, right.length); i++) {
    const diff = left[i]!.codePointAt(0)! - right[i]!.codePointAt(0)!;
    if (diff !== 0) return diff;
  }

  return left.length - right.length;
}

function encode(value: unknown): string {
  if (value === null || typeof value === "boolean" || typeof value === "string") return JSON.stringify(value);

  // Server hanya menandatangani bilangan bulat (nomor urut, waktu, ref). Angka
  // pecahan ditulis lain oleh Python ("1.0" lawan "1"), jadi ditolak.
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) throw new TypeError("only safe integers are signed");
    return String(value);
  }

  if (Array.isArray(value)) return `[${value.map(encode).join(",")}]`;

  if (isObject(value)) {
    const keys = Object.keys(value).sort(byCodePoint);
    return `{${keys.map((key) => `${JSON.stringify(key)}:${encode(value[key])}`).join(",")}}`;
  }

  throw new TypeError(`cannot sign ${typeof value}`);
}

/** Bentuk tiket yang ditandatangani, sama byte demi byte dengan canonical() di Python. */
export function canonical(ticket: unknown): Uint8Array {
  return new TextEncoder().encode(encode(ticket));
}

function unb64url(text: unknown): Uint8Array<ArrayBuffer> {
  if (typeof text !== "string" || !B64URL.test(text) || text.length % 4 === 1) throw new TypeError("bad base64url");
  const binary = atob(text.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (text.length % 4)) % 4));
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

/** WebCrypto dulu (Chrome 137+). Kalau Ed25519 belum didukung, pustaka @noble/curves (keputusan D19). */
export async function ed25519Verify(publicKey: Uint8Array<ArrayBuffer>, signature: Uint8Array<ArrayBuffer>,
  message: Uint8Array<ArrayBuffer>): Promise<boolean> {
  let key: CryptoKey;

  try {
    key = await crypto.subtle.importKey("raw", publicKey, { name: "Ed25519" }, false, ["verify"]);
  } catch (error) {
    if ((error as { name?: unknown } | null)?.name !== "NotSupportedError") throw error;

    try {
      return ed25519.verify(signature, message, publicKey, { zip215: false });
    } catch {
      return false;
    }
  }

  try {
    return await crypto.subtle.verify({ name: "Ed25519" }, key, signature, message);
  } catch {
    return false;
  }
}

/** Alasan tiket ditolak, atau null kalau sah. Tidak pernah melempar. */
export async function verifyTicket(signed: unknown, keys: unknown, context: TicketContext): Promise<TicketReason | null> {
  try {
    if (!isObject(signed) || Object.keys(signed).sort().join() !== SIGNED_KEYS.join()) return "bad_form";

    const { ticket, kid, sig } = signed;
    if (!isObject(ticket) || typeof kid !== "string" || typeof sig !== "string") return "bad_form";

    const entry = Array.isArray(keys)
      ? keys.find((item): item is PublicKeyEntry => isObject(item) && item.kid === kid && item.alg === "Ed25519")
      : undefined;
    if (entry === undefined) return "unknown_key";

    const message = canonical(ticket);
    let valid: boolean;

    try {
      valid = await ed25519Verify(unb64url(entry.key), unb64url(sig), message as Uint8Array<ArrayBuffer>);
    } catch {
      valid = false;
    }

    if (!valid) return "bad_signature";
    if (ticket.task !== context.task) return "wrong_task";
    if (ticket.device !== context.device) return "wrong_device";
    if (!isInt(ticket.seq) || ticket.seq <= context.lastSeq) return "old_seq";
    if (!isInt(ticket.exp) || context.now > ticket.exp) return "expired";
    return null;
  } catch {
    return "bad_form";
  }
}
