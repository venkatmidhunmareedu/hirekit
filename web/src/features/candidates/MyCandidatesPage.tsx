import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";

import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Loading } from "../../components/Loading";
import { PageHeader } from "../../components/PageHeader";
import { StatusTag } from "../../components/StatusTag";

import { candidateLabel } from "./api";
import { myCandidatesQueryOptions } from "./hooks";

/** The interviewer's assigned candidates (US-00-014). Anonymized ids only. */
export function MyCandidatesPage() {
  const mine = useQuery(myCandidatesQueryOptions);
  return (
    <div className="stack">
      <PageHeader title="My candidates" />
      {mine.isPending && <Loading label="Loading your candidates" />}
      {mine.isError && (
        <ErrorNotice
          error={mine.error}
          retry={() => {
            void mine.refetch();
          }}
        />
      )}
      {mine.data?.length === 0 && (
        <EmptyState message="No candidates are assigned to you yet. A recruiter assigns them." />
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
                <td>
                  <StatusTag tone={c.has_submitted ? "success" : "neutral"}>
                    {c.has_submitted ? "Submitted" : "Not submitted"}
                  </StatusTag>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
