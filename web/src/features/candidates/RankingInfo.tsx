import { Info, X } from "lucide-react";
import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

const RULE =
  "Scores are AI suggestions. Hiding names reduces some bias but does not remove it: schools, clubs, wording and career gaps can still show.";
const SCOPE = "The stage filter covers every candidate; the checkboxes cover this page.";

/**
 * The note under Ranked candidates: the anonymization rule and the filter scope. It can be put
 * away for this visit, but then it stays one click away behind an info button, so the rule is
 * never gone (Design.md section 9).
 */
export function RankingInfo() {
  const [open, setOpen] = useState(true);
  if (open) {
    return (
      <Alert
        role="status"
        className="flex items-center gap-3 border-note bg-note-soft py-0.5 pr-1 pl-3"
      >
        <Info aria-hidden="true" className="size-4 shrink-0 text-note" />
        <AlertDescription className="min-w-0 flex-1 font-medium text-foreground">
          {RULE}
        </AlertDescription>
        <Button
          type="button"
          variant="ghost"
          className="h-10 px-3"
          onClick={() => {
            setOpen(false);
          }}
        >
          <X aria-hidden="true" />
          Hide note
        </Button>
      </Alert>
    );
  }
  return (
    <div>
      <Popover>
        <PopoverTrigger asChild>
          <Button type="button" variant="outline" className="h-10 px-3">
            <Info aria-hidden="true" className="text-note" />
            About these scores
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-80 text-sm">
          <p className="font-medium">{RULE}</p>
          <p className="mt-2 text-muted-foreground">{SCOPE}</p>
        </PopoverContent>
      </Popover>
    </div>
  );
}
