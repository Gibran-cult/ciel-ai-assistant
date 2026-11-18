import { useRef } from "react";
import { textOf, useSafeDialog } from "./dialog";
import { previewSentence, TEXT } from "./strings";

// Mode "Tanya dulu": setiap aksi tampil sebagai satu kalimat sebelum dijalankan.
export function Preview({ id, prompt, onAnswer }: { id: number; prompt: Record<string, unknown>; onAnswer: (value: boolean) => void }) {
  const skip = useRef<HTMLButtonElement>(null);
  useSafeDialog(skip, () => onAnswer(false), id);
  const sentence = previewSentence(textOf(prompt.tool) ?? "", textOf(prompt.target) ?? "", textOf(prompt.text), textOf(prompt.url));

  return (
    <section className="card dialog" role="alertdialog" aria-modal="false" aria-labelledby="preview-title">
      <h2 id="preview-title" className="sentence">{sentence}</h2>
      <div className="actions even">
        <button ref={skip} type="button" className="secondary" onClick={() => onAnswer(false)}>{TEXT.skip}</button>
        <button type="button" className="primary" onClick={() => onAnswer(true)}>{TEXT.run}</button>
      </div>
    </section>
  );
}
