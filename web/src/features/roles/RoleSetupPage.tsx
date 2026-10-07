import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

import { ErrorNotice } from "../../components/ErrorNotice";
import { Loading } from "../../components/Loading";
import { Notice } from "../../components/Notice";
import { Section } from "../../components/Section";

import { CriteriaEditor } from "./CriteriaEditor";
import { RoleHeader } from "./RoleHeader";
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
    <div className="flex flex-col gap-6">
      <RoleHeader role={role.data} current="criteria" />
      <div className="grid items-start gap-6 lg:grid-cols-3">
        <details open className="rounded-lg border bg-card p-4 lg:sticky lg:top-20">
          <summary className="cursor-pointer text-base font-semibold">Job description</summary>
          <p className="mt-3 max-w-prose text-sm whitespace-pre-line">
            {role.data.job_description}
          </p>
        </details>
        <div className="flex flex-col gap-8 lg:col-span-2">
          <Proposal role={role.data} />
          <CriteriaEditor
            key={`${role.data.criteria_version}:${role.data.updated_at}:${JSON.stringify(role.data.criteria)}`}
            role={role.data}
          />
        </div>
      </div>
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
      description="The AI suggests criteria from the job description. Edit them, then approve."
    >
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant={role.criteria.length === 0 ? "default" : "outline"}
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
