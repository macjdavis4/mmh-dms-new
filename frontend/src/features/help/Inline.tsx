import type { ReactNode } from "react";
import { Link } from "react-router";

/** Renders the inline subset of the help articles' Markdown as React
 * elements: **bold**, `code`, and [links](/app/page) or [links](help:slug#heading).
 * No HTML is ever injected; anything else is shown as plain text. */
const TOKEN = /\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)/g;

export function helpHref(href: string): string {
  if (href.startsWith("help:")) {
    const [slug, anchor] = href.slice(5).split("#");
    return `/help/${slug ?? ""}${anchor ? `#${anchor}` : ""}`;
  }
  return href;
}

export function Inline({ text }: { text: string }) {
  const out: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(TOKEN)) {
    const at = match.index;
    if (at > last) out.push(text.slice(last, at));
    const [whole, bold, code, label, href] = match;
    if (bold !== undefined) {
      out.push(
        <strong key={at} className="font-semibold">
          <Inline text={bold} />
        </strong>,
      );
    } else if (code !== undefined) {
      out.push(
        <code key={at} className="bg-muted rounded px-1.5 py-0.5 font-mono text-[0.9em]">
          {code}
        </code>,
      );
    } else if (label !== undefined && href !== undefined && (href.startsWith("/") || href.startsWith("help:")) && !href.startsWith("//")) {
      out.push(
        <Link key={at} to={helpHref(href)} className="text-primary font-semibold underline underline-offset-2">
          {label}
        </Link>,
      );
    } else {
      out.push(whole);
    }
    last = at + whole.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return <>{out}</>;
}
