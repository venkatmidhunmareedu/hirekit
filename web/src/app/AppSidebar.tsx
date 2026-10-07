import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { motion } from "motion/react";
import { Briefcase, ClipboardList, LayoutDashboard, type LucideIcon } from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";

import { Logo } from "../components/Logo";
import { rolesQueryOptions } from "../features/roles/hooks";

/** The active item's mark. A shared layoutId makes it slide from the old item to the new one. */
function ActiveMark() {
  return (
    <motion.span
      layoutId="nav-active"
      aria-hidden="true"
      transition={{ duration: 0.2, ease: "easeOut" }}
      className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-sidebar-primary"
    />
  );
}

const ITEM =
  "relative h-10 aria-[current=page]:bg-sidebar-accent aria-[current=page]:font-medium aria-[current=page]:text-sidebar-accent-foreground";

function NavLink({
  to,
  label,
  Icon,
}: {
  to: "/" | "/roles" | "/me/candidates";
  label: string;
  Icon: LucideIcon;
}) {
  const { isMobile, setOpenMobile } = useSidebar();
  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        asChild
        tooltip={label}
        className={ITEM}
        onClick={() => {
          if (isMobile) setOpenMobile(false);
        }}
      >
        <Link to={to} activeOptions={{ exact: true }}>
          {({ isActive }) => (
            <>
              {isActive && <ActiveMark />}
              <Icon aria-hidden="true" />
              <span>{label}</span>
            </>
          )}
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}

/** Recent roles: up to five, each opening its candidates (approved) or its criteria (draft). Recruiters only. */
function RecentRoles() {
  const roles = useQuery(rolesQueryOptions);
  const { isMobile, setOpenMobile } = useSidebar();
  const recent = roles.data?.slice(0, 5) ?? [];
  if (recent.length === 0) return null;
  const close = () => {
    if (isMobile) setOpenMobile(false);
  };
  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel>Recent roles</SidebarGroupLabel>
      <SidebarMenu>
        {recent.map((role) => (
          <SidebarMenuItem key={role.id}>
            <SidebarMenuButton asChild className={ITEM} onClick={close}>
              {role.status === "approved" ? (
                <Link to="/roles/$roleId/candidates" params={{ roleId: role.id }}>
                  {({ isActive }) => (
                    <>
                      {isActive && <ActiveMark />}
                      <span>{role.title}</span>
                    </>
                  )}
                </Link>
              ) : (
                <Link
                  to="/roles/$roleId"
                  params={{ roleId: role.id }}
                  activeOptions={{ exact: true }}
                >
                  {({ isActive }) => (
                    <>
                      {isActive && <ActiveMark />}
                      <span>{role.title}</span>
                    </>
                  )}
                </Link>
              )}
            </SidebarMenuButton>
            {role.status === "draft" && (
              <SidebarMenuBadge className="top-2.5 right-2">Draft</SidebarMenuBadge>
            )}
          </SidebarMenuItem>
        ))}
      </SidebarMenu>
    </SidebarGroup>
  );
}

/** Primary navigation (Design.md 5): a collapsible rail on desktop, a sheet on mobile. */
export function AppSidebar({ recruiter }: { recruiter: boolean }) {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="h-14 justify-center border-b px-3">
        <Link
          to="/"
          aria-label="HireKit, Dashboard"
          className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
        >
          <Logo wordmarkClassName="group-data-[collapsible=icon]:hidden" />
        </Link>
      </SidebarHeader>
      <SidebarContent>
        <nav aria-label="Main" className="flex flex-col">
          <SidebarGroup>
            <SidebarMenu className="gap-1">
              <NavLink to="/" label="Dashboard" Icon={LayoutDashboard} />
              {recruiter ? (
                <NavLink to="/roles" label="Roles" Icon={Briefcase} />
              ) : (
                <NavLink to="/me/candidates" label="My candidates" Icon={ClipboardList} />
              )}
            </SidebarMenu>
          </SidebarGroup>
          {recruiter && <RecentRoles />}
        </nav>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  );
}
