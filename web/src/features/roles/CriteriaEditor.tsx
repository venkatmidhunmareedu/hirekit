import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { Notice } from "../../components/Notice";
import { Section } from "../../components/Section";
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
  const approveBlocker = dirty
    ? "Save your edits first."
    : rows.length === 0
      ? "Add at least one criterion first."
      : null;

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
    <div className="flex flex-col gap-8">
      {(["must_have", "nice_to_have"] as const).map((kind) => (
        <Section
          key={kind}
          id={`group-${kind}`}
          title={kind === "must_have" ? "Must-have" : "Nice-to-have"}
        >
          {rows.filter((r) => r.kind === kind).length === 0 && (
            <p className="text-muted-foreground">
              No {kind === "must_have" ? "must-have" : "nice-to-have"} criteria.
            </p>
          )}
          {rows
            .filter((r) => r.kind === kind)
            .map((row) => (
              <Card key={row.key} className="px-5 py-5">
                <fieldset className="flex min-w-0 flex-col gap-4">
                  <legend className="mb-3 text-base font-semibold">
                    {row.name.trim() || "New criterion"}
                  </legend>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor={`name-${row.key}`}>Name</Label>
                    <Input
                      id={`name-${row.key}`}
                      className="h-10"
                      value={row.name}
                      onChange={(e) => {
                        update(row.key, { name: e.target.value });
                      }}
                    />
                  </div>
                  <div className="flex flex-wrap gap-4">
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor={`kind-${row.key}`}>Type</Label>
                      <Select
                        value={row.kind}
                        onValueChange={(value) => {
                          update(row.key, {
                            kind: value === "nice_to_have" ? "nice_to_have" : "must_have",
                          });
                        }}
                      >
                        <SelectTrigger id={`kind-${row.key}`} className="h-10 w-44">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="must_have">Must-have</SelectItem>
                          <SelectItem value="nice_to_have">Nice-to-have</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor={`weight-${row.key}`}>Weight</Label>
                      <Input
                        id={`weight-${row.key}`}
                        type="number"
                        min="0"
                        step="any"
                        className="h-10 w-28 font-mono"
                        value={row.weight}
                        onChange={(e) => {
                          update(row.key, { weight: e.target.value });
                        }}
                      />
                    </div>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {row.rubric.map((level) => (
                      <div className="flex flex-col gap-1.5" key={level.level}>
                        <Label htmlFor={`level-${row.key}-${level.level}`}>
                          Score {level.level} looks like
                        </Label>
                        <Textarea
                          id={`level-${row.key}-${level.level}`}
                          rows={3}
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
                  </div>
                  <div>
                    <Button
                      type="button"
                      variant="destructive"
                      className="h-10 px-4"
                      onClick={() => {
                        setRows((current) => current.filter((r) => r.key !== row.key));
                      }}
                    >
                      <Trash2 aria-hidden="true" />
                      Remove criterion
                    </Button>
                  </div>
                </fieldset>
              </Card>
            ))}
        </Section>
      ))}
      <div>
        <Button type="button" variant="outline" className="h-10 px-4" onClick={add}>
          <Plus aria-hidden="true" />
          Add criterion
        </Button>
      </div>

      {problem !== null && dirty && <p className="text-muted-foreground">{problem}</p>}
      {role.status === "approved" && (
        <p className="text-muted-foreground">
          Saving changes returns this role to Draft until you approve again.
        </p>
      )}
      {failure && <Notice tone="danger">{errorMessage(failure)}</Notice>}
      {confirming && (
        <div role="group" aria-label="Confirm approval">
          <Notice
            tone="warning"
            role="status"
            action={
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  className="h-10 px-4"
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
                </Button>
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
              </div>
            }
          >
            Approve these criteria? This unlocks resume upload and scoring. Resumes are scored only
            against the criteria you approve.
          </Notice>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant={dirty ? "default" : "outline"}
          className="h-10 px-4"
          disabled={!dirty || problem !== null || save.isPending}
          onClick={() => {
            save.mutate(rows.map(toInput));
          }}
        >
          {save.isPending ? "Saving draft" : "Save draft"}
        </Button>
        <Button
          type="button"
          variant={dirty ? "outline" : "default"}
          className="h-10 px-4"
          aria-describedby={approveBlocker ? "approve-blocker" : undefined}
          disabled={!canApprove || approve.isPending}
          onClick={() => {
            setConfirming(true);
          }}
        >
          Approve criteria
        </Button>
        {role.status === "draft" && approveBlocker && (
          <span id="approve-blocker" className="text-muted-foreground">
            {approveBlocker}
          </span>
        )}
      </div>
    </div>
  );
}
