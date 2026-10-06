import { useState, type DragEvent } from "react";

import { AlertIcon } from "../../components/AlertIcon";
import { errorMessage } from "../../lib/errors";

import { MAX_FILES, type UploadFileResult } from "./api";
import { useUpload } from "./hooks";

function resultText(result: UploadFileResult): string {
  if (result.status === "accepted") {
    const duplicate =
      result.duplicate_of_candidate_no === null
        ? ""
        : `, possible duplicate of C-${String(result.duplicate_of_candidate_no).padStart(3, "0")}`;
    return `Accepted${duplicate}`;
  }
  if (result.status === "role_not_approved") return "Not uploaded: approve the criteria first";
  return `Not uploaded${result.reason === null ? "" : `: ${result.reason}`}`;
}

/** Upload zone (Design.md 7.8): picker or drop, then one result row per file. */
export function UploadZone({ roleId }: { roleId: string }) {
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
    <section aria-labelledby="upload-heading" className="card stack">
      <h2 id="upload-heading">Upload resumes</h2>
      <div
        className="dropzone"
        onDragOver={(e) => {
          e.preventDefault();
        }}
        onDrop={drop}
      >
        <p>Drop PDF or DOCX files here, or choose them. Up to {MAX_FILES} at a time.</p>
        <label className="btn btn-primary" htmlFor="resume-files">
          Choose files
        </label>
        <input
          id="resume-files"
          className="visually-hidden"
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
        <p role="alert" className="notice notice-danger">
          <AlertIcon />
          <span>Upload at most {MAX_FILES} files at a time. Choose fewer files.</span>
        </p>
      )}
      {upload.isError && (
        <p role="alert" className="notice notice-danger">
          <AlertIcon />
          <span>{errorMessage(upload.error)}</span>
        </p>
      )}
      {results.length > 0 && (
        <div className="stack">
          <p role="status">
            {results.length - failed} of {results.length} files uploaded
            {failed > 0 ? `, ${failed} not uploaded` : ""}.
          </p>
          <ul className="file-results">
            {results.map((result, index) => (
              <li key={`${result.file_name}-${index}`}>
                <span className="file-name">{result.file_name}</span>
                <span className={result.status === "accepted" ? "" : "muted"}>
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
