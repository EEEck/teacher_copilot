import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { client, ClassSummary } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  let classes: ClassSummary[] = [];
  let error: string | null = null;
  try {
    const data = await client.getClasses();
    classes = data.classes;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load classes";
  }

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
            Backend not reachable: {error}. Start the API with{" "}
            <code className="rounded bg-accent px-1 text-accent-foreground">uvicorn app.main:app --reload</code>
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4">
        {classes.map((c) => (
          <Link
            key={c.id}
            href={`/classes/${c.id}`}
            className="block rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          >
            <Card className="transition hover:border-primary/30 hover:shadow-md">
              <CardContent className="p-6">
                <h2 className="text-xl font-semibold">{c.label}</h2>
                <p className="mt-1 text-sm text-muted-foreground">Subject: {c.subject}</p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
