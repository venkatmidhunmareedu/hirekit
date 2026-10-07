import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { useState, type SubmitEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Loading } from "../../components/Loading";
import { PageHeader } from "../../components/PageHeader";
import { StatusTag } from "../../components/StatusTag";

import { nextUp } from "./nextUp";
import { rolesQueryOptions, useCreateRole } from "./hooks";

/** Role list (Design.md 8.1) with the new-role form: title and job description (PRD step 1). */
export function RolesPage() {
  const roles = useQuery(rolesQueryOptions);
  const [creating, setCreating] = useState(false);

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Roles"
        purpose="Each role has its own criteria, candidates and interview kit."
        action={
          <Button
            type="button"
            size="lg"
            className="h-10 px-4"
            onClick={() => {
              setCreating(true);
            }}
          >
            New role
          </Button>
        }
      />
      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold">New role</DialogTitle>
            <DialogDescription>
              Paste the job description. You can ask for proposed criteria on the next screen.
            </DialogDescription>
          </DialogHeader>
          <NewRoleForm
            onCancel={() => {
              setCreating(false);
            }}
          />
        </DialogContent>
      </Dialog>
      <section aria-labelledby="your-roles" className="flex flex-col gap-4">
        <h2 id="your-roles">Your roles</h2>
        {roles.isPending && <Loading label="Loading roles" />}
        {roles.isError && (
          <ErrorNotice
            error={roles.error}
            retry={() => {
              void roles.refetch();
            }}
          />
        )}
        {roles.data?.length === 0 && (
          <EmptyState message="No roles yet. Choose New role to add one and set its criteria." />
        )}
        {roles.data && roles.data.length > 0 && (
          <ul className="flex flex-col gap-3">
            {roles.data.map((role) => (
              <li key={role.id}>
                <Card className="flex-row flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4">
                  <Link
                    to="/roles/$roleId"
                    params={{ roleId: role.id }}
                    className="text-base font-semibold underline-offset-4 hover:underline"
                  >
                    {role.title}
                  </Link>
                  <StatusTag tone={role.status === "draft" ? "neutral" : "success"}>
                    {role.status === "draft" ? "Draft" : "Approved"}
                  </StatusTag>
                  <RoleAction roleId={role.id} status={role.status} />
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/** The row's single action: the same next-up label the role header shows (counts are unknown here). */
function RoleAction({ roleId, status }: { roleId: string; status: "draft" | "approved" }) {
  const next = nextUp({ status });
  const content = (
    <>
      {next.label}
      <ArrowRight aria-hidden="true" />
    </>
  );
  return (
    <Button asChild variant="outline" className="ml-auto h-10 px-3">
      {next.step === "criteria" ? (
        <Link to="/roles/$roleId" params={{ roleId }}>
          {content}
        </Link>
      ) : (
        <Link to="/roles/$roleId/candidates" params={{ roleId }}>
          {content}
        </Link>
      )}
    </Button>
  );
}

function NewRoleForm({ onCancel }: { onCancel: () => void }) {
  const navigate = useNavigate();
  const create = useCreateRole();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const ready = title.trim() !== "" && description.trim() !== "";

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready) return;
    create.mutate(
      { title: title.trim(), job_description: description.trim() },
      {
        onSuccess: (role) => {
          void navigate({ to: "/roles/$roleId", params: { roleId: role.id } });
        },
      },
    );
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={submit}>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="role-title">Role title</Label>
        <Input
          id="role-title"
          className="h-10"
          value={title}
          onChange={(e) => {
            setTitle(e.target.value);
          }}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="role-jd">Job description</Label>
        <Textarea
          id="role-jd"
          rows={8}
          value={description}
          onChange={(e) => {
            setDescription(e.target.value);
          }}
        />
      </div>
      {create.isError && <ErrorNotice error={create.error} />}
      <DialogFooter>
        <Button type="button" variant="outline" className="h-10 px-4" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" className="h-10 px-4" disabled={!ready || create.isPending}>
          {create.isPending ? "Creating role" : "Create role"}
        </Button>
      </DialogFooter>
    </form>
  );
}
