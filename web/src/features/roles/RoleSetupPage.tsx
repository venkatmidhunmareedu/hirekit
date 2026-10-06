import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import { useState } from "react";

import { AlertIcon } from "../../components/AlertIcon";
import { errorMessage } from "../../lib/errors";

import { CriteriaEditor } from "./CriteriaEditor";
import { RoleTabs } from "./RoleTabs";
import type { RoleDetail } from "./api";
import {
  jobQueryOptions,
  roleKeys,
  roleQueryOptions,
  useCancelJob,
  useProposeCriteria,
} from "./hooks";

/** Role setup and criteria approval (Design.md 8.2, PRD step 1). */
export function RoleSetupPage() {
  const { roleId } = useParams({ strict: false });
  if (roleId === undefined) throw new Error("route has no roleId");
  return <RoleSetup key={roleId} roleId={roleId} />;
}

function RoleSetup({ roleId }: { roleId: string }) {
  const role = useQuery(roleQueryOptions(roleId));

  if (role.isPending) return <p role="status">Loading role</p>;
  if (role.isError) {
    return (
      <p role="alert" className="notice notice-danger">
        <AlertIcon />
        <span>{errorMessage(role.error)}</span>
        <button type="button" className="btn btn-secondary" onClick={() => void role.refetch()}>
          Try again
        </button>
      </p>
    );
  }
  return (
    <div className="stack">
      <h1>{role.data.title}</h1>
      <RoleTabs roleId={roleId} />
      <div className="card stack">
        <h2>Job description</h2>
        <p className="job-description">{role.data.job_description}</p>
      </div>
      {role.data.status === "draft" ? (
        <p className="notice notice-info" role="status">
          Draft. Approve the criteria to start uploading and scoring resumes.
        </p>
      ) : (
        <p className="notice notice-info" role="status">
          Approved. You can upload resumes on the Candidates tab.
        </p>
      )}
      <Proposal role={role.data} />
      <CriteriaEditor
        key={`${role.data.criteria_version}:${role.data.updated_at}:${JSON.stringify(role.data.criteria)}`}
        role={role.data}
      />
    </div>
  );
}

/** Ask the model for criteria, with progress and a cancel option (Design.md 8.2 step 2). */
function Proposal({ role }: { role: RoleDetail }) {
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<number | null>(null);
  const propose = useProposeCriteria(role.id);
  const cancel = useCancelJob();
  const job = useQuery({
    ...jobQueryOptions(jobId ?? 0, () => {
      void queryClient.invalidateQueries({ queryKey: roleKeys.detail(role.id) });
    }),
    enabled: jobId !== null,
  });
  const failure = propose.error ?? cancel.error ?? job.error;
  const status = job.data?.status;
  const openJob =
    jobId !== null && (status === undefined || status === "queued" || status === "running")
      ? jobId
      : null;

  return (
    <div className="card stack">
      <h2>Proposed criteria</h2>
      <p className="muted">
        The model suggests criteria from the job description. Review and edit every one before you
        approve.
      </p>
      <div className="actions">
        <button
          type="button"
          className="btn btn-secondary"
          disabled={propose.isPending || openJob !== null}
          onClick={() => {
            propose.mutate(undefined, { onSuccess: setJobId });
          }}
        >
          Propose criteria
        </button>
        {openJob !== null && (
          <button
            type="button"
            className="btn btn-secondary"
            disabled={cancel.isPending}
            onClick={() => {
              cancel.mutate(openJob);
            }}
          >
            Cancel
          </button>
        )}
      </div>
      {openJob !== null && <progress aria-label="Proposing criteria" />}
      {status === "failed" && (
        <p role="alert" className="notice notice-danger">
          <AlertIcon />
          <span>The proposal did not finish. Try again, or add criteria by hand.</span>
        </p>
      )}
      {status === "succeeded" && <p role="status">Proposed criteria are below.</p>}
      {status === "cancelled" && <p role="status">Proposal cancelled.</p>}
      {failure && (
        <p role="alert" className="notice notice-danger">
          <AlertIcon />
          <span>{errorMessage(failure)}</span>
        </p>
      )}
    </div>
  );
}
