// Aturan host yang sama dengan guard/domains.py: normalize_host dan
// match_allowed. Daftar situs yang selalu diblokir diambil dari
// guard/blocked_targets.json lewat vektor bersama.
import blocked from "./shared/vectors/blocked.json";

const LABEL = "[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?";
const HOST = new RegExp(`^${LABEL}(?:\\.${LABEL})+$`);
const PORT = /:\d{1,5}$/;

/** Host huruf kecil tanpa port dan titik akhir, atau null kalau bukan nama host yang sah. */
export function normalizeHost(host: unknown): string | null {
  if (typeof host !== "string") return null;
  let clean = host.toLowerCase().replace(PORT, "");
  if (clean.endsWith(".")) clean = clean.slice(0, -1);
  return clean.length <= 253 && HOST.test(clean) ? clean : null;
}

/** Host dari alamat https, atau null. */
export function httpsHost(url: unknown): string | null {
  if (typeof url !== "string") return null;

  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" && !parsed.username && !parsed.password ? normalizeHost(parsed.hostname) : null;
  } catch {
    return null;
  }
}

export function isBlockedHost(host: string): boolean {
  return blocked.host_suffixes.some((domain) => host === domain || host.endsWith(`.${domain}`));
}
