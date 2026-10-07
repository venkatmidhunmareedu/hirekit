import { Check, CircleDashed, Info, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type Tone = "neutral" | "success" | "warning" | "danger" | "info";

const TONE: Record<Tone, { icon: typeof Check; className: string }> = {
  neutral: { icon: CircleDashed, className: "bg-muted text-muted-foreground" },
  success: { icon: Check, className: "bg-ok-soft text-ok" },
  warning: { icon: TriangleAlert, className: "bg-warn-soft text-warn" },
  danger: { icon: TriangleAlert, className: "bg-bad-soft text-bad" },
  info: { icon: Info, className: "bg-note-soft text-note" },
};

/** A state label: tone colour plus an icon and the text, so colour is never the only signal. */
export function StatusTag({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  const { icon: ToneIcon, className } = TONE[tone];
  return (
    <Badge
      variant="secondary"
      className={cn("h-6 rounded-full px-2.5 text-xs font-medium", className)}
    >
      <ToneIcon aria-hidden="true" />
      {children}
    </Badge>
  );
}
