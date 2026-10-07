import { ChevronDown, LogOut, MessageSquare, ShieldCheck } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { initials } from "./crumbs";

interface Person {
  name: string;
  email: string;
  role: string;
}

const ROLE_VIEW = {
  recruiter: { label: "Recruiter", Icon: ShieldCheck },
  interviewer: { label: "Interviewer", Icon: MessageSquare },
} as const;

export function RoleBadge({ role }: { role: string }) {
  const view = role === "interviewer" ? ROLE_VIEW.interviewer : ROLE_VIEW.recruiter;
  return (
    <Badge variant="secondary" className="h-6 rounded-full px-2.5">
      <view.Icon aria-hidden="true" />
      {view.label}
    </Badge>
  );
}

/** Initials, name and role in one menu with Sign out. The name stays in the DOM on narrow screens for assistive tech. */
export function UserMenu({
  user,
  signingOut,
  onSignOut,
}: {
  user: Person;
  signingOut: boolean;
  onSignOut: () => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button type="button" variant="ghost" className="h-10 gap-2 px-2">
          <Avatar size="sm">
            <AvatarFallback className="bg-accent text-xs font-semibold text-accent-foreground">
              {initials(user.name)}
            </AvatarFallback>
          </Avatar>
          <span className="max-w-32 truncate text-sm font-medium max-sm:sr-only">{user.name}</span>
          <ChevronDown aria-hidden="true" className="text-muted-foreground max-sm:hidden" />
          <span className="sr-only">Account menu</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="flex flex-col gap-1.5 py-2 font-normal">
          <span className="truncate text-sm font-semibold text-foreground">{user.name}</span>
          <span className="truncate text-xs text-muted-foreground">{user.email}</span>
          <RoleBadge role={user.role} />
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="h-10"
          disabled={signingOut}
          onSelect={() => {
            onSignOut();
          }}
        >
          <LogOut aria-hidden="true" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
