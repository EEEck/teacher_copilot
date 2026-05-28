"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { client, LessonPlan, planToMarkdown } from "@/lib/api";

export default function PlanPage() {
  const params = useParams();
  const classId = params.classId as string;
  const [plan, setPlan] = useState<LessonPlan | null>(null);
  const [markdown, setMarkdown] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      const p = await client.planLesson(classId);
      setPlan(p);
      setMarkdown(planToMarkdown(p));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate plan");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader
        backHref={`/classes/${classId}`}
        backLabel="Class home"
        title="Create lesson plan"
        description="Generate a 45-minute plan grounded in your class wiki memory."
      />

      {error && (
        <Alert className="mb-6 border-destructive/50 bg-destructive/5 text-destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Button onClick={generate} disabled={loading}>
        {loading ? "Generating…" : "Generate next lesson plan"}
      </Button>

      {plan && (
        <Card className="mt-8">
          <CardHeader>
            <CardTitle>{plan.title}</CardTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              className="min-h-[480px] font-mono text-sm"
              value={markdown}
              onChange={(e) => setMarkdown(e.target.value)}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
