import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Textarea } from "@/components/ui/textarea";

import { ErrorNotice } from "../../../components/ErrorNotice";
import { type ScoreCell } from "../api";
import { useOverride } from "../hooks";

import { EvidenceBlock, ScoreChip } from "./ScoreParts";

const MIN_NOTE = 10;

/** Change score dialog (Design.md 7.6): new score, required note, the AI value for reference. */
export function OverrideDialog({
  candidateId,
  cell,
  initialScore,
  onClose,
}: {
  candidateId: string;
  cell: ScoreCell;
  /** The segment the recruiter clicked; the note is still required before anything is saved. */
  initialScore?: number;
  onClose: () => void;
}) {
  const override = useOverride(candidateId);
  const [score, setScore] = useState<number | null>(
    initialScore ?? cell.override_score ?? cell.model_score,
  );
  const [note, setNote] = useState("");
  const length = note.trim().length;
  const noteReady = length >= MIN_NOTE;
  const valid = score !== null && noteReady;

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-2xl font-medium">
            Change score: {cell.criterion_name}
          </DialogTitle>
          <DialogDescription>
            Pick the score you give this criterion and say why. The AI suggestion stays on record.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col items-start gap-2">
          <p className="text-sm font-medium text-muted-foreground">AI suggestion</p>
          <ScoreChip model={cell.model_score} override={null} />
          <EvidenceBlock cell={cell} />
        </div>
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (score === null || !valid) return;
            override.mutate(
              { criterionId: cell.criterion_id, score, note: note.trim() },
              { onSuccess: onClose },
            );
          }}
        >
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-medium">New score</legend>
            <RadioGroup
              className="flex gap-4"
              value={score === null ? "" : String(score)}
              onValueChange={(value) => {
                setScore(Number(value));
              }}
            >
              {[0, 1, 2, 3, 4].map((n) => (
                <div key={n} className="flex min-h-10 items-center gap-2">
                  <RadioGroupItem id={`override-score-${n}`} value={String(n)} />
                  <Label htmlFor={`override-score-${n}`} className="mono font-mono">
                    {n}
                  </Label>
                </div>
              ))}
            </RadioGroup>
          </fieldset>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="override-note">Note (at least {MIN_NOTE} characters)</Label>
            <Textarea
              id="override-note"
              aria-describedby="override-note-count"
              rows={3}
              value={note}
              onChange={(e) => {
                setNote(e.target.value);
              }}
            />
            <p
              id="override-note-count"
              className={noteReady ? "text-sm text-ok" : "text-sm text-muted-foreground"}
            >
              {noteReady ? "Ready to save" : `${length} of ${MIN_NOTE} characters`}
            </p>
            <p role="status" className="sr-only">
              {noteReady ? "Note is long enough to save" : ""}
            </p>
          </div>
          {override.error && <ErrorNotice error={override.error} />}
          <DialogFooter>
            <Button type="button" variant="outline" className="h-10 px-4" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" className="h-10 px-4" disabled={!valid || override.isPending}>
              Save score
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
