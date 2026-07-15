"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { HomeLanding } from "@/components/klassenpilot/home-landing";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { client, type ClassSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

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
    <div className="relative left-1/2 w-screen max-w-[100vw] -translate-x-1/2 -mx-6 -my-6 min-h-[calc(100vh-3.5rem)] bg-muted/60 px-6 py-10 sm:px-8 sm:py-14">
      <div className="mx-auto w-full max-w-[58rem]">
        <HomeLanding />

        <section
          aria-labelledby="coming-soon-classes-heading"
          className="mt-10 opacity-70 sm:mt-12"
        >
          <h2
            id="coming-soon-classes-heading"
            className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground"
          >
            Coming soon
          </h2>
          <p className="mb-4 max-w-lg text-sm leading-relaxed text-muted-foreground">
            All classes in this workspace. The beta highlights Chemie 9b above; more classes will
            land here over time.
          </p>

          {error && (
            <Alert className="mb-4 border-border/60 bg-muted/40 text-muted-foreground shadow-none">
              <AlertDescription>
                {needsLogin ? (
                  <>
                    Beta login required.{" "}
                    <Link href="/beta/login" className="text-foreground underline underline-offset-2">
                      Enter invite code
                    </Link>
                  </>
                ) : (
                  <>
                    Backend not reachable: {error}. Start the API with{" "}
                    <code className="rounded bg-muted px-1 text-foreground/80">
                      uvicorn app.main:app --reload
                    </code>
                  </>
                )}
              </AlertDescription>
            </Alert>
          )}

          <div className="grid gap-2">
            {loading && (
              <Card className="border-border/50 bg-muted/30 shadow-none">
                <CardContent className="p-5 text-sm text-muted-foreground">
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
                  <Card
                    className={cn(
                      "border-border/50 bg-muted/30 shadow-none transition",
                      "hover:border-border hover:bg-muted/50",
                    )}
                  >
                    <CardContent className="p-5">
                      <h3 className="text-base font-medium text-muted-foreground">{c.label}</h3>
                      <p className="mt-1 text-sm text-muted-foreground/80">Subject: {c.subject}</p>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            {!loading && !error && classes.length === 0 && (
              <Card className="border-border/50 bg-muted/30 shadow-none">
                <CardContent className="p-5 text-sm text-muted-foreground">
                  No classes yet.
                </CardContent>
              </Card>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
