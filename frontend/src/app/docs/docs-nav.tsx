import Link from "next/link";
import { docsPages } from "@/lib/docs/registry";

export function DocsNav({ activeSlug }: { activeSlug?: string }) {
  return (
    <nav className="space-y-2 text-sm">
      <p className="px-2 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
        Guide
      </p>
      <ol className="space-y-1">
        {docsPages.map((page, index) => {
          const active = page.slug === activeSlug;
          return (
            <li key={page.slug}>
              <Link
                href={`/docs/${page.slug}`}
                aria-current={active ? "page" : undefined}
                className={
                  active
                    ? "flex items-start gap-2.5 rounded-md border-l-2 border-primary bg-muted px-2 py-2 font-medium text-foreground"
                    : "flex items-start gap-2.5 rounded-md border-l-2 border-transparent px-2 py-2 text-muted-foreground hover:bg-muted hover:text-foreground"
                }
              >
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-primary/25 bg-background font-mono text-[0.65rem] text-primary">
                  {index + 1}
                </span>
                <span className="min-w-0">
                  <span className="block leading-snug">{page.title}</span>
                  <span className="mt-0.5 block text-[0.68rem] uppercase tracking-[0.12em] text-muted-foreground">
                    {page.group}
                  </span>
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
