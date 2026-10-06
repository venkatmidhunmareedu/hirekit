import { errorMessage } from "../lib/errors";

import { AlertIcon } from "./AlertIcon";

/** A visible, announced error with an icon (Design.md section 11: plain message, next step). */
export function ErrorNotice({ error }: { error: unknown }) {
  return (
    <p role="alert" className="notice notice-danger">
      <AlertIcon />
      <span>{errorMessage(error)}</span>
    </p>
  );
}
