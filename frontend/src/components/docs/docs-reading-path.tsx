import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { docsPages, type DocPage } from "@/lib/docs/registry";

function ReadingPathStep({
  page,
  step,
  active,
}: {
  page: DocPage;
  step: number;
  active: boolean;
}) {
  return (
    <Link
      href={`/docs/${page.slug}`}
      aria-current={active ? "page" : undefined}
      className={
        active
          ? "group flex gap-4 rounded-xl border border-primary/30 bg-card p-4 shadow-sm ring-1 ring-primary/10"
          : "group flex gap-4 rounded-xl border border-border bg-card p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-primary/25 hover:shadow-md"
      }
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-background font-mono text-sm font-medium text-primary">
        {step}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center justify-between gap-2">
          <span className="font-semibold text-foreground">{page.title}</span>
          <ArrowRight
            className="h-4 w-4 shrink-0 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-primary"
            aria-hidden="true"
          />
        </span>
        <span className="mt-1 block text-sm leading-6 text-muted-foreground">{page.outcome}</span>
      </span>
    </Link>
  );
}

export function DocsReadingPath({ activeSlug }: { activeSlug?: string }) {
  const leftColumn = docsPages.slice(0, 3);
  const rightColumn = docsPages.slice(3, 5);

  return (
    <section className="space-y-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
          Reading path
        </p>
        <h2 className="mt-2 text-xl font-semibold tracking-tight">Five steps through the beta</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Follow in order — each page builds on the last.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 sm:items-start">
        <ol className="flex list-none flex-col gap-3">
          {leftColumn.map((page, index) => (
            <li key={page.slug}>
              <ReadingPathStep
                page={page}
                step={index + 1}
                active={page.slug === activeSlug}
              />
            </li>
          ))}
        </ol>
        <ol className="flex list-none flex-col gap-3">
          {rightColumn.map((page, index) => (
            <li key={page.slug}>
              <ReadingPathStep
                page={page}
                step={index + 4}
                active={page.slug === activeSlug}
              />
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
