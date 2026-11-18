import { useState } from "react";
import { TEXT } from "./strings";

export function Ask({ question, onAnswer }: { question: string; onAnswer: (value: string) => void }) {
  const [answer, setAnswer] = useState("");

  return (
    <form
      className="card dialog"
      aria-labelledby="ask-title"
      onSubmit={(event) => {
        event.preventDefault();
        if (answer.trim()) onAnswer(answer.trim());
      }}
    >
      <h2 id="ask-title" className="sentence">{question}</h2>
      <label className="label" htmlFor="ask-answer">{TEXT.askLabel}</label>
      <textarea id="ask-answer" rows={3} maxLength={2000} value={answer} onChange={(event) => setAnswer(event.target.value)} />
      <div className="actions">
        <button type="submit" className="primary" disabled={!answer.trim()}>{TEXT.askSend}</button>
      </div>
    </form>
  );
}
