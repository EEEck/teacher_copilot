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

const CHEMISTRY_LABEL = "Chemie";

function routeKey(route: CurriculumRoute): string {
  return `${route.subject}|${route.grade}|${route.branch}`;
}

function routeLabel(route: CurriculumRoute): string {
  return `${CHEMISTRY_LABEL} ${route.grade} ${route.branch}`;
}

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
        const chemistryRoutes = data.routes.filter(
          (route) =>
            route.subject === "chemie" &&
            route.branch === "NTG" &&
            (route.grade === 8 || route.grade === 9),
        );
        setRoutes(chemistryRoutes);
        setSelectedRoute(chemistryRoutes[0] ? routeKey(chemistryRoutes[0]) : "");
        setError(
          chemistryRoutes.length === 0
            ? "No reviewed Chemie routes are available right now."
            : null,
        );
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Failed to load curriculum routes");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const route = routes.find((item) => routeKey(item) === selectedRoute);
  const label = route
    ? `${CHEMISTRY_LABEL} ${route.grade}${section}${
        schoolYear ? ` — ${schoolYear.replace("_", "/")}` : ""
      }`
    : "";

  async function submit(event: React.FormEvent<HTMLFormElement>) {
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
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Failed to create class");
      setSubmitting(false);
    }
  }

  return (
    <Card className="border-border/60 bg-card shadow-sm">
      <CardContent className="p-5">
        <form onSubmit={submit} className="grid gap-5">
          <Field>
            <FieldLabel htmlFor="new-class-route">Curriculum route</FieldLabel>
            <NativeSelect
              id="new-class-route"
              value={selectedRoute}
              onChange={(event) => setSelectedRoute(event.target.value)}
              disabled={routes.length === 0}
            >
              {routes.map((item) => (
                <NativeSelectOption key={routeKey(item)} value={routeKey(item)}>
                  {routeLabel(item)}
                </NativeSelectOption>
              ))}
            </NativeSelect>
            <FieldDescription>
              Only reviewed Chemie teaching frameworks can be used for a new class.
            </FieldDescription>
          </Field>

          <div className="grid gap-5 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="new-class-section">Section</FieldLabel>
              <Input
                id="new-class-section"
                value={section}
                maxLength={1}
                onChange={(event) => setSection(event.target.value.toLowerCase())}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="new-class-year">School year</FieldLabel>
              <Input
                id="new-class-year"
                value={schoolYear}
                onChange={(event) => setSchoolYear(event.target.value)}
              />
            </Field>
          </div>

          <Field>
            <FieldLabel htmlFor="new-class-prior">What have you covered so far?</FieldLabel>
            <Textarea
              id="new-class-prior"
              rows={2}
              value={priorLearning}
              onChange={(event) => setPriorLearning(event.target.value)}
              placeholder="Optional — recorded as prior learning, not as logged lessons."
            />
          </Field>

          <Field>
            <FieldLabel htmlFor="new-class-roster">Roster</FieldLabel>
            <Textarea
              id="new-class-roster"
              rows={3}
              value={roster}
              onChange={(event) => setRoster(event.target.value)}
              placeholder="Optional — one student name per line."
            />
          </Field>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              {label && (
                <>
                  Creates <span className="font-medium text-foreground">{label}</span>
                </>
              )}
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
