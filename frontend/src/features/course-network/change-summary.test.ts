import { expect, it } from "vitest";
import { summarizeGraphChanges } from "./change-summary";
import type { GraphChanges } from "./material-types";
import type { MaterialMapping } from "./types";

const mapping: MaterialMapping = { id: "map-one", material_id: "mat-one", section_id: "sec-one",
  node_id: "concept-one", relation: "explains", teacher_note: "Keep this note", origin: "teacher", confidence: null };
const changes: GraphChanges = { class_id: "chemie", base_revision: 1, summary: "Model claims are not authoritative",
  operations: [], material_id: "mat-one", replacement_mappings: null };

it("counts additions, note edits and removals without counting retained mappings as new", () => {
  const removed = { ...mapping, id: "map-removed", section_id: "sec-removed" };
  const retained = { ...mapping, id: "map-retained", section_id: "sec-retained" };
  const unrelated = { ...mapping, id: "map-other", material_id: "mat-other" };
  const summary = summarizeGraphChanges({ ...changes, replacement_mappings: [
    { ...mapping, teacher_note: "Changed note" }, retained,
    { ...mapping, id: "map-new", section_id: "sec-new" },
  ] }, [mapping, removed, retained, unrelated], []);
  expect(summary).toContain("Chapter connections: 1 added, 1 edited, 1 removed");
});

it("includes chapter links removed implicitly by retiring a concept", () => {
  const other = { ...mapping, id: "map-other", material_id: "mat-other" };
  expect(summarizeGraphChanges({ ...changes,
    operations: [{ op: "retire_node", node_id: "concept-one" }],
  }, [mapping, other], [])).toContain("Chapter connections: 0 added, 0 edited, 2 removed");
});

it("distinguishes unchanged mappings from an explicit empty replacement", () => {
  expect(summarizeGraphChanges(changes, [mapping], [])).toContain("Chapter connections: 0 added, 0 edited, 0 removed");
  expect(summarizeGraphChanges({ ...changes, replacement_mappings: [] }, [mapping], []))
    .toContain("Chapter connections: 0 added, 0 edited, 1 removed");
});

it("counts connections removed by retirement without double-counting an explicit removal", () => {
  const edge = { id: "edge-one", source_id: "concept-one", target_id: "concept-two",
    relation: "builds_on" as const, origin: "teacher" as const, curriculum_refs: [], material_refs: [] };
  expect(summarizeGraphChanges({ ...changes, operations: [
    { op: "remove_edge", edge_id: "edge-one" }, { op: "retire_node", node_id: "concept-one" },
  ] }, [], [edge, { ...edge, id: "edge-two", target_id: "concept-three" }]))
    .toContain("Concept connections: 0 added, 2 removed");
});
