import { AlertCircle } from "lucide-react";

import { ApiError } from "@/lib/api";

/** Top-of-form error for anything that isn't tied to a single field. */
export function FormError({ error }: { error: unknown }) {
  if (!error) return null;
  const message =
    error instanceof ApiError
      ? Object.keys(error.fields).length > 0 && error.code === "invalid"
        ? "Please fix the highlighted fields."
        : error.message
      : "Something went wrong. Please try again.";
  return (
    <div
      role="alert"
      className="border-destructive/30 bg-destructive/10 text-destructive flex items-start gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium"
    >
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
