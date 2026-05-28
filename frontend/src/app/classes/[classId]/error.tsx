"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function ClassError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto max-w-lg space-y-4 py-12">
      <h1 className="text-2xl font-semibold">Could not load class</h1>
      <p className="text-sm text-muted-foreground">
        {error.message || "Something went wrong while loading this page."}
      </p>
      <p className="text-sm text-muted-foreground">
        Make sure the API is running on port 8001:{" "}
        <code className="rounded bg-accent px-1 text-accent-foreground">
          uvicorn app.main:app --reload --port 8001
        </code>
      </p>
      <div className="flex gap-3">
        <Button onClick={reset}>Try again</Button>
        <Button variant="outline" asChild>
          <Link href="/">All classes</Link>
        </Button>
      </div>
    </div>
  );
}
