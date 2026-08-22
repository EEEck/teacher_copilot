"use client";

import Link from "next/link";
import { ArrowRight, BookOpen, ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
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
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import type {
  CurriculumReference,
  LearningBlock,
  NetworkEdge,
} from "@/features/course-network/types";
import { cn } from "@/lib/utils";
import { wikiViewerHref } from "@/lib/wiki-viewer-links";

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

function curriculumWikiPath(sourceId: string): string | null {
  const match = sourceId.match(
    /^by-lehrplanplus-([a-z0-9-]+)-(\d+)-([a-z0-9-]+)$/i,
  );
  if (!match) return null;
  const [, subject, grade, branch] = match;
  return `wiki/sources/bayern/lehrplanplus/${subject!.replaceAll("-", "_")}_${grade}_${branch!.toLocaleLowerCase().replaceAll("-", "_")}.md`;
}

export function CurriculumSourceLinks({
  classId,
  references,
  className,
}: {
  classId: string;
  references: CurriculumReference[];
  className?: string;
}) {
  const uniqueReferences = [
    ...new Map(
      references.map((reference) => [
        `${reference.source_id}:${reference.section_id}`,
        reference,
      ]),
    ).values(),
  ];

  if (!uniqueReferences.length) {
    return <p className="text-sm text-muted-foreground">No curriculum sources cited.</p>;
  }

  return (
    <ul className={cn("space-y-1.5", className)}>
      {uniqueReferences.map((reference) => {
        const path = curriculumWikiPath(reference.source_id);
        const label = `${reference.source_id} · ${reference.section_id}`;
        return (
          <li key={`${reference.source_id}:${reference.section_id}`}>
            {path ? (
              <Link
                href={wikiViewerHref(classId, path)}
                className="inline-flex items-start gap-1 text-sm text-primary underline-offset-4 hover:underline"
              >
                <span className="break-all">{label}</span>
                <ExternalLink aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
              </Link>
            ) : (
              <span className="break-all text-sm text-muted-foreground">{label}</span>
            )}
          </li>
        );
      })}
    </ul>
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
          <ScrollArea className="min-h-0 flex-1">
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
          </ScrollArea>
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
