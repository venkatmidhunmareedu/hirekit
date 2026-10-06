import { ApiError } from "./api";

/** Plain-language copy for a failed call (Design.md section 10: what happened, what next). */
export function errorMessage(error: Error): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case "network":
        return "Could not reach the server. Check your connection and try again.";
      case "forbidden":
        return "Your account may not do this.";
      case "not_found":
        return "That item was not found, or you cannot see it.";
      case "role_not_approved":
        return "Approve the criteria to start uploading and scoring resumes.";
      case "criteria_changed":
        return "The criteria changed since you loaded them. Reload the page and review them again.";
      case "budget_reached":
        return "The model budget has been reached. No new model calls can be made.";
      case "job_already_open":
        return "A job for this role is already running. Wait for it to finish.";
      case "payload_too_large":
        return "That upload is too large. Send fewer or smaller files.";
      case "too_many_files":
        return "Upload at most 100 files at a time.";
      case "no_criteria":
        return "Add at least one criterion before approving.";
      case "validation_error":
        return "Some fields are not valid. Check them and try again.";
    }
  }
  return "Something went wrong. Try again in a moment.";
}
