import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { useState } from "react";

import { AlertIcon } from "../../components/AlertIcon";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Loading } from "../../components/Loading";
import { PageHeader } from "../../components/PageHeader";

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

  if (role.isPending) return <Loading label="Loading role" />;
  if (role.isError) {
    return (
      <ErrorNotice
        error={role.error}
        retry={() => {
          void role.refetch();
        }}
      />
    );
  }
  return (
    <div className="stack">
      <PageHeader title={role.data.title} />
      <RoleTabs roleId={roleId} status={role.data.status} current="criteria" />
      <section className="section">
        <h2>Job description</h2>
        <p className="job-description">{role.data.job_description}</p>
      </section>
      {role.data.status === "draft" ? (
        <p className="notice notice-info" role="status">
          Draft. Approve the criteria to start uploading and scoring resumes.
        </p>
      ) : (
        <div className="notice notice-info" role="status">
          <span>Approved. You can upload resumes on the Candidates step.</span>
          <Link to="/roles/$roleId/candidates" params={{ roleId }} className="btn btn-primary">
            Next: upload resumes
          </Link>
        </div>
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
    <section className="section">
      <h2>Proposed criteria</h2>
      <p className="muted">
        The AI suggests criteria from the job description. Review and edit every one before you
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
      {failure && <ErrorNotice error={failure} />}
    </section>
  );
}
