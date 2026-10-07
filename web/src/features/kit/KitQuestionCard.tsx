import {
  ArrowDown,
  ArrowUp,
  Check,
  ChevronDown,
  Ellipsis,
  Minus,
  Pencil,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { motion } from "motion/react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

import { ErrorNotice } from "../../components/ErrorNotice";

import { type Question } from "./api";
import { useDeleteQuestion, useEditQuestion, useRegenerate, useSwap } from "./hooks";

const FIELDS = [
  ["question_text", "Question"],
  ["strong_answer", "Strong answer"],
  ["weak_answer", "Weak answer"],
] as const;

/** Edit form in place of the card; the card keeps its slot so the rail and the scroll stay put. */
function QuestionForm({
  question,
  roleId,
  onDone,
}: {
  question: Question;
  roleId: string;
  onDone: () => void;
}) {
  const edit = useEditQuestion(roleId);
  const [draft, setDraft] = useState<Question>(question);
  return (
    <Card className="px-5">
      <form
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          edit.mutate(
            {
              id: question.id,
              patch: {
                question_text: draft.question_text.trim(),
                strong_answer: draft.strong_answer.trim(),
                weak_answer: draft.weak_answer.trim(),
              },
            },
            { onSuccess: onDone },
          );
        }}
      >
        {FIELDS.map(([field, label]) => (
          <div className="flex flex-col gap-1.5" key={field}>
            <Label htmlFor={`${field}-${question.id}`}>{label}</Label>
            <Textarea
              id={`${field}-${question.id}`}
              rows={3}
              required
              value={draft[field]}
              onChange={(e) => {
                setDraft({ ...draft, [field]: e.target.value });
              }}
            />
          </div>
        ))}
        {edit.error && <ErrorNotice error={edit.error} />}
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" className="h-10 px-4" onClick={onDone}>
            Cancel
          </Button>
          <Button type="submit" className="h-10 px-4" disabled={edit.isPending}>
            Save question
          </Button>
        </div>
      </form>
    </Card>
  );
}

function ActionsMenu({
  number,
  canUp,
  canDown,
  busy,
  on,
}: {
  number: number;
  canUp: boolean;
  canDown: boolean;
  busy: { swap: boolean; regenerate: boolean; remove: boolean };
  on: {
    edit: () => void;
    regenerate: () => void;
    up: () => void;
    down: () => void;
    remove: () => void;
  };
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          className="size-10 shrink-0 text-muted-foreground print:hidden"
          aria-label={`Actions for question ${number}`}
        >
          <Ellipsis aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuItem className="min-h-10" onSelect={on.edit}>
          <Pencil aria-hidden="true" />
          Edit
        </DropdownMenuItem>
        <DropdownMenuItem className="min-h-10" disabled={busy.regenerate} onSelect={on.regenerate}>
          <RefreshCw aria-hidden="true" />
          Regenerate
        </DropdownMenuItem>
        <DropdownMenuItem className="min-h-10" disabled={!canUp || busy.swap} onSelect={on.up}>
          <ArrowUp aria-hidden="true" />
          Move up
        </DropdownMenuItem>
        <DropdownMenuItem className="min-h-10" disabled={!canDown || busy.swap} onSelect={on.down}>
          <ArrowDown aria-hidden="true" />
          Move down
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="min-h-10"
          variant="destructive"
          disabled={busy.remove}
          onSelect={on.remove}
        >
          <Trash2 aria-hidden="true" />
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/**
 * One kit question: the text, one overflow menu for a recruiter, and a closed "Strong and weak
 * answers" disclosure (open in print). Answers are guidance for the interviewer, not a key.
 */
export function KitQuestionCard({
  question,
  number,
  neighbours,
  roleId,
  recruiter,
  open,
  onToggle,
  onJob,
}: {
  question: Question;
  number: number;
  neighbours: { prev: Question | null; next: Question | null };
  roleId: string;
  recruiter: boolean;
  open: boolean;
  onToggle: () => void;
  onJob: (id: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const remove = useDeleteQuestion(roleId);
  const swap = useSwap(roleId);
  const regenerate = useRegenerate();
  const failure = remove.error ?? swap.error ?? regenerate.error;
  const panel = useId();
  return (
    <motion.li layout="position" transition={{ duration: 0.2 }}>
      {editing ? (
        <QuestionForm
          question={question}
          roleId={roleId}
          onDone={() => {
            setEditing(false);
          }}
        />
      ) : (
        <Card className="gap-0 px-4 py-2">
          <div className="flex items-start gap-3">
            <span aria-hidden="true" className="w-6 pt-2.5 font-mono text-sm text-muted-foreground">
              {number}
            </span>
            <h3 className="min-w-0 flex-1 py-2.5 text-base leading-snug font-medium">
              {question.question_text}
            </h3>
            {recruiter && (
              <ActionsMenu
                number={number}
                canUp={neighbours.prev !== null}
                canDown={neighbours.next !== null}
                busy={{
                  swap: swap.isPending,
                  regenerate: regenerate.isPending,
                  remove: remove.isPending,
                }}
                on={{
                  edit: () => {
                    setEditing(true);
                  },
                  regenerate: () => {
                    regenerate.mutate(question.id, { onSuccess: onJob });
                  },
                  up: () => {
                    if (neighbours.prev) swap.mutate([question, neighbours.prev]);
                  },
                  down: () => {
                    if (neighbours.next) swap.mutate([question, neighbours.next]);
                  },
                  remove: () => {
                    remove.mutate(question.id);
                  },
                }}
              />
            )}
          </div>
          <div className="pl-9">
            <button
              type="button"
              aria-expanded={open}
              aria-controls={panel}
              onClick={onToggle}
              className="-ml-2 flex min-h-10 items-center gap-1.5 rounded-md px-2 text-sm text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 print:hidden"
            >
              <ChevronDown
                aria-hidden="true"
                className={cn("size-4 transition-transform", open && "rotate-180")}
              />
              Strong and weak answers
            </button>
            <motion.div
              id={panel}
              inert={!open}
              initial={false}
              animate={open ? { height: "auto", opacity: 1 } : { height: 0, opacity: 0 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              className="@container overflow-hidden print:h-auto! print:opacity-100!"
            >
              <div className="grid gap-3 pt-2 pb-1 @md:grid-cols-2">
                <div className="flex flex-col gap-1 rounded-md border bg-muted/50 p-3">
                  <p className="flex items-center gap-1.5 text-sm font-medium">
                    <Check aria-hidden="true" className="size-4" /> Strong answer
                  </p>
                  <p className="text-sm">{question.strong_answer}</p>
                </div>
                <div className="flex flex-col gap-1 rounded-md border border-dashed p-3">
                  <p className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                    <Minus aria-hidden="true" className="size-4" /> Weak answer
                  </p>
                  <p className="text-sm text-muted-foreground">{question.weak_answer}</p>
                </div>
              </div>
            </motion.div>
          </div>
          {failure && <ErrorNotice error={failure} />}
        </Card>
      )}
    </motion.li>
  );
}
