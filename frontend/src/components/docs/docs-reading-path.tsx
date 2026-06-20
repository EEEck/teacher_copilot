import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { docsPages } from "@/lib/docs/registry";

export function DocsReadingPath({ activeSlug }: { activeSlug?: string }) {
  return (
    <section className="space-y-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
          Reading path
        </p>
        <h2 className="mt-2 text-xl font-semibold tracking-tight">
          Five steps through the beta
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Follow in order — each page builds on the last.
        </p>
      </div>
      <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
        {docsPages.map((page, index) => {
          const active = page.slug === activeSlug;
          return (
            <li key={page.slug}>
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
                  {index + 1}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-foreground">{page.title}</span>
                    <ArrowRight
                      className="h-4 w-4 shrink-0 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-primary"
                      aria-hidden="true"
                    />
                  </span>
                  <span className="mt-1 block text-sm leading-6 text-muted-foreground">
                    {page.outcome}
                  </span>
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
