import { useState } from "react";
import type { PlanScope } from "../controller";
import { ACTIONS, TEXT } from "./strings";

interface Props {
  steps: string[];
  scope: PlanScope;
  onStart: (mode: "ask" | "auto") => void;
  onEdit: () => void;
}

export function Plan({ steps, scope, onStart, onEdit }: Props) {
  const [mode, setMode] = useState<"ask" | "auto">("ask");

  return (
    <section className="card" aria-labelledby="plan-title">
      <h2 id="plan-title" className="section-title">{TEXT.planTitle}</h2>
      <ol className="steps">
        {steps.map((step, index) => <li key={index}>{step}</li>)}
      </ol>

      {scope.start_host && (
        <div className="field-group">
          <h3 className="label">{TEXT.planStart}</h3>
          <p><code>{scope.start_host}</code></p>
        </div>
      )}

      {scope.hosts.length > 0 && (
        <div className="field-group">
          <h3 className="label">{TEXT.planScope}</h3>
          <ul className="chips">
            {scope.hosts.map((host) => <li key={host}><code>{host}</code></li>)}
          </ul>
        </div>
      )}

      {scope.kinds.length > 0 && (
        <div className="field-group">
          <h3 className="label">{TEXT.planKinds}</h3>
          <p className="note">{scope.kinds.map((kind) => ACTIONS[kind] ?? kind).join(", ")}</p>
        </div>
      )}

      <fieldset className="field-group">
        <legend className="label">{TEXT.planMode}</legend>
        {(["ask", "auto"] as const).map((value) => (
          <div className="choice" key={value}>
            <input type="radio" id={`mode-${value}`} name="mode" value={value} checked={mode === value}
              aria-describedby={`mode-${value}-hint`} onChange={() => setMode(value)} />
            <label htmlFor={`mode-${value}`} className="choice-name">{value === "ask" ? TEXT.modeAsk : TEXT.modeAuto}</label>
            <span id={`mode-${value}-hint`} className="choice-hint">{value === "ask" ? TEXT.modeAskHint : TEXT.modeAutoHint}</span>
          </div>
        ))}
      </fieldset>

      <div className="actions even">
        <button type="button" className="secondary" onClick={onEdit}>{TEXT.edit}</button>
        <button type="button" className="primary" onClick={() => onStart(mode)}>{TEXT.start}</button>
      </div>
    </section>
  );
}
