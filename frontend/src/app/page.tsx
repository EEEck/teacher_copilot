"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { client, type ClassSummary } from "@/lib/api";

export default function HomePage() {
  const [classes, setClasses] = useState<ClassSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    client
      .getClasses()
      .then((data) => {
        if (!cancelled) {
          setClasses(data.classes);
          setError(null);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load classes");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const needsLogin = error?.includes("API 401");

  return (
    <div>
      <header className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight">Select a class</h1>
        <p className="mt-2 text-muted-foreground">
          Open your lesson timeline, log memory, or generate a lesson plan.
        </p>
      </header>

      {error && (
        <Alert className="mb-6 border-border bg-muted text-foreground">
          <AlertDescription>
            {needsLogin ? (
              <>
                Beta login required.{" "}
                <Link href="/beta/login" className="text-primary hover:underline">
                  Enter invite code
                </Link>
              </>
            ) : (
              <>
                Backend not reachable: {error}. Start the API with{" "}
                <code className="rounded bg-accent px-1 text-accent-foreground">
                  uvicorn app.main:app --reload
                </code>
              </>
            )}
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4">
        {loading && (
          <Card>
            <CardContent className="p-6 text-sm text-muted-foreground">
              Loading classes...
            </CardContent>
          </Card>
        )}
        {!loading &&
          classes.map((c) => (
            <Link
              key={c.id}
              href={`/classes/${c.id}`}
              className="block rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
            >
              <Card className="transition hover:border-primary/30 hover:shadow-md">
                <CardContent className="p-6">
                  <h2 className="text-xl font-semibold">{c.label}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Subject: {c.subject}
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
      </div>
    </div>
  );
}
