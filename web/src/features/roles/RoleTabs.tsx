import { Link } from "@tanstack/react-router";

/** Role sub-navigation. The Candidates tab stays visible for a Draft role; its page explains the lock. */
export function RoleTabs({ roleId }: { roleId: string }) {
  return (
    <nav aria-label="Role" className="tabs">
      <Link to="/roles/$roleId" params={{ roleId }} activeOptions={{ exact: true }}>
        Criteria
      </Link>
      <Link to="/roles/$roleId/candidates" params={{ roleId }}>
        Candidates
      </Link>
    </nav>
  );
}
