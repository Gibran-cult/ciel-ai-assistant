// Badge di ikon ekstensi: kosong, "ON" saat Ciel bekerja, "!" saat Ciel
// menunggu kamu (persetujuan, serah terima, atau jeda).
import tokens from "../../design/tokens.json";
import type { Phase } from "./stop";

export async function showBadge(phase: Phase, waiting = false): Promise<void> {
  const text = phase === "paused" || phase === "handover" || (phase === "running" && waiting) ? "!" : phase === "running" ? "ON" : "";
  await chrome.action.setBadgeText({ text });
  if (text) await chrome.action.setBadgeBackgroundColor({ color: text === "!" ? tokens.light.warn : tokens.light.accent });
}
