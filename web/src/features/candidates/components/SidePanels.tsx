import { useQuery } from "@tanstack/react-query";
import { type SubmitEvent, useState } from "react";

import { ErrorNotice } from "../../../components/ErrorNotice";
import { Icon } from "../../../components/Icon";
import { Modal } from "../../../components/Modal";
import { type AuditEvent, type Identity } from "../api";
import { anonymizedTextQueryOptions, useAssign, useReveal, useUnassign } from "../hooks";

/** Split text around the quote, matching on whitespace-normalized words only (PRD: no fuzzy match). */
export function splitAtQuote(text: string, quote: string | null): [string, string, string] | null {
  const words = quote?.trim().split(/\s+/) ?? [];
  if (words.length === 0 || words[0] === "") return null;
  const pattern = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+");
  const hit = new RegExp(pattern).exec(text);
  if (!hit) return null;
  return [text.slice(0, hit.index), hit[0], text.slice(hit.index + hit[0].length)];
}

/** The anonymized resume text, with the selected criterion's quote highlighted (Design.md 8.4). */
export function ResumeText({ candidateId, quote }: { candidateId: string; quote: string | null }) {
  const text = useQuery(anonymizedTextQueryOptions(candidateId));
  if (text.isPending) return <p role="status">Loading the resume text</p>;
  if (text.isError) return <ErrorNotice error={text.error} />;
  const parts = splitAtQuote(text.data, quote);
  return (
    <section aria-labelledby="resume-heading" className="section">
      <h2 id="resume-heading">Anonymized resume text</h2>
      <p className="muted">
        Identity signals are removed by code. Some signals, such as schools or career gaps, can
        remain.
      </p>
      <div className="resume-text">
        {parts ? (
          <>
            {parts[0]}
            <mark>{parts[1]}</mark>
            {parts[2]}
          </>
        ) : (
          text.data
        )}
      </div>
    </section>
  );
}

/** Reveal identity (Design.md section 9): an explicit, logged action behind a confirmation. */
export function RevealIdentity({ candidateId }: { candidateId: string }) {
  const reveal = useReveal(candidateId);
  const [asking, setAsking] = useState(false);
  const identity: Identity | undefined = reveal.data;

  if (identity) {
    return (
      <p>
        <span className="muted">Identity (revealed, logged): </span>
        <strong>{identity.identity_name ?? "No name found"}</strong>
        <span className="muted"> from {identity.file_name}</span>
      </p>
    );
  }
  return (
    <div className="stack">
      <button
        type="button"
        className="btn btn-secondary"
        onClick={() => {
          setAsking(true);
        }}
      >
        <Icon name="eye" /> Reveal identity
      </button>
      {asking && (
        <Modal
          title="Reveal identity?"
          onClose={() => {
            setAsking(false);
          }}
        >
          <p>Revealing the name is recorded in the audit history under your name.</p>
          {reveal.error && <ErrorNotice error={reveal.error} />}
          <div className="actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setAsking(false);
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={reveal.isPending}
              onClick={() => {
                reveal.mutate(undefined, {
                  onSuccess: () => {
                    setAsking(false);
                  },
                });
              }}
            >
              Reveal identity
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

/**
 * Assign interviewers. The contract has no call that lists users or a candidate's
 * assignments, so this takes an interviewer's user id and lists what was assigned
 * in this visit (see docs/progress/noticed.md).
 */
export function Assignments({ candidateId }: { candidateId: string }) {
  const assign = useAssign(candidateId);
  const unassign = useUnassign(candidateId);
  const [userId, setUserId] = useState("");
  const [assigned, setAssigned] = useState<string[]>([]);

  function onSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const id = userId.trim();
    assign.mutate(id, {
      onSuccess: () => {
        setAssigned((prev) => (prev.includes(id) ? prev : [...prev, id]));
        setUserId("");
      },
    });
  }

  return (
    <section aria-labelledby="assign-heading" className="section">
      <h2 id="assign-heading">Interviewers</h2>
      <form onSubmit={onSubmit} className="stack">
        <div className="field">
          <label htmlFor="assign-user">Interviewer user id</label>
          <span className="muted">
            Paste the interviewer's account id. The app cannot list users yet.
          </span>
          <input
            id="assign-user"
            value={userId}
            required
            onChange={(e) => {
              setUserId(e.target.value);
            }}
          />
        </div>
        <button type="submit" className="btn btn-secondary" disabled={assign.isPending}>
          Assign interviewer
        </button>
      </form>
      {assign.error && <ErrorNotice error={assign.error} />}
      {unassign.error && <ErrorNotice error={unassign.error} />}
      {assigned.length > 0 && (
        <ul className="plain-list">
          {assigned.map((id) => (
            <li key={id} className="row-between">
              <span className="mono">{id}</span>
              <button
                type="button"
                className="btn btn-ghost"
                aria-label={`Remove interviewer ${id}`}
                disabled={unassign.isPending}
                onClick={() => {
                  unassign.mutate(id, {
                    onSuccess: () => {
                      setAssigned((prev) => prev.filter((p) => p !== id));
                    },
                  });
                }}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function describe(event: AuditEvent): string {
  switch (event.kind) {
    case "score_override":
      return `Override on ${event.criterion_name ?? "a criterion"}: ${event.old_score ?? "none"} to ${event.new_score ?? "none"}`;
    case "stage_change":
      return `Stage ${event.from_stage ?? "none"} to ${event.to_stage ?? "none"}`;
    case "identity_reveal":
      return "Identity revealed";
    default:
      return event.kind.replaceAll("_", " ");
  }
}

/** Stage history and override history (Design.md 8.4), newest first, as the API sends it. */
export function AuditHistory({ events }: { events: AuditEvent[] }) {
  return (
    <section aria-labelledby="history-heading" className="section">
      <h2 id="history-heading">History</h2>
      {events.length === 0 ? (
        <p className="muted">No stage moves or overrides yet.</p>
      ) : (
        <ul className="plain-list">
          {events.map((e) => (
            <li key={e.id}>
              <span>{describe(e)}</span>
              {e.note && <span className="muted"> ({e.note})</span>}
              <span className="muted mono"> {e.created_at}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
