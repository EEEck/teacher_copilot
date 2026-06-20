import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { DocsHero } from "@/components/docs/docs-hero";
import { DocsReadingPath } from "@/components/docs/docs-reading-path";
import { Card, CardContent } from "@/components/ui/card";
import { docsPages } from "@/lib/docs/registry";

export const dynamic = "force-static";

export default function DocsLandingPage() {
  return (
    <div className="space-y-10 pb-8">
      <DocsHero />

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] lg:gap-10">
        <DocsReadingPath />

        <div className="space-y-6">
          <Card variant="highlight" className="border-primary/15">
            <CardContent className="p-5 sm:p-6">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
                Key takeaway
              </p>
              <p className="mt-3 text-base font-medium leading-7 text-foreground">
                KlassenPilot never saves class memory without your approval.
              </p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Chat drafts plans and lesson results. Durable wiki changes happen only
                after you review proposed file changes.
              </p>
            </CardContent>
          </Card>

          <Card className="border-dashed border-primary/25">
            <CardContent className="p-5 sm:p-6">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                Beta question
              </p>
              <p className="mt-3 text-sm leading-7 text-foreground">
                Can you update class memory, trust what changed, and get a better next
                lesson plan because of it?
              </p>
              <Link
                href="/docs/start-here"
                className="mt-4 inline-flex items-center text-sm font-medium text-primary hover:underline"
              >
                Read how we test this
                <ArrowRight className="ml-1 h-4 w-4" aria-hidden="true" />
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>

      <section className="border-t border-dashed border-primary/20 pt-8">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          All pages
        </p>
        <ul className="mt-4 space-y-2">
          {docsPages.map((page, index) => (
            <li key={page.slug}>
              <Link
                href={`/docs/${page.slug}`}
                className="group flex items-baseline gap-3 rounded-md py-1.5 text-sm hover:text-primary"
              >
                <span className="font-mono text-xs text-primary">{index + 1}.</span>
                <span className="font-medium">{page.title}</span>
                <span className="hidden text-muted-foreground sm:inline">— {page.description}</span>
                <ArrowRight
                  className="ml-auto h-4 w-4 shrink-0 text-muted-foreground opacity-0 transition group-hover:translate-x-0.5 group-hover:opacity-100 group-hover:text-primary"
                  aria-hidden="true"
                />
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
