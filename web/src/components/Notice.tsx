import { CircleAlert, CircleCheck, Info, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { cn } from "@/lib/utils";

type Tone = "info" | "warning" | "success" | "danger";

const TONE = {
  info: { icon: Info, box: "border-note bg-note-soft", glyph: "text-note" },
  warning: { icon: TriangleAlert, box: "border-warn bg-warn-soft", glyph: "text-warn" },
  success: { icon: CircleCheck, box: "border-ok bg-ok-soft", glyph: "text-ok" },
  danger: { icon: CircleAlert, box: "border-bad bg-bad-soft", glyph: "text-bad" },
} as const;

/**
 * A state message: tone tint, an icon and the words, so colour is never the only signal.
 * Danger is announced as an alert; the other tones are polite status text. The body keeps
 * the foreground colour for contrast; an optional action sits beside it.
 */
export function Notice({
  tone = "info",
  role,
  action,
  children,
}: {
  tone?: Tone;
  role?: "alert" | "status";
  action?: ReactNode;
  children: ReactNode;
}) {
  const { icon: ToneIcon, box, glyph } = TONE[tone];
  return (
    <Alert
      role={role ?? (tone === "danger" ? "alert" : "status")}
      className={cn("flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2.5", box)}
    >
      <ToneIcon aria-hidden="true" className={cn("size-4 shrink-0", glyph)} />
      <AlertDescription className="min-w-0 flex-1 text-foreground">{children}</AlertDescription>
      {action}
    </Alert>
  );
}
