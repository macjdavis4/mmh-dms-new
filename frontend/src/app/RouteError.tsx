import { useRouteError } from "react-router";

import { ErrorState } from "@/components/states";

export function RouteError() {
  const error = useRouteError();
  console.error(error);
  return (
    <div className="grid min-h-dvh place-items-center p-6">
      <ErrorState
        title="This page hit a problem"
        message="It's been reported. Reload the page to try again."
        onRetry={() => window.location.reload()}
      />
    </div>
  );
}
