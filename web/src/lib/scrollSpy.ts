import { type RefObject, useEffect, useRef, useState } from "react";

/** After a click the page scrolls through other sections; their reports are ignored this long (ms). */
const CLICK_LOCK_MS = 700;

/** Smooth scrolling unless the person asked for less motion. */
export function scrollBehavior(): ScrollBehavior {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
}

/**
 * Scroll a region (not the page) so `target` sits in its middle. scrollIntoView would also move
 * the page; this moves only the region's own scrollTop. `inset` keeps a start-aligned target
 * clear of something sticky at the top of the region.
 */
export function revealIn(
  region: HTMLElement,
  target: HTMLElement,
  block: "center" | "start" = "center",
  inset = 0,
) {
  const box = target.getBoundingClientRect();
  const offset = box.top - region.getBoundingClientRect().top;
  const lead = block === "center" ? (region.clientHeight - box.height) / 2 : inset;
  region.scrollTo({ top: region.scrollTop + offset - lead, behavior: scrollBehavior() });
}

/**
 * Which of the sections `ids` is in view. Returns the active id and a setter for a click, so the
 * navigator highlights at once instead of waiting for the scroll to finish. Pass `rootRef` with
 * `scoped` when the sections scroll inside a region of their own; otherwise the page is the root.
 */
export function useScrollSpy(
  ids: string[],
  options: { rootRef?: RefObject<Element | null>; scoped?: boolean; rootMargin?: string } = {},
): [string | null, (id: string) => void] {
  const { rootRef, scoped = false, rootMargin = "0px 0px -60% 0px" } = options;
  const [seen, setSeen] = useState<string | null>(null);
  const lockedUntil = useRef(0);
  const key = ids.join("|");

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined" || key === "") return;
    const order = key.split("|");
    const inView = new Set<string>();
    const observer = new IntersectionObserver(
      (entries) => {
        let aboveAll = false;
        for (const entry of entries) {
          if (entry.isIntersecting) inView.add(entry.target.id);
          else inView.delete(entry.target.id);
          // The first section dropped below the viewing band: the reader is above every section.
          if (entry.target.id === order[0] && !entry.isIntersecting) {
            aboveAll = entry.boundingClientRect.top > 0;
          }
        }
        if (performance.now() < lockedUntil.current) return;
        const first = order.find((id) => inView.has(id)) ?? (aboveAll ? order[0] : undefined);
        if (first !== undefined) setSeen(first);
      },
      { root: scoped ? (rootRef?.current ?? null) : null, rootMargin },
    );
    for (const id of order) {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    }
    return () => {
      observer.disconnect();
    };
  }, [key, rootRef, scoped, rootMargin]);

  const active = seen !== null && ids.includes(seen) ? seen : (ids[0] ?? null);
  const choose = (id: string) => {
    lockedUntil.current = performance.now() + CLICK_LOCK_MS;
    setSeen(id);
  };
  return [active, choose];
}
