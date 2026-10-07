import { CircleCheck, FileUp, TriangleAlert } from "lucide-react";
import { useState, type DragEvent } from "react";

import { Button } from "@/components/ui/button";

import { Notice } from "../../components/Notice";
import { errorMessage } from "../../lib/errors";

import { MAX_FILES, type UploadFileResult, candidateLabel } from "./api";
import { useUpload } from "./hooks";

function resultText(result: UploadFileResult): string {
  if (result.status === "accepted") {
    const duplicate =
      result.duplicate_of_candidate_no === null
        ? ""
        : `, possible duplicate of ${candidateLabel(result.duplicate_of_candidate_no)}`;
    return `Accepted${duplicate}`;
  }
  if (result.status === "role_not_approved") return "Not uploaded: approve the criteria first";
  return `Not uploaded${result.reason === null ? "" : `: ${result.reason}`}`;
}

/**
 * Upload zone (Design.md 7.8): picker or drop, then one result row per file. Compact is a single
 * row, used once the role has candidates so the ranked list stays first; its button is not primary.
 */
export function UploadZone({ roleId, compact }: { roleId: string; compact: boolean }) {
  const upload = useUpload(roleId);
  const [tooMany, setTooMany] = useState(false);

  function send(files: File[]) {
    if (files.length === 0) return;
    setTooMany(files.length > MAX_FILES);
    if (files.length > MAX_FILES) return;
    upload.mutate(files);
  }

  function drop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    send(Array.from(event.dataTransfer.files));
  }

  const results = upload.data ?? [];
  const failed = results.filter((r) => r.status !== "accepted").length;

  return (
    <section aria-labelledby="upload-heading" className="flex flex-col gap-3">
      <div
        className={
          compact
            ? "flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-dashed border-input bg-card px-4 py-2.5 focus-within:ring-3 focus-within:ring-ring/50"
            : "flex flex-col items-start gap-3 rounded-lg border border-dashed border-input bg-card p-6 focus-within:ring-3 focus-within:ring-ring/50"
        }
        onDragOver={(e) => {
          e.preventDefault();
        }}
        onDrop={drop}
      >
        {compact ? (
          <FileUp aria-hidden="true" className="size-4 text-muted-foreground" />
        ) : (
          <FileUp aria-hidden="true" className="size-6 text-muted-foreground" />
        )}
        <h2 id="upload-heading" className={compact ? "text-sm font-medium" : undefined}>
          Upload resumes
        </h2>
        <p className={compact ? "text-sm text-muted-foreground" : undefined}>
          Drop PDF or DOCX files here, or choose them. Up to {MAX_FILES} at a time.
        </p>
        <Button
          asChild
          variant={compact ? "outline" : "default"}
          className={compact ? "ml-auto h-10 px-4" : "h-10 px-4"}
        >
          <label htmlFor="resume-files" className="cursor-pointer">
            Choose files
          </label>
        </Button>
        <input
          id="resume-files"
          className="sr-only"
          type="file"
          multiple
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          disabled={upload.isPending}
          onChange={(e) => {
            send(Array.from(e.target.files ?? []));
            e.target.value = "";
          }}
        />
      </div>
      {upload.isPending && <p role="status">Uploading</p>}
      {tooMany && (
        <Notice tone="danger">
          Upload at most {MAX_FILES} files at a time. Choose fewer files.
        </Notice>
      )}
      {upload.isError && <Notice tone="danger">{errorMessage(upload.error)}</Notice>}
      {results.length > 0 && (
        <div className="flex flex-col gap-2">
          <p role="status">
            {results.length - failed} of {results.length} files uploaded
            {failed > 0 ? `, ${failed} not uploaded` : ""}.
          </p>
          <ul className="flex flex-col divide-y rounded-lg border bg-card">
            {results.map((result, index) => (
              <li
                key={`${result.file_name}-${index}`}
                className="flex min-h-10 flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2"
              >
                {result.status === "accepted" ? (
                  <CircleCheck aria-hidden="true" className="size-4 shrink-0 text-ok" />
                ) : (
                  <TriangleAlert aria-hidden="true" className="size-4 shrink-0 text-warn" />
                )}
                <span className="font-mono text-sm">{result.file_name}</span>
                <span className={result.status === "accepted" ? "" : "text-muted-foreground"}>
                  {resultText(result)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
