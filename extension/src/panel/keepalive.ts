import { useEffect } from "react";

// Chrome bisa menghentikan service worker setelah sekitar 30 detik tanpa
// event, misalnya saat dialog rencana menunggu jawaban. Pesan lewat port
// panel dihitung sebagai event, jadi panel mengirim satu setiap 20 detik
// selama ada tugas.
const EVERY_MS = 20_000;

export function useKeepalive(active: boolean, post: (message: { type: "keepalive" }) => void): void {
  useEffect(() => {
    if (!active) return undefined;
    const timer = setInterval(() => post({ type: "keepalive" }), EVERY_MS);
    return () => clearInterval(timer);
  }, [active, post]);
}
