import type { Edge, Node } from "@xyflow/react";

export type CurriculumReference = {
  source_id: string;
  section_id: string;
};

export type MaterialSectionReference = {
  material_id: string;
  section_id: string;
  page_start: number | null;
  page_end: number | null;
};

export type LearningBlock = {
  id: string;
  title: string;
  description: string;
  learning_goal: string;
  curriculum_refs: CurriculumReference[];
  material_refs: MaterialSectionReference[];
  origin: "curriculum" | "teacher" | "material";
  status: "proposed" | "adopted" | "retired";
};

export type NetworkEdge = {
  id: string;
  source_id: string;
  target_id: string;
  relation: "builds_on" | "related_to";
  curriculum_refs: CurriculumReference[];
  material_refs: MaterialSectionReference[];
  origin: LearningBlock["origin"];
};

export type CanvasPosition = {
  x: number;
  y: number;
};

export type MaterialMapping = {
  id: string;
  material_id: string;
  section_id: string;
  node_id: string;
  relation: "explains" | "practices" | "assesses" | "extends";
  confidence: number | null;
  teacher_note: string;
  origin: "agent" | "teacher";
};

/**
 * Feature-local source of truth for the inner CourseNetwork API record.
 * API clients should import or re-export this type instead of defining a
 * parallel transport shape when they add the nullable response envelope.
 */
export type CourseNetwork = {
  schema_version: 1;
  class_id: string;
  route: {
    subject: string;
    grade: number;
    branch: string;
  };
  revision: number;
  nodes: LearningBlock[];
  edges: NetworkEdge[];
  material_mappings: MaterialMapping[];
  positions: Record<string, CanvasPosition>;
  updated_at: string;
};

export type CourseNetworkNode = Node<{
  learningBlock: LearningBlock;
  inspectorSelected?: boolean;
}>;
export type CourseNetworkEdge = Edge<{ relation: NetworkEdge["relation"] }>;

export type ReactFlowModel = {
  nodes: CourseNetworkNode[];
  edges: CourseNetworkEdge[];
};
