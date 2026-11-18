import type { SocketState } from "../socket";
import { TEXT } from "./strings";

// Luring: Stop tetap bisa ditekan (lihat StopButton di App), aksi baru ditahan.
export function Offline({ connection }: { connection: SocketState }) {
  const text = connection === "update_required" ? TEXT.updateRequired
    : connection === "origin_refused" ? TEXT.originRefused
    : connection === "connecting" ? TEXT.connecting : TEXT.offline;
  return <p className="notice" role="status">{text}</p>;
}
