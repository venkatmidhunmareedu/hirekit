import { errorMessage } from "../lib/errors";

import { AlertIcon } from "./AlertIcon";

/** A visible, announced error with an icon (Design.md section 11: plain message, next step). */
export function ErrorNotice({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <p role="alert" className="notice notice-danger">
      <AlertIcon />
      <span>{errorMessage(error)}</span>
      {retry && (
        <button type="button" className="btn btn-secondary" onClick={retry}>
          Try again
        </button>
      )}
    </p>
  );
}
