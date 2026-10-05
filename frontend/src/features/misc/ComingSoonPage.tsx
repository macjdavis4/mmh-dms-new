import { Construction } from "lucide-react";
import { Link, useLocation } from "react-router";

import { findNavItem } from "@/app/nav";
import { EmptyState, PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export function ComingSoonPage() {
  const { pathname } = useLocation();
  const item = findNavItem(pathname);
  const Icon = item?.icon ?? Construction;
  return (
    <>
      <PageHeader title={item?.label ?? "Coming soon"} />
      <Card>
        <EmptyState
          icon={Icon}
          title={item?.comingInPhase ? `Arrives in phase ${item.comingInPhase}` : "Not built yet"}
          message={item?.description}
          action={
            <Button asChild variant="outline">
              <Link to="/">Back to dashboard</Link>
            </Button>
          }
        />
      </Card>
    </>
  );
}

export function NotFoundPage() {
  return (
    <Card>
      <EmptyState
        title="Page not found"
        message="The link may be old, or the page was moved."
        action={
          <Button asChild variant="cta">
            <Link to="/">Go to dashboard</Link>
          </Button>
        }
      />
    </Card>
  );
}
