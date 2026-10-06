import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

import { ErrorNotice } from "../../components/ErrorNotice";
import { Loading } from "../../components/Loading";
import { Notice } from "../../components/Notice";
import { PageHeader } from "../../components/PageHeader";
import { Section } from "../../components/Section";

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
    <div className="flex flex-col gap-8">
      <PageHeader title={role.data.title} />
      <RoleTabs roleId={roleId} status={role.data.status} current="criteria" />
      <Section id="job-description" title="Job description">
        <p className="max-w-prose whitespace-pre-line">{role.data.job_description}</p>
      </Section>
      {role.data.status === "draft" ? (
        <Notice>Draft. Approve the criteria to start uploading and scoring resumes.</Notice>
      ) : (
        <Notice
          action={
            <Button asChild className="h-10 px-4">
              <Link to="/roles/$roleId/candidates" params={{ roleId }}>
                Next: upload resumes
              </Link>
            </Button>
          }
        >
          Approved. You can upload resumes on the Candidates step.
        </Notice>
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
    <Section
      id="proposed-criteria"
      title="Proposed criteria"
      description="The AI suggests criteria from the job description. Review and edit every one before you approve."
    >
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          className="h-10 px-4"
          disabled={propose.isPending || openJob !== null}
          onClick={() => {
            propose.mutate(undefined, { onSuccess: setJobId });
          }}
        >
          Propose criteria
        </Button>
        {openJob !== null && (
          <Button
            type="button"
            variant="outline"
            className="h-10 px-4"
            disabled={cancel.isPending}
            onClick={() => {
              cancel.mutate(openJob);
            }}
          >
            Cancel
          </Button>
        )}
      </div>
      {openJob !== null && (
        <Progress
          aria-label="Proposing criteria"
          value={null}
          className="h-2 animate-pulse bg-primary/30 motion-reduce:animate-none"
        />
      )}
      {status === "failed" && (
        <Notice tone="danger">
          The proposal did not finish. Try again, or add criteria by hand.
        </Notice>
      )}
      {status === "succeeded" && <p role="status">Proposed criteria are below.</p>}
      {status === "cancelled" && <p role="status">Proposal cancelled.</p>}
      {failure && <ErrorNotice error={failure} />}
    </Section>
  );
}
