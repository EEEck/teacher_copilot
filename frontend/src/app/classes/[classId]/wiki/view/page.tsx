"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { MarkdownPreview } from "@/components/klassenpilot/markdown-preview";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { client, type WikiPageSummary } from "@/lib/api";
import { shortWikiPath } from "@/lib/markdown-diff";
import { cn } from "@/lib/utils";

const KIND_ORDER = ["meta", "rollup", "memory", "lessons", "students", "raw", "timeline"];

function kindLabel(kind: string): string {
  switch (kind) {
    case "rollup":
      return "Roll-ups";
    case "meta":
      return "Class meta";
    case "memory":
      return "Memory";
    case "lessons":
      return "Lessons";
    case "students":
      return "Students";
    case "raw":
      return "Raw notes";
    case "timeline":
      return "Timeline";
    default:
      return kind;
  }
}

export default function WikiViewPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const classId = params.classId as string;

  const paths = useMemo(() => {
    const list = searchParams.getAll("path");
    const bulk = searchParams.get("paths");
    if (bulk) {
      list.push(...bulk.split(",").map((p) => p.trim()).filter(Boolean));
    }
    return [...new Set(list)];
  }, [searchParams]);

  const [catalog, setCatalog] = useState<WikiPageSummary[]>([]);
  const [activePath, setActivePath] = useState(paths[0] ?? "");
  const [markdown, setMarkdown] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    if (paths.length > 0) {
      if (!activePath || !paths.includes(activePath)) setActivePath(paths[0]);
      return;
    }
    if (!activePath && catalog.length > 0) {
      setActivePath(catalog[0].path);
    }
  }, [paths, activePath, catalog]);

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

  const sidebarPages = useMemo(() => {
    if (paths.length > 0) {
      return paths.map((path) => ({ kind: "selected", id: path, path }));
    }
    return [...catalog].sort((a, b) => {
      const ai = KIND_ORDER.indexOf(a.kind);
      const bi = KIND_ORDER.indexOf(b.kind);
      if (ai !== bi) return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
      return a.path.localeCompare(b.path);
    });
  }, [paths, catalog]);

  const grouped = useMemo(() => {
    const groups = new Map<string, WikiPageSummary[]>();
    for (const page of sidebarPages) {
      const key = page.kind;
      const list = groups.get(key) ?? [];
      list.push(page);
      groups.set(key, list);
    }
    return groups;
  }, [sidebarPages]);

  const showSidebar = sidebarPages.length > 0;

  return (
    <div className="space-y-6">
      <PageHeader
        backHref={`/classes/${classId}`}
        backLabel="Class home"
        title="Inspect wiki"
        description={activePath || "Select a class memory file"}
      />

      {error && (
        <Alert className="border-destructive/30 bg-[var(--error-bg)] text-destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className={cn("grid gap-6", showSidebar && "lg:grid-cols-[240px_1fr]")}>
        {showSidebar && (
          <Card>
            <CardContent className="max-h-[70vh] space-y-4 overflow-y-auto p-3">
              {[...grouped.entries()].map(([kind, pages]) => (
                <div key={kind}>
                  <p className="mb-2 text-xs font-medium text-muted-foreground">
                    {kindLabel(kind)}
                  </p>
                  <ul className="space-y-1">
                    {pages.map((page) => (
                      <li key={page.path}>
                        <button
                          type="button"
                          onClick={() => setActivePath(page.path)}
                          className={cn(
                            "w-full rounded-md px-2 py-1.5 text-left font-mono text-xs hover:bg-muted",
                            activePath === page.path && "bg-muted text-primary",
                          )}
                        >
                          {shortWikiPath(page.path)}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        <Card>
          <CardContent className="p-4">
            <p className="mb-3 font-mono text-xs text-muted-foreground">
              {activePath || "No file selected"}
            </p>
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : activePath ? (
              <MarkdownPreview markdown={markdown || "_Empty file._"} />
            ) : (
              <p className="text-sm text-muted-foreground">
                No wiki pages found for this class yet.
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
