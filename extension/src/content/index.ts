// Content script: disuntikkan hanya ke tab tugas (runner.ts). Menyediakan
// pembaca dan pelaksana aksi untuk service worker. Kalau disuntik dua kali
// di halaman yang sama, yang pertama dipakai supaya nomor rujukan tetap.
import { act } from "./act";
import { observe } from "./reader";
import { watchTakeover } from "./takeover";

const scope = globalThis as { cielAgent?: { act: typeof act; observe: typeof observe } };
if (!scope.cielAgent) {
  scope.cielAgent = Object.freeze({ act, observe });

  // Klik atau ketikan pengguna sungguhan di tab ini dilaporkan ke service worker.
  if (typeof chrome !== "undefined" && chrome.runtime?.id) {
    watchTakeover(document, () => void chrome.runtime.sendMessage({ type: "takeover" }).catch(() => undefined));
  }
}
