import { useEffect, useState } from "react";
import type { PanelCommand, PanelState } from "../controller";
import { Ask } from "./Ask";
import { Confirm } from "./Confirm";
import { Handover } from "./Handover";
import { Log } from "./Log";
import { Offline } from "./Offline";
import { Plan } from "./Plan";
import { Preview } from "./Preview";
import { SignedOut } from "./SignedOut";
import { StopButton } from "./StopButton";
import { TEXT } from "./strings";

interface Props {
  state: PanelState;
  send: (command: PanelCommand) => void;
  activeTab: () => Promise<number | null>;
  requestPermission: (host: string) => Promise<boolean>;
}

function statusText(state: PanelState): string {
  if (state.phase === "running" && state.dialog && state.dialog.kind !== "handover") return TEXT.status.waiting;
  return TEXT.status[state.phase];
}

function statusTone(state: PanelState): string {
  if (state.phase === "running") return state.dialog ? "wait" : "active";
  if (state.phase === "handover") return "wait";
  return "quiet";
}

export function App({ state, send, activeTab, requestPermission }: Props) {
  const [instruction, setInstruction] = useState(state.instruction);
  const busy = state.phase === "running" || state.phase === "paused" || state.phase === "handover";
  const signedIn = state.auth === "signed_in";

  // "Ubah" di kartu rencana mengembalikan perintah ke kolom.
  useEffect(() => setInstruction(state.instruction), [state.instruction]);

  async function start() {
    const tabId = await activeTab();
    if (tabId !== null && instruction.trim()) send({ type: "start", instruction: instruction.trim(), tabId });
  }

  async function allow(host: string) {
    if (await requestPermission(host)) send({ type: "permission_granted" });
  }

  const dialog = state.dialog;

  return (
    <div className="panel">
      <header className="top">
        <div className="top-text">
          <h1 className="app-title">{TEXT.title}</h1>
          {signedIn && (
            <p className={`status ${statusTone(state)}`} role="status">
              <span className="status-mark" aria-hidden="true" />
              {statusText(state)}
            </p>
          )}
        </div>
        <StopButton active={busy} onStop={() => send({ type: "stop" })} />
      </header>

      <main className="body">
        {!signedIn && (
          <SignedOut consentRequired={state.auth === "consent_required"} failed={state.loginFailed} onLogin={() => send({ type: "login" })} />
        )}

        {signedIn && state.connection !== "ready" && <Offline connection={state.connection} />}

        {signedIn && state.needPermission && (
          <section className="card" aria-labelledby="permission-title">
            <h2 id="permission-title" className="section-title">{TEXT.permissionNeeded(state.needPermission)}</h2>
            <button type="button" className="primary" onClick={() => void allow(state.needPermission!)}>
              {TEXT.permissionButton(state.needPermission)}
            </button>
          </section>
        )}

        {signedIn && dialog?.kind === "plan" && (
          <Plan steps={dialog.steps} scope={dialog.scope}
            onStart={(mode) => send({ type: "answer", id: dialog.id, value: mode })}
            onEdit={() => send({ type: "answer", id: dialog.id, value: null })} />
        )}

        {signedIn && dialog?.kind === "confirm" && (dialog.prompt.reason === "ask_mode"
          ? <Preview id={dialog.id} prompt={dialog.prompt} onAnswer={(value) => send({ type: "answer", id: dialog.id, value })} />
          : <Confirm id={dialog.id} prompt={dialog.prompt} onAnswer={(value) => send({ type: "answer", id: dialog.id, value })} />)}

        {signedIn && dialog?.kind === "handover" && (
          <Handover prompt={dialog.prompt} onDone={(done) => send({ type: "handover_done", done })} />
        )}

        {signedIn && dialog?.kind === "ask" && (
          <Ask question={dialog.question} onAnswer={(value) => send({ type: "answer", id: dialog.id, value })} />
        )}

        {signedIn && state.phase === "paused" && (
          <section className="card wait" aria-labelledby="paused-title">
            <h2 id="paused-title" className="section-title">{TEXT.pausedTitle}</h2>
            <p className="note">{TEXT.pausedNote}</p>
            <button type="button" className="primary" onClick={() => send({ type: "resume" })}>{TEXT.continue}</button>
          </section>
        )}

        {signedIn && state.ended && (
          <section className="card" aria-labelledby="end-title">
            <h2 id="end-title" className="section-title">{TEXT.endTitle[state.ended.status] ?? state.ended.status}</h2>
            {state.ended.reason && state.ended.status !== "done" && (
              <p>{TEXT.endReason[state.ended.reason] ?? TEXT.endCode(state.ended.reason)}</p>
            )}
            {state.ended.report && <p className="report">{state.ended.report}</p>}
            <p className="note">{TEXT.endSteps(state.ended.steps)}</p>
            <button type="button" className="secondary" onClick={() => send({ type: "dismiss" })}>{TEXT.dismiss}</button>
          </section>
        )}

        {signedIn && !busy && (
          <form className="block" onSubmit={(event) => { event.preventDefault(); void start(); }}>
            <label className="label" htmlFor="instruction">{TEXT.commandLabel}</label>
            <textarea id="instruction" rows={4} maxLength={2000} value={instruction}
              aria-describedby="instruction-hint" onChange={(event) => setInstruction(event.target.value)} />
            <p id="instruction-hint" className="note">{TEXT.commandHint}</p>
            <button type="submit" className="primary" disabled={!instruction.trim() || state.connection !== "ready"}>{TEXT.start}</button>
          </form>
        )}

        {signedIn && (busy || state.log.length > 0) && <Log lines={state.log} />}

        {signedIn && !busy && (
          <button type="button" className="quiet" onClick={() => send({ type: "logout" })}>{TEXT.signOut}</button>
        )}
      </main>
    </div>
  );
}
