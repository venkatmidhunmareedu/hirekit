import { useState } from "react";

import { ErrorNotice } from "../../../components/ErrorNotice";
import { Modal } from "../../../components/Modal";
import { type ScoreCell } from "../api";
import { useOverride } from "../hooks";

import { EvidenceBlock, ScoreChip } from "./ScoreParts";

const MIN_NOTE = 10;

/** Change score dialog (Design.md 7.6): new score, required note, the AI value for reference. */
export function OverrideDialog({
  candidateId,
  cell,
  onClose,
}: {
  candidateId: string;
  cell: ScoreCell;
  onClose: () => void;
}) {
  const override = useOverride(candidateId);
  const [score, setScore] = useState<number | null>(cell.override_score ?? cell.model_score);
  const [note, setNote] = useState("");
  const valid = score !== null && note.trim().length >= MIN_NOTE;

  return (
    <Modal title={`Change score: ${cell.criterion_name}`} onClose={onClose}>
      <p className="muted">AI suggestion</p>
      <ScoreChip model={cell.model_score} override={null} />
      <EvidenceBlock cell={cell} />
      <form
        className="stack"
        onSubmit={(event) => {
          event.preventDefault();
          if (score === null || !valid) return;
          override.mutate(
            { criterionId: cell.criterion_id, score, note: note.trim() },
            { onSuccess: onClose },
          );
        }}
      >
        <fieldset className="radio-row">
          <legend>New score</legend>
          {[0, 1, 2, 3, 4].map((n) => (
            <label key={n} className="radio">
              <input
                type="radio"
                name="override-score"
                checked={score === n}
                onChange={() => {
                  setScore(n);
                }}
              />
              <span className="mono">{n}</span>
            </label>
          ))}
        </fieldset>
        <div className="field">
          <label htmlFor="override-note">Note (at least {MIN_NOTE} characters)</label>
          <textarea
            id="override-note"
            rows={3}
            value={note}
            onChange={(e) => {
              setNote(e.target.value);
            }}
          />
        </div>
        {override.error && <ErrorNotice error={override.error} />}
        <div className="actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={!valid || override.isPending}>
            Save score
          </button>
        </div>
      </form>
    </Modal>
  );
}
