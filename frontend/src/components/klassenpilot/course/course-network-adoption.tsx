"use client";

import { CheckCircle2, GitFork, Network, ShieldCheck, TriangleAlert } from "lucide-react";

import { CourseNetworkOutline } from "./course-network-outline";
import {
  CurriculumSourceLinks,
  LearningBlockInspector,
} from "./learning-block-inspector";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import type { CourseNetworkDraftResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

export type CourseNetworkAdoptionAction = "review" | "revise" | "adopt" | "discard";

export function isExactCourseNetworkReview(
  draft: CourseNetworkDraftResponse,
): boolean {
  return Boolean(
    draft.review &&
      draft.review.artifact_revision === draft.artifact_revision &&
      draft.review.artifact_hash === draft.artifact_hash,
  );
}

export function isExactPassingReview(
  draft: CourseNetworkDraftResponse,
): boolean {
  return Boolean(
    draft.status === "draft" &&
      isExactCourseNetworkReview(draft) &&
      draft.review?.decision === "accept" &&
      !draft.review.findings.some((finding) => finding.severity === "block"),
  );
}

function decisionPresentation(draft: CourseNetworkDraftResponse) {
  if (!draft.review) {
    return {
      label: "Not reviewed",
      description: "Run the bounded proposal review before adoption.",
      variant: "outline" as const,
    };
  }
  if (!isExactCourseNetworkReview(draft)) {
    return {
      label: "Review stale",
      description: "The saved review does not match this proposal revision and hash.",
      variant: "destructive" as const,
    };
  }
  if (draft.review.decision === "accept") {
    return {
      label: "Review passed",
      description: "This exact proposal snapshot passed review and can be adopted.",
      variant: "default" as const,
    };
  }
  if (draft.review.decision === "revise") {
    return {
      label: "Revision needed",
      description: "Revise the proposal to address these findings, then review it again.",
      variant: "outline" as const,
    };
  }
  return {
    label: "Adoption blocked",
    description: "Blocking findings must be resolved before this seed can be adopted.",
    variant: "destructive" as const,
  };
}

export function CourseNetworkAdoption({
  classId,
  draft,
  selectedId,
  onSelect,
  busyAction,
  onReview,
  onRevise,
  onAdopt,
  onDiscard,
}: {
  classId: string;
  draft: CourseNetworkDraftResponse;
  selectedId: string | null;
  onSelect: (nodeId: string) => void;
  busyAction: CourseNetworkAdoptionAction | null;
  onReview: () => Promise<void>;
  onRevise?: () => Promise<void>;
  onAdopt: () => Promise<void>;
  onDiscard: () => Promise<void>;
}) {
  const exactReview = isExactCourseNetworkReview(draft);
  const exactPassingReview = isExactPassingReview(draft);
  const reviewPresentation = decisionPresentation(draft);
  const curriculumReferences = [
    ...draft.network.nodes.flatMap((node) => node.curriculum_refs),
    ...draft.network.edges.flatMap((edge) => edge.curriculum_refs),
  ];
  const busy = busyAction !== null;

  return (
    <div className="min-h-0 space-y-4 pb-2">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Course network proposal</CardTitle>
              <CardDescription className="mt-1">
                A reviewed curriculum seed for {draft.network.route.subject}, grade{" "}
                {draft.network.route.grade} · {draft.network.route.branch}.
              </CardDescription>
            </div>
            <Badge variant={reviewPresentation.variant}>
              {reviewPresentation.label}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-border bg-muted p-3">
              <Network aria-hidden="true" className="size-4 text-muted-foreground" />
              <p className="mt-2 text-2xl font-semibold text-foreground">
                {draft.network.nodes.length}
              </p>
              <p className="text-xs text-muted-foreground">Proposed learning blocks</p>
            </div>
            <div className="rounded-lg border border-border bg-muted p-3">
              <GitFork aria-hidden="true" className="size-4 text-muted-foreground" />
              <p className="mt-2 text-2xl font-semibold text-foreground">
                {draft.network.edges.length}
              </p>
              <p className="text-xs text-muted-foreground">Proposed relationships</p>
            </div>
          </div>

          <section aria-labelledby="proposal-sources-heading">
            <h2
              id="proposal-sources-heading"
              className="text-sm font-semibold text-foreground"
            >
              Curriculum sources
            </h2>
            <p className="mb-2 mt-1 text-xs text-muted-foreground">
              Inspect the exact class-authorized section and its provenance.
            </p>
            <CurriculumSourceLinks
              classId={classId}
              references={curriculumReferences}
              className="grid gap-x-4 sm:grid-cols-2"
            />
          </section>
        </CardContent>
      </Card>

      <div className="grid min-h-0 gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <CourseNetworkOutline
          nodes={draft.network.nodes}
          selectedId={selectedId}
          onSelect={onSelect}
          heading="Proposal outline"
          className="min-h-[28rem]"
        />
        <LearningBlockInspector
          classId={classId}
          nodes={draft.network.nodes}
          edges={draft.network.edges}
          selectedId={selectedId}
          onSelect={onSelect}
          className="min-h-[28rem]"
        />
      </div>

      <Card aria-labelledby="proposal-review-heading">
        <CardHeader>
          <div className="flex items-start gap-3">
            <ShieldCheck
              aria-hidden="true"
              className="mt-0.5 size-5 shrink-0 text-muted-foreground"
            />
            <div>
              <CardTitle id="proposal-review-heading">Proposal review</CardTitle>
              <CardDescription className="mt-1">
                {reviewPresentation.description}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {draft.review ? (
            <>
              <Alert
                variant={
                  draft.review.decision === "block" || !exactReview
                    ? "destructive"
                    : "default"
                }
                className={cn(
                  exactPassingReview && "border-primary/30 bg-primary/5",
                )}
              >
                {exactPassingReview ? (
                  <CheckCircle2 aria-hidden="true" />
                ) : (
                  <TriangleAlert aria-hidden="true" />
                )}
                <AlertTitle>{reviewPresentation.label}</AlertTitle>
                <AlertDescription>{draft.review.summary}</AlertDescription>
              </Alert>

              <section aria-labelledby="review-findings-heading">
                <h3 id="review-findings-heading" className="text-sm font-semibold">
                  Review findings ({draft.review.findings.length})
                </h3>
                {draft.review.findings.length ? (
                  <ul className="mt-2 space-y-2">
                    {draft.review.findings.map((finding, index) => (
                      <li
                        key={`${finding.code}:${finding.path}:${index}`}
                        className="rounded-lg border border-border p-3"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge
                            variant={
                              finding.severity === "block"
                                ? "destructive"
                                : "outline"
                            }
                          >
                            {finding.severity === "block" ? "Blocking" : "Note"}
                          </Badge>
                          <span className="text-xs font-medium text-muted-foreground">
                            {finding.code}
                          </span>
                        </div>
                        <p className="mt-2 text-sm text-foreground">{finding.message}</p>
                        {finding.path ? (
                          <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
                            {finding.path}
                          </p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-sm text-muted-foreground">
                    No review findings were reported for this proposal.
                  </p>
                )}
              </section>

              <p className="break-all text-xs text-muted-foreground">
                Reviewed snapshot: revision {draft.review.artifact_revision} ·{" "}
                {draft.review.artifact_hash}
              </p>
            </>
          ) : (
            <Alert className="border-border bg-muted">
              <AlertTitle>Review required</AlertTitle>
              <AlertDescription>
                Review checks the exact saved proposal. It does not adopt or edit the
                network.
              </AlertDescription>
            </Alert>
          )}

          <div
            role="group"
            aria-label="Course network proposal actions"
            className="flex flex-wrap items-center gap-2 border-t border-border pt-4"
          >
            <Button
              type="button"
              variant={!exactReview && !exactPassingReview ? "default" : "outline"}
              disabled={busy || exactReview}
              aria-busy={busyAction === "review"}
              onClick={() => void onReview()}
            >
              {busyAction === "review" ? <Spinner aria-label="Reviewing proposal" /> : null}
              {draft.review && !exactReview ? "Review again" : "Review proposal"}
            </Button>
            {onRevise && draft.review?.decision !== "accept" && <Button variant="outline" disabled={busy} onClick={() => void onRevise()}>Revise proposal</Button>}
            <Button
              type="button"
              variant={exactPassingReview ? "default" : "outline"}
              disabled={busy || !exactPassingReview}
              aria-busy={busyAction === "adopt"}
              onClick={() => void onAdopt()}
            >
              {busyAction === "adopt" ? <Spinner aria-label="Adopting course network" /> : null}
              Adopt course network
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={busy}
              aria-busy={busyAction === "discard"}
              onClick={() => void onDiscard()}
              className="sm:ml-auto"
            >
              {busyAction === "discard" ? <Spinner aria-label="Discarding proposal" /> : null}
              Discard proposal
            </Button>
          </div>
          <p className="text-xs text-muted-foreground" aria-live="polite">
            {busyAction === "review"
              ? "Review in progress. This may take a moment."
              : busyAction === "adopt"
                ? "Adopting the exact reviewed proposal."
                : busyAction === "discard"
                  ? "Discarding the proposal without changing the class network."
                  : exactPassingReview
                    ? "Adoption is enabled for this exact revision and hash."
                    : "Adoption stays disabled until this exact proposal passes review."}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
