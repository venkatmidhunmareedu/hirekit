import { Monitor, Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";
import { type Theme, useTheme } from "@/lib/theme";

export const THEMES = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "dark", label: "Dark", Icon: Moon },
  { value: "system", label: "System", Icon: Monitor },
] as const satisfies readonly { value: Theme; label: string; Icon: typeof Sun }[];

/** Light, Dark or System as a compact segmented control. */
export function ThemeToggle() {
  const [theme, setTheme] = useTheme();
  return (
    <div role="group" aria-label="Theme" className="inline-flex gap-1 rounded-lg border p-1">
      {THEMES.map(({ value, label, Icon }) => (
        <Button
          key={value}
          type="button"
          size="sm"
          variant={theme === value ? "secondary" : "ghost"}
          aria-pressed={theme === value}
          onClick={() => {
            setTheme(value);
          }}
        >
          <Icon aria-hidden="true" />
          <span className="max-sm:sr-only">{label}</span>
        </Button>
      ))}
    </div>
  );
}
