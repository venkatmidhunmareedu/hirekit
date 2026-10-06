import { LoaderCircle } from "lucide-react";

/** A polite status with a spinner; the text names what is loading. */
export function Loading({ label }: { label: string }) {
  return (
    <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
      <LoaderCircle aria-hidden="true" className="size-4 animate-spin motion-reduce:animate-none" />
      <span>{label}</span>
    </p>
  );
}
