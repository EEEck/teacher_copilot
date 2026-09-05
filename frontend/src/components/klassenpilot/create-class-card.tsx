"use client";

import { useEffect, useState } from "react";

import { ActionLink } from "@/components/klassenpilot/action-link";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { client, type ClassSummary, type CurriculumRoute } from "@/lib/api";

const CHEMISTRY_LABEL = "Chemie";

function currentSchoolYear(): string {
  const today = new Date();
  const start = today.getFullYear() - (today.getMonth() < 8 ? 1 : 0);
  return `${start}_${String(start + 1).slice(-2)}`;
}

function routeKey(route: CurriculumRoute): string {
  return `${route.subject}|${route.grade}|${route.branch}`;
}

function routeLabel(route: CurriculumRoute): string {
  return `${CHEMISTRY_LABEL} ${route.grade} ${route.branch}`;
}

export function CreateClassCard({ onCreated }: { onCreated?: () => void }) {
  const [routes, setRoutes] = useState<CurriculumRoute[]>([]);
  const [selectedRoute, setSelectedRoute] = useState("");
  const [section, setSection] = useState("a");
  const [schoolYear, setSchoolYear] = useState(currentSchoolYear);
  const [customLabel, setCustomLabel] = useState<string | null>(null);
  const [createdClass, setCreatedClass] = useState<ClassSummary | null>(null);
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
            ? "No reviewed Chemie 8 or 9 NTG routes are available. Reload to try again or contact your beta host."
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
  const suggestedLabel = route
    ? `${CHEMISTRY_LABEL} ${route.grade}${section}${
        schoolYear ? ` — ${schoolYear.replace("_", "/")}` : ""
      }`
    : "";
  const label = customLabel ?? suggestedLabel;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!route || !label.trim() || submitting) return;

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
      setCreatedClass(created);
      onCreated?.();
    } catch (cause: unknown) {
      const message = cause instanceof Error ? cause.message : "Failed to create class";
      setError(message.includes("already exists")
        ? "This class already exists. Change the section or school year, or open the existing class from Your classes."
        : message.includes("No shared teaching framework") || message.includes("not supported")
          ? "This curriculum route is unavailable. Choose an available Chemie 8 or 9 NTG route, or reload to refresh the choices."
          : message);
      setSubmitting(false);
    }
  }

  if (createdClass) {
    const base = `/classes/${encodeURIComponent(createdClass.id)}`;
    return (
      <Card>
        <CardContent className="grid gap-4 p-5">
          <div role="status">
            <h3 className="font-medium">{createdClass.label} is ready</h3>
            <p className="mt-1 text-sm text-muted-foreground">No taught lessons yet. Review the curriculum map in Course, then add a chapter in Materials.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <ActionLink href={`${base}/course`} variant="default">Course</ActionLink>
            <ActionLink href={`${base}/course/materials`}>Materials</ActionLink>
            <ActionLink href={base}>Open class</ActionLink>
          </div>
        </CardContent>
      </Card>
    );
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
              Chemie 8 or 9 NTG, Gymnasium in Bavaria. New classes start with no taught lessons.
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
                maxLength={20}
                onChange={(event) => setSchoolYear(event.target.value)}
              />
              <FieldDescription>Confirm the suggested year, for example 2029/30.</FieldDescription>
            </Field>
          </div>

          <Field>
            <FieldLabel htmlFor="new-class-label">Class label</FieldLabel>
            <Input id="new-class-label" value={label} required maxLength={120}
              onChange={(event) => setCustomLabel(event.target.value)} />
            <FieldDescription>The name shown in Your classes. You can edit the suggestion.</FieldDescription>
          </Field>

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
            <FieldLabel htmlFor="new-class-roster">Roster (optional)</FieldLabel>
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
            <Button type="submit" disabled={submitting || !route || !label.trim()}>
              {submitting ? "Creating…" : "Create class"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
