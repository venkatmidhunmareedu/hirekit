import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";

import { ErrorNotice } from "../../components/ErrorNotice";

import { candidateLabel } from "./api";
import { myCandidatesQueryOptions } from "./hooks";

/** The interviewer's assigned candidates (US-00-014). Anonymized ids only. */
export function MyCandidatesPage() {
  const mine = useQuery(myCandidatesQueryOptions);
  return (
    <div className="stack">
      <h1>My candidates</h1>
      {mine.isPending && <p role="status">Loading your candidates</p>}
      {mine.isError && <ErrorNotice error={mine.error} />}
      {mine.data?.length === 0 && (
        <p className="muted">No candidates are assigned to you yet. A recruiter assigns them.</p>
      )}
      {mine.data && mine.data.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Candidate</th>
              <th scope="col">Role</th>
              <th scope="col">Your feedback</th>
            </tr>
          </thead>
          <tbody>
            {mine.data.map((c) => (
              <tr key={c.candidate_id}>
                <td className="mono">
                  <Link to="/candidates/$candidateId" params={{ candidateId: c.candidate_id }}>
                    {candidateLabel(c.candidate_no)}
                  </Link>
                </td>
                <td>{c.role_title}</td>
                <td>{c.has_submitted ? "Submitted" : "Not submitted"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
