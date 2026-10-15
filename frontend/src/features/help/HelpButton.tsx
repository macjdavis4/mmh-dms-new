import { CircleHelp } from "lucide-react";
import { Link, useLocation } from "react-router";

import { Button } from "@/components/ui/button";
import { isOn, useFlags } from "@/lib/flags";

import { articleForPage, useHelpIndex } from "./api";

/** The "?" in the header: opens the help for the page you're on, or Help. */
export function HelpButton() {
  const { pathname } = useLocation();
  const flags = useFlags();
  const on = isOn(flags.data?.flags, "help");
  const index = useHelpIndex(on);
  if (!on) return null;
  const article = pathname.startsWith("/help") ? undefined : articleForPage(index.data?.articles ?? [], pathname);
  const to = article ? `/help/${article.slug}` : "/help";
  const label = article ? `Help for this page: ${article.title}` : "Help";
  return (
    <Button asChild variant="ghost" size="icon" className="size-11">
      <Link to={to} aria-label={label} title={label}>
        <CircleHelp className="size-5" />
      </Link>
    </Button>
  );
}
