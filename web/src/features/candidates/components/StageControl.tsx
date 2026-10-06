import { useState } from "react";

import { ErrorNotice } from "../../../components/ErrorNotice";
import { Modal } from "../../../components/Modal";
import { STAGES, type Stage } from "../api";
import { useChangeStage } from "../hooks";

const MOVES = STAGES.filter((s) => s !== "rejected");

/**
 * Stage control (Design.md 7.7). Rejected sits apart and always asks first; only a
 * recruiter's explicit choice here changes a stage.
 */
export function StageControl({ candidateId, stage }: { candidateId: string; stage: Stage | null }) {
  const change = useChangeStage(candidateId);
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState("");

  return (
    <div className="stack">
      <div className="field">
        <label htmlFor="stage">Stage</label>
        <select
          id="stage"
          value={stage ?? ""}
          disabled={change.isPending}
          onChange={(e) => {
            const next = STAGES.find((s) => s === e.target.value);
            if (!next) return;
            if (next === "rejected") setConfirming(true);
            else change.mutate({ stage: next, reason: null });
          }}
        >
          {stage === null && <option value="">Not set</option>}
          <optgroup label="Stages">
            {MOVES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </optgroup>
          <optgroup label="Reject">
            <option value="rejected">rejected</option>
          </optgroup>
        </select>
      </div>
      {change.error && !confirming && <ErrorNotice error={change.error} />}
      {confirming && (
        <Modal
          title="Reject this candidate?"
          onClose={() => {
            setConfirming(false);
          }}
        >
          <p>
            This is recorded under your name and can be reversed by a recruiter. Nothing is hidden
            or removed from the list.
          </p>
          <div className="field">
            <label htmlFor="reject-reason">Reason (optional)</label>
            <textarea
              id="reject-reason"
              rows={2}
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
              }}
            />
          </div>
          {change.error && <ErrorNotice error={change.error} />}
          <div className="actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setConfirming(false);
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-destructive"
              disabled={change.isPending}
              onClick={() => {
                change.mutate(
                  { stage: "rejected", reason: reason.trim() || null },
                  {
                    onSuccess: () => {
                      setConfirming(false);
                    },
                  },
                );
              }}
            >
              Reject candidate
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
