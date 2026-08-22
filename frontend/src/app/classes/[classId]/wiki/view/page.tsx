"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

import { MarkdownPreview } from "@/components/klassenpilot/markdown-preview";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { client, type WikiPageSummary } from "@/lib/api";
import { shortWikiPath } from "@/lib/markdown-diff";
import {
  normalizeClassWikiPath,
  wikiViewerHref,
} from "@/lib/wiki-viewer-links";
import { cn } from "@/lib/utils";

/** API kinds are singular for lesson/student rows. */
const KIND_ORDER = [
  "meta",
  "rollup",
  "memory",
  "timeline",
  "course_network",
  "lesson",
  "student",
  "raw",
];

function kindLabel(kind: string): string {
  switch (kind) {
    case "rollup":
      return "Roll-ups";
    case "meta":
      return "Class meta";
    case "memory":
      return "Memory";
    case "lesson":
    case "lessons":
      return "Lessons";
    case "student":
    case "students":
      return "Students";
    case "raw":
      return "Raw notes";
    case "timeline":
      return "Timeline";
    case "course_network":
      return "Course network";
    default:
      return kind.charAt(0).toUpperCase() + kind.slice(1);
  }
}

function fileName(path: string): string {
  const parts = path.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] || path;
}

function kindForPath(catalog: WikiPageSummary[], path: string): string | null {
  return catalog.find((page) => page.path === path)?.kind ?? null;
}

function HighlightMatch({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>;
  const lower = text.toLowerCase();
  const q = query.toLowerCase();
  const index = lower.indexOf(q);
  if (index < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, index)}
      <mark className="rounded-sm bg-accent px-0.5 text-accent-foreground">
        {text.slice(index, index + q.length)}
      </mark>
      {text.slice(index + q.length)}
    </>
  );
}

export default function WikiViewPage() {
  return (
    <Suspense fallback={<p className="p-6 text-muted-foreground">Loading wiki…</p>}>
      <WikiViewPageContent />
    </Suspense>
  );
}

function WikiViewPageContent() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const classId = params.classId as string;

  const deepLinkPath = useMemo(() => {
    const list = searchParams.getAll("path");
    const bulk = searchParams.get("paths");
    if (bulk) {
      list.push(...bulk.split(",").map((p) => p.trim()).filter(Boolean));
    }
    const raw = [...new Set(list)][0] ?? "";
    return raw ? normalizeClassWikiPath(classId, raw) : "";
  }, [searchParams, classId]);

  const [catalog, setCatalog] = useState<WikiPageSummary[]>([]);
  const [activePath, setActivePath] = useState(deepLinkPath);
  const [filterQuery, setFilterQuery] = useState("");
  const [openKinds, setOpenKinds] = useState<Set<string>>(new Set());
  const [markdown, setMarkdown] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeRowRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    void client
      .listWikiPages(classId)
      .then((res) => {
        if (!cancelled) setCatalog(res.pages);
      })
      .catch(() => {
        if (!cancelled) setCatalog([]);
      });
    return () => {
      cancelled = true;
    };
  }, [classId]);

  useEffect(() => {
    if (!deepLinkPath) return;
    setActivePath(deepLinkPath);
    const raw = searchParams.get("path") ?? "";
    if (raw && normalizeClassWikiPath(classId, raw) !== raw) {
      router.replace(wikiViewerHref(classId, deepLinkPath), { scroll: false });
    }
  }, [deepLinkPath, classId, router, searchParams]);

  useEffect(() => {
    if (deepLinkPath) return;
    if (!activePath && catalog.length > 0) {
      setActivePath(catalog[0].path);
    }
  }, [deepLinkPath, activePath, catalog]);

  useEffect(() => {
    const kind = kindForPath(catalog, activePath);
    if (!kind) return;
    setOpenKinds((prev) => {
      if (prev.has(kind)) return prev;
      const next = new Set(prev);
      next.add(kind);
      return next;
    });
  }, [catalog, activePath]);

  const load = useCallback(async () => {
    if (!activePath) return;
    setLoading(true);
    setError(null);
    try {
      const res = await client.getWikiFile(classId, activePath);
      setMarkdown(res.markdown);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load file");
      setMarkdown("");
    } finally {
      setLoading(false);
    }
  }, [classId, activePath]);

  useEffect(() => {
    void load();
  }, [load]);

  const selectPath = useCallback(
    (path: string) => {
      const normalized = normalizeClassWikiPath(classId, path);
      setActivePath(normalized);
      router.replace(wikiViewerHref(classId, normalized), { scroll: false });
    },
    [classId, router],
  );

  const normalizedFilter = filterQuery.trim().toLowerCase();

  const filteredCatalog = useMemo(() => {
    if (!normalizedFilter) return catalog;
    return catalog.filter((page) => {
      const haystack =
        `${page.path} ${shortWikiPath(page.path)} ${fileName(page.path)}`.toLowerCase();
      return haystack.includes(normalizedFilter);
    });
  }, [catalog, normalizedFilter]);

  const sortedFiltered = useMemo(() => {
    return [...filteredCatalog].sort((a, b) => {
      const ai = KIND_ORDER.indexOf(a.kind);
      const bi = KIND_ORDER.indexOf(b.kind);
      if (ai !== bi) return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
      return a.path.localeCompare(b.path);
    });
  }, [filteredCatalog]);

  const grouped = useMemo(() => {
    const groups = new Map<string, WikiPageSummary[]>();
    for (const page of sortedFiltered) {
      const list = groups.get(page.kind) ?? [];
      list.push(page);
      groups.set(page.kind, list);
    }
    return KIND_ORDER.filter((kind) => groups.has(kind))
      .concat([...groups.keys()].filter((kind) => !KIND_ORDER.includes(kind)))
      .map((kind) => [kind, groups.get(kind)!] as const);
  }, [sortedFiltered]);

  useEffect(() => {
    if (!normalizedFilter) return;
    setOpenKinds(new Set(grouped.map(([kind]) => kind)));
  }, [normalizedFilter, grouped]);

  useEffect(() => {
    activeRowRef.current?.scrollIntoView({ block: "nearest" });
  }, [activePath, openKinds, filterQuery]);

  const activeHiddenByFilter =
    Boolean(activePath) &&
    Boolean(normalizedFilter) &&
    !filteredCatalog.some((page) => page.path === activePath);

  const toggleKind = (kind: string, open: boolean) => {
    setOpenKinds((prev) => {
      const next = new Set(prev);
      if (open) next.add(kind);
      else next.delete(kind);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        backHref={`/classes/${classId}`}
        backLabel="Class home"
        title="Inspect wiki"
        description="Browse compiled memory for this class"
      />

      {error && (
        <Alert className="border-destructive/30 bg-[var(--error-bg)] text-destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <Card>
          <CardHeader className="space-y-3 p-4 pb-2">
            <CardTitle className="text-base">Files</CardTitle>
            <Input
              value={filterQuery}
              onChange={(event) => setFilterQuery(event.target.value)}
              placeholder="Filter by file name…"
              aria-label="Filter wiki files by name"
            />
            {normalizedFilter ? (
              <p className="text-xs text-muted-foreground">
                Showing {filteredCatalog.length} of {catalog.length}
                {activeHiddenByFilter
                  ? " · open file hidden by filter"
                  : ""}
              </p>
            ) : null}
          </CardHeader>
          <CardContent className="max-h-[70vh] space-y-2 overflow-y-auto p-3 pt-0">
            {grouped.length === 0 ? (
              <p className="px-1 py-2 text-sm text-muted-foreground">
                {catalog.length === 0
                  ? "No wiki pages found for this class yet."
                  : "No files match that filter."}
              </p>
            ) : (
              grouped.map(([kind, pages]) => (
                <Collapsible
                  key={kind}
                  open={openKinds.has(kind)}
                  onOpenChange={(open) => toggleKind(kind, open)}
                >
                  <CollapsibleTrigger asChild>
                    <button
                      type="button"
                      className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-xs font-medium text-muted-foreground hover:bg-muted"
                    >
                      <span>
                        {kindLabel(kind)}
                        <span className="ml-1 font-normal opacity-70">
                          ({pages.length})
                        </span>
                      </span>
                      <ChevronDown
                        className={cn(
                          "size-3.5 shrink-0 transition-transform",
                          openKinds.has(kind) ? "rotate-0" : "-rotate-90",
                        )}
                      />
                    </button>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <ul className="mt-1 space-y-1 pb-2">
                      {pages.map((page) => {
                        const selected = activePath === page.path;
                        const label = shortWikiPath(page.path);
                        return (
                          <li key={page.path}>
                            <button
                              ref={selected ? activeRowRef : undefined}
                              type="button"
                              onClick={() => selectPath(page.path)}
                              className={cn(
                                "w-full rounded-md px-2 py-1.5 text-left font-mono text-xs hover:bg-muted",
                                selected && "bg-muted text-primary",
                                normalizedFilter &&
                                  !selected &&
                                  "bg-accent/40",
                              )}
                            >
                              <HighlightMatch
                                text={label}
                                query={normalizedFilter}
                              />
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </CollapsibleContent>
                </Collapsible>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="space-y-1 p-4 pb-2">
            <CardTitle className="text-base">
              {activePath ? fileName(activePath) : "No file selected"}
            </CardTitle>
            {activePath ? (
              <p className="break-all font-mono text-xs text-muted-foreground">
                {activePath}
              </p>
            ) : null}
          </CardHeader>
          <CardContent className="p-4 pt-2">
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : activePath ? (
              <MarkdownPreview
                markdown={markdown || "_Empty file._"}
                classId={classId}
                currentWikiPath={activePath}
              />
            ) : (
              <p className="text-sm text-muted-foreground">
                Select a file from the list to read it.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <Button variant="outline" asChild>
        <Link href={`/classes/${classId}`}>Back to class home</Link>
      </Button>
    </div>
  );
}
