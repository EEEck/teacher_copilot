import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export function DocsHero() {
  return (
    <section className="docs-sheet relative overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <div className="absolute inset-x-0 top-0 h-1 bg-primary" aria-hidden="true" />
      <div className="px-6 py-8 lg:px-10 lg:py-10">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">
          Beta guide
        </p>
        <h1 className="mt-4 max-w-2xl text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
          The class notebook that helps you plan what comes next.
        </h1>
        <p className="mt-4 max-w-2xl text-lg leading-8 text-muted-foreground">
          KlassenPilot learns from approved lesson memory, adapts to your teaching
          style and each class, then drafts plans you inspect, edit, and approve.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button asChild>
            <Link href="/docs/start-here">
              Start here
              <ArrowRight className="ml-1 h-4 w-4" aria-hidden="true" />
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/docs/first-session">20-minute walkthrough</Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
