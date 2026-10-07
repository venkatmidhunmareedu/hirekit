import { useNavigate, useSearch } from "@tanstack/react-router";
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp } from "lucide-react";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";

import { useMediaQuery } from "../../lib/useMediaQuery";

import { ReviewPane } from "./CandidateDetailPage";
import { type Entry, RankedList } from "./RankedList";
import { type RankedPage, candidateLabel } from "./api";
import { PAGE_SIZE } from "./api";
import { isTypingTarget, step } from "./selection";

export const WIDE = "(min-width: 1024px)";

/**
 * Review mode (Design.md 8.3): the ranked list beside the open candidate. The open candidate is
 * the `c` search param, so reload and back work; below lg a row opens the candidate page instead.
 */
export function ReviewWorkspace({
  roleId,
  page,
  entries,
  selected,
  onToggle,
  onOffset,
}: {
  roleId: string;
  page: RankedPage;
  entries: Entry[];
  selected: string[];
  onToggle: (id: string) => void;
  onOffset: (offset: number) => void;
}) {
  const wide = useMediaQuery(WIDE);
  const navigate = useNavigate();
  const { c } = useSearch({ strict: false });
  const paneRef = useRef<HTMLDivElement>(null);

  const ids = entries.map((e) => e.candidate.id);
  const activeId = wide ? (c ?? ids[0] ?? null) : null;
  const position = activeId === null ? -1 : ids.indexOf(activeId);
  const active = position === -1 ? undefined : entries[position];

  const open = (id: string, replace: boolean) => {
    void navigate({
      to: "/roles/$roleId/candidates",
      params: { roleId },
      search: { c: id },
      replace,
    });
  };

  // j and k: a keyboard shortcut is a subscription to the document, which is what effects are for.
  const idsKey = ids.join(",");
  useEffect(() => {
    if (!wide) return;
    const list = idsKey === "" ? [] : idsKey.split(",");
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key !== "j" && event.key !== "k") return;
      if (isTypingTarget(event.target)) return;
      const id = step(list, c ?? list[0] ?? null, event.key === "j" ? 1 : -1);
      if (id !== null) {
        void navigate({
          to: "/roles/$roleId/candidates",
          params: { roleId },
          search: { c: id },
          replace: true,
        });
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
    };
  }, [wide, idsKey, c, navigate, roleId]);

  // Keep the open row visible in the list, and the pane's top in view after a move.
  useEffect(() => {
    if (activeId === null) return;
    document.getElementById(`row-${activeId}`)?.scrollIntoView({ block: "nearest" });
    const pane = paneRef.current;
    if (pane && pane.getBoundingClientRect().top < 0) pane.scrollIntoView({ block: "start" });
  }, [activeId]);

  const moveFocus = (delta: 1 | -1, from: HTMLElement) => {
    const id = step(ids, from.closest("li")?.id.replace("row-", "") ?? null, delta);
    if (id === null) return;
    open(id, true);
    document.getElementById(`row-${id}`)?.querySelector<HTMLElement>("[data-row]")?.focus();
  };

  const last = page.offset + page.data.length;
  const more = last < page.total;
  const before = position > 0 ? entries[position - 1] : undefined;
  const after = position >= 0 ? entries[position + 1] : undefined;

  const controls = active && (
    <div className="flex flex-col items-end gap-1">
      <div className="flex items-center gap-2">
        <span className="mr-1 text-xs text-muted-foreground tabular-nums">
          {position + 1} of {entries.length} on this page
        </span>
        <Button
          type="button"
          variant="outline"
          className="h-10 px-3"
          aria-label="Previous candidate"
          disabled={!before}
          onClick={() => {
            if (before) open(before.candidate.id, true);
          }}
        >
          <ChevronUp aria-hidden="true" />
          Previous
        </Button>
        <Button
          type="button"
          variant="outline"
          className="h-10 px-3"
          aria-label="Next candidate"
          disabled={!after}
          onClick={() => {
            if (after) open(after.candidate.id, true);
          }}
        >
          <ChevronDown aria-hidden="true" />
          Next
        </Button>
      </div>
      {!after && more && (
        <p className="text-xs text-muted-foreground">
          This is the last one loaded. Use Next page under the list to continue.
        </p>
      )}
    </div>
  );

  return (
    <div className="grid gap-6 lg:grid-cols-12">
      <div className="flex flex-col overflow-hidden rounded-lg border bg-card lg:sticky lg:top-20 lg:col-span-4 lg:review-rail lg:self-start xl:col-span-3">
        <RankedList
          entries={entries}
          activeId={activeId}
          selected={selected}
          onToggle={onToggle}
          onOpen={
            wide
              ? (id) => {
                  open(id, false);
                }
              : null
          }
          onArrow={moveFocus}
        />
        <nav
          aria-label="Pages"
          className="flex items-center justify-between gap-2 border-t px-2 py-2"
        >
          <Button
            type="button"
            variant="outline"
            className="h-10 px-3"
            aria-label="Previous page"
            disabled={page.offset === 0}
            onClick={() => {
              onOffset(Math.max(0, page.offset - PAGE_SIZE));
            }}
          >
            <ChevronLeft aria-hidden="true" />
            Prev
          </Button>
          <span className="text-xs text-muted-foreground">
            {page.data.length === 0 ? 0 : page.offset + 1} to {last} of {page.total}
          </span>
          <Button
            type="button"
            variant="outline"
            className="h-10 px-3"
            aria-label="Next page"
            disabled={!more}
            onClick={() => {
              onOffset(page.offset + PAGE_SIZE);
            }}
          >
            Next
            <ChevronRight aria-hidden="true" />
          </Button>
        </nav>
      </div>
      {wide && (
        <div
          ref={paneRef}
          aria-label="Open candidate"
          role="region"
          className="min-w-0 scroll-mt-20 lg:col-span-8 xl:col-span-9"
        >
          <p role="status" className="sr-only">
            {active
              ? `Showing ${candidateLabel(active.candidate.candidate_no)}, ${position + 1} of ${entries.length}`
              : ""}
          </p>
          {active ? (
            <ReviewPane
              candidateId={active.candidate.id}
              summary={active.candidate}
              controls={controls}
            />
          ) : (
            c !== undefined && <ReviewPane candidateId={c} summary={undefined} controls={null} />
          )}
        </div>
      )}
    </div>
  );
}
