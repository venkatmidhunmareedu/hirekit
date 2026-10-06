import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useState, type SubmitEvent } from "react";

import { AlertIcon } from "../../components/AlertIcon";
import { errorMessage } from "../../lib/errors";

import { rolesQueryOptions, useCreateRole } from "./hooks";

/** Role list (Design.md 8.1) with the new-role form: title and job description (PRD step 1). */
export function RolesPage() {
  const roles = useQuery(rolesQueryOptions);

  return (
    <div className="stack">
      <h1>Roles</h1>
      <NewRoleForm />
      <section aria-labelledby="your-roles" className="stack">
        <h2 id="your-roles">Your roles</h2>
        {roles.isPending && <p role="status">Loading roles</p>}
        {roles.isError && (
          <p role="alert" className="notice notice-danger">
            <AlertIcon />
            <span>{errorMessage(roles.error)}</span>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => void roles.refetch()}
            >
              Try again
            </button>
          </p>
        )}
        {roles.data?.length === 0 && (
          <p className="muted">No roles yet. Create one above to set its criteria.</p>
        )}
        {roles.data && roles.data.length > 0 && (
          <ul className="role-list">
            {roles.data.map((role) => (
              <li key={role.id} className="card role-row">
                <Link to="/roles/$roleId" params={{ roleId: role.id }}>
                  {role.title}
                </Link>
                <span className="tag">{role.status === "draft" ? "Draft" : "Approved"}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function NewRoleForm() {
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
    <form className="card stack" onSubmit={submit} aria-labelledby="new-role">
      <h2 id="new-role">New role</h2>
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
      {create.isError && (
        <p role="alert" className="notice notice-danger">
          <AlertIcon />
          <span>{errorMessage(create.error)}</span>
        </p>
      )}
      <div>
        <button type="submit" className="btn btn-primary" disabled={!ready || create.isPending}>
          {create.isPending ? "Creating role" : "Create role"}
        </button>
      </div>
    </form>
  );
}
