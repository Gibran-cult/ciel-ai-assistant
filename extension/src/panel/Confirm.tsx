import { useRef } from "react";
import { textOf, useSafeDialog } from "./dialog";
import { confirmButton, confirmTitle, reasonText, TEXT } from "./strings";

interface Props {
  id: number;
  prompt: Record<string, unknown>;
  onAnswer: (value: boolean) => void;
}

// Konfirmasi aksi berisiko. Hanya ada di side panel, jadi halaman tidak bisa
// membuat, menutup, atau menekan tombolnya.
export function Confirm({ id, prompt, onAnswer }: Props) {
  const cancel = useRef<HTMLButtonElement>(null);
  useSafeDialog(cancel, () => onAnswer(false), id);

  const tool = textOf(prompt.tool) ?? "";
  const target = textOf(prompt.target) ?? "";
  const reason = textOf(prompt.reason);
  const url = textOf(prompt.url);
  const typed = textOf(prompt.text);
  const lookalike = textOf(prompt.lookalike);
  const widens = textOf(prompt.widens);
  const level = textOf(prompt.level);

  return (
    <section className="card dialog" role="alertdialog" aria-modal="false" aria-labelledby="confirm-title" aria-describedby="confirm-reason">
      <h2 id="confirm-title" className="dialog-title">{confirmTitle(tool, target)}</h2>
      {level && <p className="risk">{TEXT.risk(level)}</p>}
      {reason && <p id="confirm-reason">{reasonText(reason)}</p>}

      {lookalike && (
        <div className="compare">
          <div>
            <span className="label">{TEXT.lookalikeTarget}</span>
            <code>{target}</code>
          </div>
          <div>
            <span className="label">{TEXT.lookalikeCopied}</span>
            <code>{lookalike}</code>
          </div>
        </div>
      )}

      {url && (
        <div className="field-group">
          <span className="label">{TEXT.fullAddress}</span>
          <code className="address">{url}</code>
        </div>
      )}

      {typed && (
        <div className="field-group">
          <span className="label">{TEXT.typedText}</span>
          <p className="typed">{typed}</p>
        </div>
      )}

      {prompt.from_page === true && <p className="note">{TEXT.fromPage}</p>}
      {widens && <p className="note">{TEXT.widens(widens)}</p>}

      <div className="actions even">
        <button ref={cancel} type="button" className="secondary" onClick={() => onAnswer(false)}>{TEXT.cancel}</button>
        <button type="button" className="primary" onClick={() => onAnswer(true)}>{confirmButton(tool)}</button>
      </div>
    </section>
  );
}
