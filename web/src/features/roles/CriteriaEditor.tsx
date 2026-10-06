import { useState } from "react";

import { AlertIcon } from "../../components/AlertIcon";
import { errorMessage } from "../../lib/errors";

import type { CriterionInput, CriterionKind, RoleDetail, RubricLevel } from "./api";
import { useApproveRole, useSaveCriteria } from "./hooks";

// Editable copy of a criterion; weight stays text while typing. `key` is a client-only React key.
interface Row {
  key: string;
  id: string | null;
  name: string;
  kind: CriterionKind;
  weight: string;
  rubric: RubricLevel[];
}

const LEVELS = [0, 1, 2, 3, 4];

function toRows(role: RoleDetail): Row[] {
  return role.criteria.map((c) => ({
    key: c.id,
    id: c.id,
    name: c.name,
    kind: c.kind,
    weight: String(c.weight),
    rubric: c.rubric,
  }));
}

function rowError(row: Row): string | null {
  if (row.name.trim() === "") return "Give every criterion a name.";
  if (!(Number(row.weight) > 0)) return `Give "${row.name}" a weight above zero.`;
  if (row.rubric.some((l) => l.descriptor.trim() === "")) {
    return `Describe every score level for "${row.name}".`;
  }
  return null;
}

function toInput(row: Row): CriterionInput {
  return {
    id: row.id,
    name: row.name.trim(),
    kind: row.kind,
    weight: Number(row.weight),
    rubric: row.rubric.map((l) => ({ level: l.level, descriptor: l.descriptor.trim() })),
  };
}

/**
 * Rubric editor (Design.md 7.5): must-have and nice-to-have groups, one rubric
 * descriptor per level. The parent keys this on the saved criteria, so a new
 * proposal or a save resets the draft.
 */
export function CriteriaEditor({ role }: { role: RoleDetail }) {
  const [rows, setRows] = useState<Row[]>(() => toRows(role));
  const [confirming, setConfirming] = useState(false);
  const save = useSaveCriteria(role.id);
  const approve = useApproveRole(role.id);

  const dirty = JSON.stringify(rows.map(toInput)) !== JSON.stringify(toRows(role).map(toInput));
  const problem = rows.map(rowError).find((e) => e !== null) ?? null;
  const failure = save.error ?? approve.error;
  const canApprove = !dirty && rows.length > 0 && role.status === "draft";

  function update(key: string, patch: Partial<Row>) {
    setRows((current) => current.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  }

  function add() {
    setRows((current) => [
      ...current,
      {
        key: crypto.randomUUID(),
        id: null,
        name: "",
        kind: "must_have",
        weight: "1",
        rubric: LEVELS.map((level) => ({ level, descriptor: "" })),
      },
    ]);
  }

  return (
    <div className="stack">
      {(["must_have", "nice_to_have"] as const).map((kind) => (
        <section key={kind} aria-labelledby={`group-${kind}`} className="stack">
          <h2 id={`group-${kind}`}>{kind === "must_have" ? "Must-have" : "Nice-to-have"}</h2>
          {rows.filter((r) => r.kind === kind).length === 0 && (
            <p className="muted">
              No {kind === "must_have" ? "must-have" : "nice-to-have"} criteria.
            </p>
          )}
          {rows
            .filter((r) => r.kind === kind)
            .map((row) => (
              <fieldset key={row.key} className="card criterion">
                <legend>{row.name.trim() || "New criterion"}</legend>
                <div className="field">
                  <label htmlFor={`name-${row.key}`}>Name</label>
                  <input
                    id={`name-${row.key}`}
                    value={row.name}
                    onChange={(e) => {
                      update(row.key, { name: e.target.value });
                    }}
                  />
                </div>
                <div className="criterion-meta">
                  <div className="field">
                    <label htmlFor={`kind-${row.key}`}>Type</label>
                    <select
                      id={`kind-${row.key}`}
                      value={row.kind}
                      onChange={(e) => {
                        update(row.key, {
                          kind: e.target.value === "nice_to_have" ? "nice_to_have" : "must_have",
                        });
                      }}
                    >
                      <option value="must_have">Must-have</option>
                      <option value="nice_to_have">Nice-to-have</option>
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor={`weight-${row.key}`}>Weight</label>
                    <input
                      id={`weight-${row.key}`}
                      type="number"
                      min="0"
                      step="any"
                      value={row.weight}
                      onChange={(e) => {
                        update(row.key, { weight: e.target.value });
                      }}
                    />
                  </div>
                </div>
                {row.rubric.map((level) => (
                  <div className="field" key={level.level}>
                    <label htmlFor={`level-${row.key}-${level.level}`}>
                      Score {level.level} looks like
                    </label>
                    <input
                      id={`level-${row.key}-${level.level}`}
                      value={level.descriptor}
                      onChange={(e) => {
                        update(row.key, {
                          rubric: row.rubric.map((l) =>
                            l.level === level.level ? { ...l, descriptor: e.target.value } : l,
                          ),
                        });
                      }}
                    />
                  </div>
                ))}
                <div>
                  <button
                    type="button"
                    className="btn btn-destructive"
                    onClick={() => {
                      setRows((current) => current.filter((r) => r.key !== row.key));
                    }}
                  >
                    Remove criterion
                  </button>
                </div>
              </fieldset>
            ))}
        </section>
      ))}
      <div>
        <button type="button" className="btn btn-secondary" onClick={add}>
          Add criterion
        </button>
      </div>

      {problem !== null && dirty && <p className="muted">{problem}</p>}
      {role.status === "approved" && (
        <p className="muted">Saving changes returns this role to Draft until you approve again.</p>
      )}
      {failure && (
        <p role="alert" className="notice notice-danger">
          <AlertIcon />
          <span>{errorMessage(failure)}</span>
        </p>
      )}
      {confirming && (
        <div role="group" aria-label="Confirm approval" className="card stack">
          <p>
            Approve these criteria? This unlocks resume upload and scoring. Resumes are scored only
            against the criteria you approve.
          </p>
          <div className="actions">
            <button
              type="button"
              className="btn btn-primary"
              disabled={approve.isPending}
              onClick={() => {
                approve.mutate(role.criteria_version, {
                  onSettled: () => {
                    setConfirming(false);
                  },
                });
              }}
            >
              Confirm approval
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setConfirming(false);
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      <div className="actions">
        <button
          type="button"
          className="btn btn-secondary"
          disabled={!dirty || problem !== null || save.isPending}
          onClick={() => {
            save.mutate(rows.map(toInput));
          }}
        >
          {save.isPending ? "Saving draft" : "Save draft"}
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!canApprove || approve.isPending}
          onClick={() => {
            setConfirming(true);
          }}
        >
          Approve criteria
        </button>
        {dirty && <span className="muted">Save the draft before approving.</span>}
      </div>
    </div>
  );
}
