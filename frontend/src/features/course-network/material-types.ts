import type { LearningBlock, MaterialMapping, NetworkEdge } from "./types";

export type CourseSection = { id: string; title: string; page_start: number; page_end: number; summary: string };
export type CourseMaterial = { class_id: string; material_id: string; title: string; arm: "textbook" | "personal"; source_filename: string; source_hash: string; sections: CourseSection[]; approved_at?: string; library_status?: "saved" | "approved"; archived?: boolean };
export type ImportArtifact = Omit<CourseMaterial, "sections"> & { sections: (CourseSection & { content: string; included: boolean })[] };
export type GraphOperation =
  | { op: "add_node"; node: LearningBlock }
  | { op: "update_node"; node_id: string; changes: { [K in "title" | "description" | "learning_goal" | "curriculum_refs" | "material_refs"]?: LearningBlock[K] | null } }
  | { op: "retire_node"; node_id: string }
  | { op: "add_edge"; edge: NetworkEdge }
  | { op: "remove_edge"; edge_id: string };
export type GraphChanges = { class_id: string; base_revision: number; summary: string; operations: GraphOperation[]; material_id: string | null; replacement_mappings: MaterialMapping[] | null };
export type CourseDraft<T> = { draft_id: string; class_id: string; status: string; artifact_revision: number; artifact_hash: string; artifact: T; runtime: { stage?: string; error?: string; generation?: { rationales: { item_id: string; reason: string }[]; coverage_notes: string[]; warnings: string[] } }; running: boolean; review: null | { decision: string; summary: string; findings: { message: string }[]; artifact_revision: number; artifact_hash: string } };
export const snapshot = (draft: CourseDraft<unknown>) => ({ expected_revision: draft.artifact_revision, expected_hash: draft.artifact_hash });
export const passingReview = (draft: CourseDraft<unknown>) => draft.review?.decision === "accept" && draft.review.artifact_revision === draft.artifact_revision && draft.review.artifact_hash === draft.artifact_hash;
