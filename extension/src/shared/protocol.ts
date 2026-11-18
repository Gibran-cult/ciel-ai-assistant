// Bentuk pesan sesuai docs/agent-protocol.md. Server menolak kunci di luar
// daftar ini (OBSERVATION_KEYS dan CONTROL_KEYS di agent_api/ws.py).

export interface Control {
  field_type: string | null;
  submits: boolean;
  effect: string | null;
}

export interface Observation {
  ok: boolean;
  source: "page" | "file" | "screen" | "listing" | "tool";
  text: string;
  host: string | null;
  controls: Record<string, Control>;
}
