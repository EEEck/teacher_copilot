import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { DocsSheet } from "@/components/docs/docs-canvas";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  collectHeadings,
  docsPages,
  getDocPage,
  getDocStepIndex,
  getNextDoc,
  getPreviousDoc,
} from "@/lib/docs/registry";
import {
  readDocMarkdown,
} from "@/lib/docs/server";
import { DocsMarkdown } from "../docs-markdown";
import { DocsNav } from "../docs-nav";

export const dynamic = "force-static";

export function generateStaticParams() {
  return docsPages.map((page) => ({ slug: page.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const page = getDocPage(slug);
  if (!page) return {};
  return {
    title: `${page.title} | KlassenPilot Docs`,
    description: page.description,
  };
}

export default async function DocArticlePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const page = getDocPage(slug);
  if (!page) notFound();

  const markdown = await readDocMarkdown(page.slug);
  const headings = collectHeadings(markdown);
  const step = getDocStepIndex(page.slug);
  const previous = getPreviousDoc(page.slug);
  const next = getNextDoc(page.slug);

  return (
    <div
      className={cn(
        "grid gap-10",
        headings.length >= 3
          ? "lg:grid-cols-[14rem_minmax(0,1fr)_11rem] xl:grid-cols-[15rem_minmax(0,1fr)_12rem]"
          : "lg:grid-cols-[14rem_minmax(0,1fr)]",
      )}
    >
      <aside className="hidden lg:block">
        <div className="sticky top-20">
          <Link
            href="/docs"
            className="mb-5 inline-flex items-center text-sm text-primary hover:underline"
          >
            <ArrowLeft className="mr-1 h-4 w-4" aria-hidden="true" />
            Docs home
          </Link>
          <DocsNav activeSlug={page.slug} />
        </div>
      </aside>

      <article className="min-w-0 pb-16">
        <DocsSheet>
          <div className="border-b border-border px-6 py-8 sm:px-8">
            <Link href="/docs" className="text-sm text-primary hover:underline lg:hidden">
              Docs home
            </Link>
            <p className="mt-4 text-xs font-semibold uppercase tracking-[0.2em] text-primary lg:mt-0">
              Guide · Step {step} of {docsPages.length}
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
              {page.title}
            </h1>
            <p className="mt-4 max-w-2xl text-lg leading-8 text-muted-foreground">
              {page.description}
            </p>
          </div>

          <div className="px-6 py-8 sm:px-8">
            <DocsMarkdown markdown={markdown} />
          </div>
        </DocsSheet>

        <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
          {previous ? (
            <Button asChild variant="outline">
              <Link href={`/docs/${previous.slug}`}>
                <ArrowLeft className="mr-1 h-4 w-4" aria-hidden="true" />
                {previous.title}
              </Link>
            </Button>
          ) : (
            <span />
          )}
          {next ? (
            <Button asChild variant="default">
              <Link href={`/docs/${next.slug}`}>
                Continue
                <ArrowRight className="ml-1 h-4 w-4" aria-hidden="true" />
              </Link>
            </Button>
          ) : (
            <Button asChild variant="outline">
              <Link href="/docs">
                Back to docs home
                <ArrowRight className="ml-1 h-4 w-4" aria-hidden="true" />
              </Link>
            </Button>
          )}
        </div>
      </article>

      {headings.length >= 3 && (
        <aside className="hidden xl:block">
          <div className="sticky top-20 space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              On this page
            </p>
            <nav className="space-y-1 text-sm">
              {headings.map((heading) => (
                <Link
                  key={heading.id}
                  href={`#${heading.id}`}
                  className="block rounded-md px-2 py-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  {heading.label}
                </Link>
              ))}
            </nav>
          </div>
        </aside>
      )}
    </div>
  );
}
