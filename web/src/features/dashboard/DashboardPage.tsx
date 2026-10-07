import { useSuspenseQuery } from "@tanstack/react-query";

import { sessionQueryOptions } from "../auth/hooks";

import { InterviewerDashboard } from "./InterviewerDashboard";
import { RecruiterDashboard } from "./RecruiterDashboard";

/** "/" for both roles: each sees their own overview. Neither role is redirected. */
export function DashboardPage() {
  const { data: session } = useSuspenseQuery(sessionQueryOptions);
  return session.user.role === "recruiter" ? <RecruiterDashboard /> : <InterviewerDashboard />;
}
