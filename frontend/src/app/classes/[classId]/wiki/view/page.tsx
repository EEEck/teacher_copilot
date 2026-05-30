"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { MarkdownPreview } from "@/components/klassenpilot/markdown-preview";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { client } from "@/lib/api";
import { cn } from "@/lib/utils";

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

  const [activePath, setActivePath] = useState(paths[0] ?? "");
  const [markdown, setMarkdown] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (paths.length > 0 && !activePath) setActivePath(paths[0]);
  }, [paths, activePath]);

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

  return (
    <div className="space-y-6">
      <PageHeader
        backHref={`/classes/${classId}`}
        backLabel="Class home"
        title="Wiki file"
        description={activePath || "Select a file"}
      />

      {error && (
        <Alert className="border-destructive/30 bg-[var(--error-bg)] text-destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className={cn("grid gap-6", paths.length > 1 && "lg:grid-cols-[220px_1fr]")}>
        {paths.length > 1 && (
          <Card>
            <CardContent className="p-3">
              <p className="mb-2 text-xs font-medium text-muted-foreground">Changed files</p>
              <ul className="space-y-1">
                {paths.map((p) => (
                  <li key={p}>
                    <button
                      type="button"
                      onClick={() => setActivePath(p)}
                      className={cn(
                        "w-full rounded-md px-2 py-1.5 text-left font-mono text-xs hover:bg-muted",
                        activePath === p && "bg-muted text-primary",
                      )}
                    >
                      {p.split("/").pop()}
                    </button>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardContent className="p-4">
            <p className="mb-3 font-mono text-xs text-muted-foreground">{activePath}</p>
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : (
              <MarkdownPreview markdown={markdown || "_Empty file._"} />
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
