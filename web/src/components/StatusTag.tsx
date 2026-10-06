import type { ReactNode } from "react";

import { Icon } from "./Icon";

type Tone = "neutral" | "success" | "warning" | "danger" | "info";

const ICON = {
  neutral: "dash",
  success: "check",
  warning: "triangle",
  danger: "triangle",
  info: "eye",
} as const;

const TAG_CLASS: Record<Tone, string> = {
  neutral: "tag",
  success: "tag tag-success",
  warning: "tag tag-warning",
  danger: "tag tag-danger",
  info: "tag tag-info",
};

/** A state label: tone colour plus an icon and the text, so colour is never the only signal. */
export function StatusTag({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={TAG_CLASS[tone]}>
      <Icon name={ICON[tone]} />
      {children}
    </span>
  );
}
