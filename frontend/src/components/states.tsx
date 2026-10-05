import { AlertCircle, Inbox, Loader2, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

import { LogoMark } from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function FullPageLoading() {
  return (
    <div className="grid min-h-dvh place-items-center" role="status" aria-live="polite">
      <div className="flex flex-col items-center gap-4">
        <LogoMark className="size-12" />
        <Loader2 className="text-muted-foreground size-6 animate-spin" aria-hidden="true" />
        <span className="sr-only">Loading</span>
      </div>
    </div>
  );
}

export function FullPageError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="grid min-h-dvh place-items-center p-6">
      <ErrorState
        title="Can't reach the system"
        message="Check your internet connection. If it keeps happening, the server may be down for maintenance."
        onRetry={onRetry}
      />
    </div>
  );
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  message,
  action,
  className,
}: {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  message?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-14 text-center", className)}>
      <div className="bg-muted mb-4 grid size-14 place-items-center rounded-2xl">
        <Icon className="text-muted-foreground size-7" aria-hidden="true" />
      </div>
      <h3 className="text-lg font-bold">{title}</h3>
      {message && <p className="text-muted-foreground mt-1 max-w-md text-sm">{message}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="flex flex-col items-center px-6 py-14 text-center">
      <div className="bg-destructive/10 mb-4 grid size-14 place-items-center rounded-2xl">
        <AlertCircle className="text-destructive size-7" aria-hidden="true" />
      </div>
      <h3 className="text-lg font-bold">{title}</h3>
      {message && <p className="text-muted-foreground mt-1 max-w-md text-sm">{message}</p>}
      {onRetry && (
        <Button variant="outline" className="mt-5 h-11" onClick={onRetry}>
          <RefreshCw className="size-4" /> Try again
        </Button>
      )}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{title}</h1>
        {description && <p className="text-muted-foreground mt-1 text-[15px]">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
