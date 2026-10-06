import { CircleAlert } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

import { errorMessage } from "../lib/errors";

/** A visible, announced error with an icon (Design.md section 11: plain message, next step). */
export function ErrorNotice({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <Alert variant="destructive" className="flex items-center gap-3 border-bad bg-bad-soft">
      <CircleAlert aria-hidden="true" className="size-4 shrink-0" />
      <AlertDescription className="flex-1 text-bad">{errorMessage(error)}</AlertDescription>
      {retry && (
        <Button type="button" variant="outline" size="sm" onClick={retry}>
          Try again
        </Button>
      )}
    </Alert>
  );
}
