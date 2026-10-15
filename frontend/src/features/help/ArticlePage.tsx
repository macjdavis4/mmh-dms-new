import { AlertTriangle, ArrowLeft, Info, Lightbulb } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";

import { EmptyState, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

import { type HelpBlock, useHelpArticle } from "./api";
import { HelpSearchBox } from "./HelpPage";
import { Inline } from "./Inline";

const CALLOUT = {
  tip: { icon: Lightbulb, label: "Tip", className: "border-emerald-600/30 bg-emerald-600/5" },
  note: { icon: Info, label: "Note", className: "border-primary/30 bg-primary/5" },
  warning: { icon: AlertTriangle, label: "Warning", className: "border-amber-600/40 bg-amber-500/10" },
} as const;

export function Blocks({ blocks }: { blocks: HelpBlock[] }) {
  return (
    <>
      {blocks.map((block, i) => {
        switch (block.type) {
          case "heading":
            return block.level === 2 ? (
              <h2 key={i} id={block.anchor} className="mt-8 mb-3 scroll-mt-24 text-xl font-bold first:mt-0">
                <Inline text={block.text} />
              </h2>
            ) : (
              <h3 key={i} id={block.anchor} className="mt-6 mb-2 scroll-mt-24 text-lg font-bold">
                <Inline text={block.text} />
              </h3>
            );
          case "list": {
            const Tag = block.ordered ? "ol" : "ul";
            return (
              <Tag key={i} className={cn("my-3 flex flex-col gap-2 pl-6", block.ordered ? "list-decimal" : "list-disc")}>
                {block.items.map((item, j) => (
                  <li key={j} className="pl-1">
                    <Inline text={item} />
                  </li>
                ))}
              </Tag>
            );
          }
          case "callout": {
            const c = CALLOUT[block.tone];
            const Icon = c.icon;
            return (
              <div key={i} className={cn("my-4 flex gap-3 rounded-lg border p-4", c.className)} role="note">
                <Icon className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
                <p>
                  <span className="font-bold">{c.label}: </span>
                  <Inline text={block.text} />
                </p>
              </div>
            );
          }
          default:
            return (
              <p key={i} className="my-3">
                <Inline text={block.text} />
              </p>
            );
        }
      })}
    </>
  );
}

export function HelpArticlePage() {
  const { slug = "" } = useParams();
  const { hash } = useLocation();
  const navigate = useNavigate();
  const article = useHelpArticle(slug);
  const [query, setQuery] = useState("");

  // Jump to the heading a search result pointed at, once the text is there.
  useEffect(() => {
    if (!article.data) return;
    const id = decodeURIComponent(hash.slice(1));
    const target = id ? document.getElementById(id) : null;
    if (target) target.scrollIntoView({ block: "start" });
    else window.scrollTo({ top: 0 });
  }, [article.data, hash]);

  if (article.isPending) {
    return (
      <div className="max-w-3xl" role="status" aria-label="Loading">
        <Skeleton className="mb-4 h-10 w-2/3" />
        <Skeleton className="h-64" />
      </div>
    );
  }
  if (article.isError) {
    if (article.error instanceof ApiError && article.error.status === 404) {
      return (
        <EmptyState
          title="Help article not found"
          message="It may have moved, or it isn't for your role."
          action={
            <Button asChild variant="outline" className="h-11">
              <Link to="/help">All help</Link>
            </Button>
          }
        />
      );
    }
    return <ErrorState message="We couldn't load this help article." onRetry={() => void article.refetch()} />;
  }

  const a = article.data;
  const contents = a.blocks.filter((b): b is Extract<HelpBlock, { type: "heading" }> => b.type === "heading" && b.level === 2);

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_16rem]">
      <article className="max-w-3xl min-w-0">
        <Link to="/help" className="text-muted-foreground hover:text-foreground mb-3 inline-flex min-h-11 items-center gap-1.5 text-sm font-semibold">
          <ArrowLeft className="size-4" aria-hidden="true" /> Help
        </Link>
        <p className="text-muted-foreground text-sm font-semibold tracking-wide uppercase">{a.section_title}</p>
        <h1 className="mt-1 text-2xl font-extrabold tracking-tight sm:text-3xl">{a.title}</h1>
        <p className="text-muted-foreground mt-2 text-[17px]">{a.summary}</p>
        {contents.length >= 3 && (
          <nav aria-label="On this page" className="bg-muted/50 mt-6 rounded-lg p-4 lg:hidden">
            <p className="mb-2 text-sm font-bold">On this page</p>
            <ul className="flex flex-col gap-1 text-sm">
              {contents.map((h) => (
                <li key={h.anchor}>
                  <a href={`#${h.anchor}`} className="text-primary inline-flex min-h-9 items-center font-medium hover:underline">
                    {h.text.replace(/\*\*|`/g, "")}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        )}
        <div className="mt-6 text-[16px] leading-relaxed">
          <Blocks blocks={a.blocks} />
        </div>
      </article>

      <aside className="flex flex-col gap-6 lg:sticky lg:top-24 lg:self-start">
        <form
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            if (query.trim()) void navigate(`/help?q=${encodeURIComponent(query.trim())}`);
          }}
        >
          <HelpSearchBox value={query} onChange={setQuery} placeholder="Search help" />
        </form>
        {contents.length >= 3 && (
          <nav aria-label="On this page (sidebar)" className="hidden lg:block">
            <p className="mb-2 text-sm font-bold">On this page</p>
            <ul className="flex flex-col gap-1 text-sm">
              {contents.map((h) => (
                <li key={h.anchor}>
                  <a href={`#${h.anchor}`} className="text-muted-foreground hover:text-foreground inline-flex min-h-8 items-center">
                    {h.text.replace(/\*\*|`/g, "")}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        )}
        {a.related.length > 0 && (
          <Card className="gap-0 py-3">
            <p className="px-4 pb-1 text-sm font-bold">More in {a.section_title}</p>
            <ul>
              {a.related.map((r) => (
                <li key={r.slug}>
                  <Link to={`/help/${r.slug}`} className="hover:bg-muted/60 block min-h-11 px-4 py-2.5 text-sm font-medium">
                    {r.title}
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </aside>
    </div>
  );
}
