"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";

import { Badge } from "@/components/ui/badge";
import type { CourseNetworkNode } from "@/features/course-network/types";
import { cn } from "@/lib/utils";

const originLabels = {
  curriculum: "Curriculum",
  teacher: "Teacher",
  material: "Material",
} as const;

export function LearningBlockNode({
  data,
  selected,
}: NodeProps<CourseNetworkNode>) {
  const block = data.learningBlock;
  const emphasized = selected || data.inspectorSelected;
  return (
    <article
      aria-label={`Lernbaustein: ${block.title}`}
      className={cn(
        "w-[250px] rounded-xl border bg-card p-3 text-left shadow-sm transition-colors",
        emphasized
          ? "border-primary ring-2 ring-ring/20"
          : "border-border hover:border-primary/40",
      )}
    >
      <Handle
        type="source"
        position={Position.Left}
        isConnectable={false}
        className="course-network-handle border-background bg-primary"
      />
      <Handle
        type="target"
        position={Position.Right}
        isConnectable={false}
        className="course-network-handle border-background bg-muted-foreground"
      />
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold leading-snug text-foreground">
          {block.title}
        </h3>
        <Badge
          variant="outline"
          className="shrink-0 bg-muted text-[10px] text-muted-foreground"
        >
          {originLabels[block.origin]}
        </Badge>
      </div>
      <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
        {block.learning_goal || "Learning goal not yet described."}
      </p>
    </article>
  );
}
