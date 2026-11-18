import type { PanelLogLine } from "../controller";
import { TEXT } from "./strings";

export function Log({ lines }: { lines: PanelLogLine[] }) {
  return (
    <section className="block" aria-labelledby="log-title">
      <h2 id="log-title" className="section-title">{TEXT.logTitle}</h2>
      {lines.length === 0 ? (
        <p className="note">{TEXT.logEmpty}</p>
      ) : (
        <ol className="log" aria-live="polite">
          {lines.map((line, index) => (
            <li key={index} className="log-line">
              <span className="log-time">{line.time}</span>
              <span className="log-action">{line.action}</span>
              <code className="log-target">{line.target}</code>
              <span className="log-result">{line.result}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
