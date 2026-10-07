import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import { Loader2, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { Markdown } from "@/components/RichText";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";

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
          <Markdown value={role.data.job_description} className="mt-3 max-w-prose" />
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

/** Plain, time based wording: the API reports no steps, so none are claimed. */
function phaseText(seconds: number): string {
  if (seconds >= 30) return "Still working, this can take a minute";
  if (seconds >= 6) return "Drafting criteria";
  return "Reading your job description";
}

/** Mounted only while a proposal runs, so mounting starts the clock. */
function ProgressCard({
  onCancel,
  cancelling,
}: {
  onCancel?: (() => void) | undefined;
  cancelling: boolean;
}) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => {
      setSeconds((n) => n + 1);
    }, 1000);
    return () => {
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-card p-4">
      <div className="flex items-start gap-3">
        <Loader2
          aria-hidden="true"
          className="mt-0.5 size-5 shrink-0 animate-spin text-primary motion-reduce:animate-none"
        />
        <div className="min-w-0 flex-1">
          <p role="status" className="font-medium">
            {phaseText(seconds)}
          </p>
          <p className="text-sm text-muted-foreground">Working for {seconds}s</p>
        </div>
        {onCancel && (
          <Button
            type="button"
            variant="outline"
            className="h-10 px-4"
            disabled={cancelling}
            onClick={onCancel}
          >
            Cancel
          </Button>
        )}
      </div>
      <div aria-hidden="true" className="h-1.5 overflow-hidden rounded-full bg-primary/15">
        <div className="h-full progress-slide w-1/4 rounded-full bg-primary" />
      </div>
    </div>
  );
}

/** Ask the model for criteria, with progress and a cancel option (Design.md 8.2 step 2). */
function Proposal({ role }: { role: RoleDetail }) {
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<number | null>(null);
  const [confirming, setConfirming] = useState(false);
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
  const running = propose.isPending || openJob !== null;
  const hasCriteria = role.criteria.length > 0;
  const start = () => {
    propose.mutate(undefined, { onSuccess: setJobId });
  };

  const card = (
    <ProgressCard
      cancelling={cancel.isPending}
      onCancel={
        openJob === null
          ? undefined
          : () => {
              cancel.mutate(openJob);
            }
      }
    />
  );

  return (
    <Section
      id="proposed-criteria"
      title="Proposed criteria"
      hideTitle={hasCriteria}
      description={
        hasCriteria
          ? undefined
          : "The AI suggests criteria from the job description. Edit them, then approve."
      }
    >
      {running ? (
        card
      ) : hasCriteria ? (
        role.status === "draft" && (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              Suggested by the AI from the job description. Edit, then approve.
            </p>
            <Button
              type="button"
              variant="outline"
              className="h-10 px-4"
              onClick={() => {
                setConfirming(true);
              }}
            >
              <RefreshCw aria-hidden="true" className="size-4" />
              Regenerate
            </Button>
          </div>
        )
      ) : (
        <div>
          <Button type="button" className="h-10 px-4" onClick={start}>
            Propose criteria
          </Button>
        </div>
      )}
      {running && !hasCriteria && (
        <div aria-hidden="true" className="flex flex-col gap-3">
          {[0, 1, 2].map((n) => (
            <Skeleton key={n} className="h-16" />
          ))}
        </div>
      )}
      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Regenerate criteria?</DialogTitle>
            <DialogDescription>
              This replaces the current criteria, including edits you have not saved. The old ones
              cannot be brought back.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              className="h-10 px-4"
              onClick={() => {
                setConfirming(false);
              }}
            >
              Cancel
            </Button>
            <Button
              type="button"
              className="h-10 px-4"
              disabled={propose.isPending}
              onClick={() => {
                setConfirming(false);
                start();
              }}
            >
              Regenerate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {status === "failed" && (
        <Notice tone="danger">
          The proposal did not finish. Try again, or add criteria by hand.
          {!running && (
            <>
              {" "}
              <Button type="button" variant="outline" className="ml-2 h-8 px-3" onClick={start}>
                Try again
              </Button>
            </>
          )}
        </Notice>
      )}
      {status === "succeeded" && (
        <p role="status" className="sr-only">
          Criteria proposed
        </p>
      )}
      {status === "cancelled" && <p role="status">Proposal cancelled.</p>}
      {failure && <ErrorNotice error={failure} />}
    </Section>
  );
}
