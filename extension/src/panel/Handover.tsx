import { useEffect, useRef } from "react";
import { textOf } from "./dialog";
import { reasonText, TEXT } from "./strings";

// Serah terima: pengguna mengerjakan langkah ini sendiri. Hanya "Lanjutkan"
// yang menyalakan pembaca halaman lagi.
export function Handover({ prompt, onDone }: { prompt: Record<string, unknown>; onDone: (done: boolean) => void }) {
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => title.current?.focus(), []);
  const reason = textOf(prompt.reason);
  const target = textOf(prompt.target);

  return (
    <section className="card dialog wait" aria-labelledby="handover-title">
      <h2 id="handover-title" ref={title} tabIndex={-1} className="dialog-title">{TEXT.handoverTitle}</h2>
      {reason && <p>{reasonText(reason)}</p>}
      {target && <p><code>{target}</code></p>}
      <p className="note">{TEXT.handoverNote}</p>
      <div className="actions even">
        <button type="button" className="secondary" onClick={() => onDone(false)}>{TEXT.skipStep}</button>
        <button type="button" className="primary" onClick={() => onDone(true)}>{TEXT.continue}</button>
      </div>
    </section>
  );
}
