"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { client, type CurriculumRoute } from "@/lib/api";

const SUBJECT_LABELS: Record<string, string> = { chemie: "Chemie", physik: "Physik" };

function routeKey(route: CurriculumRoute) {
  return `${route.subject}|${route.grade}|${route.branch}`;
}

function routeLabel(route: CurriculumRoute) {
  const subject = SUBJECT_LABELS[route.subject] ?? route.subject;
  return `${subject} ${route.grade} ${route.branch}`;
}

/** Deterministic class creation: the teacher supplies typed values, the backend
 * renders the wiki skeleton from templates. No model is involved. */
export function CreateClassCard({ onCreated }: { onCreated?: () => void }) {
  const router = useRouter();
  const [routes, setRoutes] = useState<CurriculumRoute[]>([]);
  const [selectedRoute, setSelectedRoute] = useState("");
  const [section, setSection] = useState("a");
  const [schoolYear, setSchoolYear] = useState("2026_27");
  const [priorLearning, setPriorLearning] = useState("");
  const [roster, setRoster] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    client
      .getCurriculumRoutes()
      .then((data) => {
        if (cancelled) return;
        setRoutes(data.routes);
        if (data.routes.length > 0) setSelectedRoute(routeKey(data.routes[0]));
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load routes");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const route = routes.find((r) => routeKey(r) === selectedRoute);
  const label = route
    ? `${SUBJECT_LABELS[route.subject] ?? route.subject} ${route.grade}${section}${
        schoolYear ? ` — ${schoolYear.replace("_", "/")}` : ""
      }`
    : "";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!route) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await client.createClass({
        label,
        subject: route.subject,
        grade: route.grade,
        branch: route.branch,
        section,
        school_year: schoolYear,
        prior_learning: priorLearning,
        student_names: roster
          .split("\n")
          .map((name) => name.trim())
          .filter(Boolean),
      });
      onCreated?.();
      router.push(`/classes/${created.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create class");
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardContent className="p-5">
        <form onSubmit={submit} className="grid gap-4">
          <Field>
            <FieldLabel htmlFor="new-class-route">Curriculum route</FieldLabel>
            <NativeSelect
              id="new-class-route"
              value={selectedRoute}
              onChange={(e) => setSelectedRoute(e.target.value)}
            >
              {routes.map((r) => (
                <NativeSelectOption key={routeKey(r)} value={routeKey(r)}>
                  {routeLabel(r)}
                </NativeSelectOption>
              ))}
            </NativeSelect>
            <FieldDescription>
              Only routes with a reviewed shared teaching framework can be created.
            </FieldDescription>
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="new-class-section">Section</FieldLabel>
              <Input
                id="new-class-section"
                value={section}
                maxLength={1}
                onChange={(e) => setSection(e.target.value.toLowerCase())}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="new-class-year">School year</FieldLabel>
              <Input
                id="new-class-year"
                value={schoolYear}
                onChange={(e) => setSchoolYear(e.target.value)}
              />
            </Field>
          </div>

          <Field>
            <FieldLabel htmlFor="new-class-prior">What have you covered so far?</FieldLabel>
            <Textarea
              id="new-class-prior"
              rows={2}
              value={priorLearning}
              onChange={(e) => setPriorLearning(e.target.value)}
              placeholder="Optional — recorded as prior learning, not as logged lessons."
            />
          </Field>

          <Field>
            <FieldLabel htmlFor="new-class-roster">Roster</FieldLabel>
            <Textarea
              id="new-class-roster"
              rows={3}
              value={roster}
              onChange={(e) => setRoster(e.target.value)}
              placeholder="Optional — one student name per line."
            />
          </Field>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              {label ? <>Creates <span className="font-medium text-foreground">{label}</span></> : null}
            </p>
            <Button type="submit" disabled={submitting || !route}>
              {submitting ? "Creating…" : "Create class"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
