// Content script: disuntikkan hanya ke tab tugas (runner.ts). Menyediakan
// pembaca dan pelaksana aksi untuk service worker. Kalau disuntik dua kali
// di halaman yang sama, yang pertama dipakai supaya nomor rujukan tetap.
import { act } from "./act";
import { type BannerMode, mountBanner, unmountBanner } from "./banner";
import { observe } from "./reader";
import { watchTakeover } from "./takeover";

function banner(mode: BannerMode | null): void {
  if (mode === null) unmountBanner(document);
  else mountBanner(document, mode);
}

const scope = globalThis as { cielAgent?: { act: typeof act; observe: typeof observe; banner: typeof banner } };
if (!scope.cielAgent) {
  scope.cielAgent = Object.freeze({ act, observe, banner });

  // Klik atau ketikan pengguna sungguhan di tab ini dilaporkan ke service worker.
  if (typeof chrome !== "undefined" && chrome.runtime?.id) {
    watchTakeover(document, () => void chrome.runtime.sendMessage({ type: "takeover" }).catch(() => undefined));
  }
}
