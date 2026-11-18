// Alamat layanan agent. Build produksi selalu memakai alamat produksi. Build
// pengembangan boleh diarahkan ke staging atau layanan lokal lewat
// chrome.storage.local kunci "apiBase".
export const PRODUCTION_API = "https://agent.ciel-ai.web.id";

const LOCAL = /^http:\/\/(localhost|127\.0\.0\.1)(:\d{1,5})?$/;

// Hanya asal (origin) tanpa path: https apa saja, atau http ke mesin sendiri.
function safeBase(value: unknown): value is string {
  if (typeof value !== "string") return false;
  if (LOCAL.test(value)) return true;

  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.origin === value;
  } catch {
    return false;
  }
}

// Build rilis (mode "production") selalu memakai alamat produksi.
export async function apiBase(development: boolean = import.meta.env.MODE !== "production"): Promise<string> {
  if (!development) return PRODUCTION_API;
  const { apiBase: chosen } = await chrome.storage.local.get("apiBase");
  return safeBase(chosen) ? chosen : PRODUCTION_API;
}
