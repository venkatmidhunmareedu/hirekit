import { useMediaQuery } from "@/lib/useMediaQuery";

/** The shadcn sidebar asks this; it reuses the project's media query hook so no effect sets state. */
export function useIsMobile(): boolean {
  return useMediaQuery("(max-width: 767px)");
}
