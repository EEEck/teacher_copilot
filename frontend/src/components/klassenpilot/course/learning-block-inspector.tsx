"use client";

import { ArrowRight, BookOpen, ExternalLink } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

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
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import type {
  CurriculumReference,
  LearningBlock,
  NetworkEdge,
} from "@/features/course-network/types";
import { cn } from "@/lib/utils";
import {
  client,
  type CourseNetworkSourceSectionResponse,
} from "@/lib/api";

const originLabels = {
  curriculum: "Curriculum",
  teacher: "Teacher",
  material: "Material",
} as const;

const statusLabels = {
  proposed: "Proposed",
  adopted: "Adopted",
  retired: "Retired",
} as const;

export function CurriculumSourceLinks({
  classId,
  references,
  className,
}: {
  classId: string;
  references: CurriculumReference[];
  className?: string;
}) {
  const requestIdRef = useRef(0);
  const [activeReference, setActiveReference] =
    useState<CurriculumReference | null>(null);
  const [sourceSection, setSourceSection] =
    useState<CourseNetworkSourceSectionResponse | null>(null);
  const [loadingSource, setLoadingSource] = useState(false);
  const [sourceError, setSourceError] = useState<string | null>(null);
  const uniqueReferences = [
    ...new Map(
      references.map((reference) => [
        `${reference.source_id}:${reference.section_id}`,
        reference,
      ]),
    ).values(),
  ];

  useEffect(
    () => () => {
      requestIdRef.current += 1;
    },
    [],
  );

  const inspectSource = useCallback(
    async (reference: CurriculumReference) => {
      const requestId = ++requestIdRef.current;
      setActiveReference(reference);
      setSourceSection(null);
      setSourceError(null);
      setLoadingSource(true);
      try {
        const response = await client.getCourseNetworkSourceSection(
          classId,
          reference.source_id,
          reference.section_id,
        );
        if (requestId === requestIdRef.current) setSourceSection(response);
      } catch (error) {
        if (requestId !== requestIdRef.current) return;
        setSourceError(
          error instanceof Error && error.message
            ? error.message
            : "This curriculum source could not be loaded.",
        );
      } finally {
        if (requestId === requestIdRef.current) setLoadingSource(false);
      }
    },
    [classId],
  );

  const closeSource = useCallback(() => {
    requestIdRef.current += 1;
    setActiveReference(null);
    setSourceSection(null);
    setSourceError(null);
    setLoadingSource(false);
  }, []);

  if (!uniqueReferences.length) {
    return <p className="text-sm text-muted-foreground">No curriculum sources cited.</p>;
  }

  return (
    <div>
      <ul className={cn("space-y-1.5", className)}>
        {uniqueReferences.map((reference) => {
          const label = `${reference.source_id} · ${reference.section_id}`;
          const active =
            reference.source_id === activeReference?.source_id &&
            reference.section_id === activeReference.section_id;
          return (
            <li key={`${reference.source_id}:${reference.section_id}`}>
              <button
                type="button"
                aria-expanded={active}
                onClick={() => void inspectSource(reference)}
                className="inline-flex items-start gap-1 text-left text-sm text-primary underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring/40"
              >
                <span className="break-all">{label}</span>
                <BookOpen aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
              </button>
            </li>
          );
        })}
      </ul>

      {activeReference ? (
        <Card
          className="mt-3 gap-0 overflow-hidden py-0"
          aria-label="Curriculum source evidence"
        >
          {loadingSource ? (
            <CardContent className="space-y-3 py-4" aria-busy="true">
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-20 w-full" />
              <p className="sr-only" role="status">
                Loading curriculum source section
              </p>
            </CardContent>
          ) : sourceError ? (
            <CardContent className="py-4">
              <Alert variant="destructive">
                <AlertTitle>Source unavailable</AlertTitle>
                <AlertDescription className="space-y-3">
                  <p>{sourceError}</p>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => void inspectSource(activeReference)}
                    >
                      Try again
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={closeSource}
                    >
                      Close
                    </Button>
                  </div>
                </AlertDescription>
              </Alert>
            </CardContent>
          ) : sourceSection ? (
            <>
              <CardHeader className="border-b border-border py-4">
                <CardTitle className="pr-8 text-base">
                  {sourceSection.section_title}
                </CardTitle>
                <CardDescription>{sourceSection.source_title}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 py-4">
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                  {sourceSection.content}
                </p>
                <Separator />
                <dl className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                  <div>
                    <dt className="font-medium text-foreground">Authority</dt>
                    <dd>{sourceSection.provenance.authority}</dd>
                  </div>
                  <div>
                    <dt className="font-medium text-foreground">Jurisdiction</dt>
                    <dd>{sourceSection.provenance.jurisdiction || "Not specified"}</dd>
                  </div>
                  <div>
                    <dt className="font-medium text-foreground">Retrieved</dt>
                    <dd>{sourceSection.provenance.retrieved_at || "Not specified"}</dd>
                  </div>
                  <div>
                    <dt className="font-medium text-foreground">Version</dt>
                    <dd>{sourceSection.provenance.version_label || "Not specified"}</dd>
                  </div>
                </dl>
                <p className="break-all font-mono text-[11px] text-muted-foreground">
                  {sourceSection.source_id} · {sourceSection.section_id} ·{" "}
                  {sourceSection.provenance.content_hash}
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <Button asChild size="sm" variant="outline">
                    <a
                      href={sourceSection.provenance.canonical_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Official source
                      <ExternalLink aria-hidden="true" />
                    </a>
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={closeSource}
                  >
                    Close
                  </Button>
                </div>
              </CardContent>
            </>
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}

function relationshipLabel(edge: NetworkEdge, selectedId: string): string {
  if (edge.relation === "related_to") return "Related to";
  return edge.source_id === selectedId ? "Builds on" : "Used by";
}

export function LearningBlockInspector({
  classId,
  nodes,
  edges,
  selectedId,
  onSelect,
  className,
}: {
  classId: string;
  nodes: LearningBlock[];
  edges: NetworkEdge[];
  selectedId: string | null;
  onSelect: (nodeId: string) => void;
  className?: string;
}) {
  const selected = nodes.find((node) => node.id === selectedId) ?? null;
  const nodesById = new Map(nodes.map((node) => [node.id, node]));
  const relationships = selected
    ? edges
        .filter(
          (edge) =>
            edge.source_id === selected.id || edge.target_id === selected.id,
        )
        .map((edge) => ({
          edge,
          other:
            nodesById.get(
              edge.source_id === selected.id ? edge.target_id : edge.source_id,
            ) ?? null,
        }))
        .filter(
          (item): item is { edge: NetworkEdge; other: LearningBlock } =>
            item.other !== null,
        )
    : [];

  return (
    <Card
      className={cn("h-full min-h-[20rem] min-w-0 gap-0 py-0", className)}
      aria-label="Learning block inspector"
    >
      {selected ? (
        <>
          <CardHeader className="border-b border-border py-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="bg-muted text-muted-foreground">
                {originLabels[selected.origin]}
              </Badge>
              <Badge
                variant={selected.status === "adopted" ? "default" : "outline"}
              >
                {statusLabels[selected.status]}
              </Badge>
            </div>
            <CardTitle className="mt-2 text-lg">{selected.title}</CardTitle>
            <CardDescription>Read-only learning block details</CardDescription>
          </CardHeader>
          <div
            data-slot="learning-block-inspector-scroll"
            className="min-h-0 flex-1 overflow-y-auto"
          >
            <CardContent className="space-y-5 py-4">
              <section>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Learning goal
                </h3>
                <p className="mt-1 text-sm leading-relaxed text-foreground">
                  {selected.learning_goal || "No learning goal has been described."}
                </p>
              </section>

              <section>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Description
                </h3>
                <p className="mt-1 text-sm leading-relaxed text-foreground">
                  {selected.description || "No description has been provided."}
                </p>
              </section>

              <Separator />

              <section>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Curriculum sources
                </h3>
                <CurriculumSourceLinks
                  classId={classId}
                  references={selected.curriculum_refs}
                />
              </section>

              {selected.material_refs.length ? (
                <section>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Material references
                  </h3>
                  <ul className="space-y-1 text-sm text-foreground">
                    {selected.material_refs.map((reference) => {
                      const pages =
                        reference.page_start === null
                          ? ""
                          : reference.page_end === null ||
                              reference.page_end === reference.page_start
                            ? ` · p. ${reference.page_start}`
                            : ` · pp. ${reference.page_start}–${reference.page_end}`;
                      return (
                        <li key={`${reference.material_id}:${reference.section_id}`}>
                          {reference.material_id} · {reference.section_id}
                          {pages}
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ) : null}

              <Separator />

              <section>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Connections ({relationships.length})
                </h3>
                {relationships.length ? (
                  <ul className="space-y-2">
                    {relationships.map(({ edge, other }) => (
                      <li key={edge.id}>
                        <button
                          type="button"
                          onClick={() => onSelect(other.id)}
                          className="group w-full rounded-lg border border-border px-3 py-2 text-left hover:border-primary/30 hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/40"
                        >
                          <span className="flex items-center justify-between gap-2 text-xs font-medium text-muted-foreground">
                            {relationshipLabel(edge, selected.id)}
                            <ArrowRight
                              aria-hidden="true"
                              className="size-3.5 transition-transform group-hover:translate-x-0.5"
                            />
                          </span>
                          <span className="mt-0.5 block text-sm font-medium text-foreground">
                            {other.title}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    This block has no relationships in the current network.
                  </p>
                )}
              </section>
            </CardContent>
          </div>
        </>
      ) : (
        <Empty className="h-full border-0">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <BookOpen aria-hidden="true" />
            </EmptyMedia>
            <EmptyTitle>Select a learning block</EmptyTitle>
            <EmptyDescription>
              Choose a block in the graph or outline to inspect its goal, sources,
              and relationships.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}
    </Card>
  );
}
