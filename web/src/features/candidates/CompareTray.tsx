import { useNavigate } from "@tanstack/react-router";
import { AnimatePresence, motion } from "motion/react";

import { Button } from "@/components/ui/button";

import { trayState } from "./selection";

/** Sticky compare bar (Design.md 8.3): shows while any candidate is ticked, fixed to the viewport bottom. */
export function CompareTray({ ids, onClear }: { ids: string[]; onClear: () => void }) {
  const navigate = useNavigate();
  const { canCompare, hint } = trayState(ids.length);
  return (
    <AnimatePresence>
      {ids.length > 0 && (
        <motion.section
          aria-label="Compare selection"
          className="fixed inset-x-0 bottom-0 z-30 border-t bg-card print:hidden"
          initial={{ y: 24, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 24, opacity: 0 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
        >
          <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
            <p className="text-sm">
              <strong>{ids.length} selected</strong>
              <span className="text-muted-foreground"> {hint}</span>
            </p>
            <div className="ml-auto flex items-center gap-2">
              <Button type="button" variant="ghost" className="h-10 px-4" onClick={onClear}>
                Clear
              </Button>
              <Button
                type="button"
                className="h-10 px-4"
                disabled={!canCompare}
                onClick={() => {
                  void navigate({ to: "/compare", search: { ids: ids.join(",") } });
                }}
              >
                Compare
              </Button>
            </div>
          </div>
        </motion.section>
      )}
    </AnimatePresence>
  );
}
