import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useState, type SubmitEvent } from "react";

import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Loading } from "../../components/Loading";
import { Modal } from "../../components/Modal";
import { PageHeader } from "../../components/PageHeader";
import { StatusTag } from "../../components/StatusTag";

import { rolesQueryOptions, useCreateRole } from "./hooks";

/** Role list (Design.md 8.1) with the new-role form: title and job description (PRD step 1). */
export function RolesPage() {
  const roles = useQuery(rolesQueryOptions);
  const [creating, setCreating] = useState(false);

  return (
    <div className="stack">
      <PageHeader
        title="Roles"
        purpose="Each role has its own criteria, candidates and interview kit."
        action={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setCreating(true);
            }}
          >
            New role
          </button>
        }
      />
      {creating && (
        <Modal
          title="New role"
          onClose={() => {
            setCreating(false);
          }}
        >
          <NewRoleForm
            onCancel={() => {
              setCreating(false);
            }}
          />
        </Modal>
      )}
      <section aria-labelledby="your-roles" className="stack">
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
          <ul className="role-list">
            {roles.data.map((role) => (
              <li key={role.id} className="card role-row">
                <Link to="/roles/$roleId" params={{ roleId: role.id }}>
                  {role.title}
                </Link>
                <StatusTag tone={role.status === "draft" ? "neutral" : "success"}>
                  {role.status === "draft" ? "Draft" : "Approved"}
                </StatusTag>
                {role.status === "draft" ? (
                  <Link to="/roles/$roleId" params={{ roleId: role.id }}>
                    Next: approve criteria
                  </Link>
                ) : (
                  <Link to="/roles/$roleId/candidates" params={{ roleId: role.id }}>
                    Next: upload and review candidates
                  </Link>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
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
    <form className="stack" onSubmit={submit}>
      <div className="field">
        <label htmlFor="role-title">Role title</label>
        <input
          id="role-title"
          value={title}
          onChange={(e) => {
            setTitle(e.target.value);
          }}
        />
      </div>
      <div className="field">
        <label htmlFor="role-jd">Job description</label>
        <textarea
          id="role-jd"
          rows={8}
          value={description}
          onChange={(e) => {
            setDescription(e.target.value);
          }}
        />
        <span className="muted">
          Paste the job description. You can ask for proposed criteria on the next screen.
        </span>
      </div>
      {create.isError && <ErrorNotice error={create.error} />}
      <div className="actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary" disabled={!ready || create.isPending}>
          {create.isPending ? "Creating role" : "Create role"}
        </button>
      </div>
    </form>
  );
}
