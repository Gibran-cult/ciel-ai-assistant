import { TEXT } from "./strings";

// Stop selalu terlihat di kanan atas. Sekali tekan langsung berhenti, tanpa dialog.
export function StopButton({ active, onStop }: { active: boolean; onStop: () => void }) {
  return (
    <button type="button" className="stop" title={TEXT.stopTitle} disabled={!active} onClick={onStop}>
      <span className="stop-square" aria-hidden="true" />
      {TEXT.stop}
    </button>
  );
}
