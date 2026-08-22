"use client";

import { useId, useMemo, useState } from "react";
import { Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { LearningBlock } from "@/features/course-network/types";
import { cn } from "@/lib/utils";

const originLabels = {
  curriculum: "Curriculum",
  teacher: "Teacher",
  material: "Material",
} as const;

export function CourseNetworkOutline({
  nodes,
  selectedId,
  onSelect,
  heading = "Learning blocks",
  className,
}: {
  nodes: LearningBlock[];
  selectedId: string | null;
  onSelect: (nodeId: string) => void;
  heading?: string;
  className?: string;
}) {
  const searchId = useId();
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const filteredNodes = useMemo(() => {
    const sorted = [...nodes].sort((left, right) =>
      left.title.localeCompare(right.title),
    );
    if (!normalizedQuery) return sorted;
    return sorted.filter((node) =>
      `${node.title} ${node.learning_goal} ${node.description}`
        .toLocaleLowerCase()
        .includes(normalizedQuery),
    );
  }, [nodes, normalizedQuery]);

  return (
    <section
      aria-labelledby={`${searchId}-heading`}
      className={cn(
        "flex min-h-0 flex-col rounded-xl border border-border bg-card shadow-sm",
        className,
      )}
    >
      <div className="border-b border-border p-3">
        <h2 id={`${searchId}-heading`} className="font-semibold text-foreground">
          {heading}
        </h2>
        <div className="relative mt-3">
          <label htmlFor={searchId} className="sr-only">
            Search learning blocks
          </label>
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            id={searchId}
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search learning blocks"
            className="pl-8"
          />
        </div>
        <p className="mt-2 text-xs text-muted-foreground" aria-live="polite">
          {filteredNodes.length} of {nodes.length} learning blocks
        </p>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        {filteredNodes.length ? (
          <ul className="space-y-1 p-2" aria-label="Course network outline">
            {filteredNodes.map((node) => {
              const selected = node.id === selectedId;
              return (
                <li key={node.id}>
                  <button
                    type="button"
                    aria-pressed={selected}
                    onClick={() => onSelect(node.id)}
                    className={cn(
                      "w-full rounded-lg border px-3 py-2 text-left transition-colors focus-visible:ring-2 focus-visible:ring-ring/40",
                      selected
                        ? "border-primary bg-primary/5"
                        : "border-transparent hover:border-border hover:bg-muted",
                    )}
                  >
                    <span className="flex items-start justify-between gap-2">
                      <span className="text-sm font-medium leading-snug text-foreground">
                        {node.title}
                      </span>
                      <Badge
                        variant="outline"
                        className="shrink-0 bg-muted text-[10px] text-muted-foreground"
                      >
                        {originLabels[node.origin]}
                      </Badge>
                    </span>
                    <span className="mt-1 line-clamp-2 block text-xs leading-relaxed text-muted-foreground">
                      {node.learning_goal || "Learning goal not yet described."}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        ) : (
          <Empty className="min-h-48 border-0">
            <EmptyHeader>
              <EmptyTitle>No matching learning blocks</EmptyTitle>
              <EmptyDescription>
                Try a title, learning goal, or keyword from the block description.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
      </ScrollArea>
    </section>
  );
}
