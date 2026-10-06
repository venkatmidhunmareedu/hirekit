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
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

import { ErrorNotice } from "../../../components/ErrorNotice";
import { STAGES, type Stage } from "../api";
import { useChangeStage } from "../hooks";
import { STAGE_LABEL } from "../labels";

const MOVES = STAGES.filter((s) => s !== "rejected");

/**
 * Hiring stage control (Design.md 7.7). Rejected sits apart and always asks first; only a
 * recruiter's explicit choice here changes a stage.
 */
export function StageControl({ candidateId, stage }: { candidateId: string; stage: Stage | null }) {
  const change = useChangeStage(candidateId);
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState("");

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="stage">Hiring stage</Label>
        <Select
          value={stage ?? ""}
          disabled={change.isPending}
          onValueChange={(value) => {
            const next = STAGES.find((s) => s === value);
            if (!next) return;
            if (next === "rejected") setConfirming(true);
            else change.mutate({ stage: next, reason: null });
          }}
        >
          <SelectTrigger id="stage" className="h-10 w-52">
            <SelectValue placeholder="Not set" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectLabel>Hiring stages</SelectLabel>
              {MOVES.map((s) => (
                <SelectItem key={s} value={s}>
                  {STAGE_LABEL[s]}
                </SelectItem>
              ))}
            </SelectGroup>
            <SelectSeparator />
            <SelectGroup>
              <SelectLabel>Reject</SelectLabel>
              <SelectItem value="rejected">{STAGE_LABEL.rejected}</SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>
      {change.error && !confirming && <ErrorNotice error={change.error} />}
      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-2xl font-medium">Reject this candidate?</DialogTitle>
            <DialogDescription>
              This is recorded under your name and can be reversed by a recruiter. Nothing is hidden
              or removed from the list.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reject-reason">Reason (optional)</Label>
            <Textarea
              id="reject-reason"
              rows={2}
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
              }}
            />
          </div>
          {change.error && <ErrorNotice error={change.error} />}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              className="h-10 px-4"
              onClick={() => {
                setConfirming(false);
              }}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              className="h-10 px-4"
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
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
