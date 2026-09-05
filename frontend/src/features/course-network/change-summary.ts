import type { GraphChanges } from "./material-types";
import type { MaterialMapping, NetworkEdge } from "./types";

/** Describe the editable proposal itself, never model claims about completed work. */
export function summarizeGraphChanges(changes: GraphChanges, existing: MaterialMapping[], edges: NetworkEdge[]): string {
  const count = (op: GraphChanges["operations"][number]["op"]) => changes.operations.filter(item => item.op === op).length;
  const retired = new Set(changes.operations.flatMap(item => item.op === "retire_node" ? [item.node_id] : []));
  const removedEdges = new Set(changes.operations.flatMap(item => item.op === "remove_edge" ? [item.edge_id] : []));
  for (const edge of edges) {
    if (retired.has(edge.source_id) || retired.has(edge.target_id)) removedEdges.add(edge.id);
  }
  const proposed = (changes.replacement_mappings == null ? existing : [
    ...existing.filter(item => item.material_id !== changes.material_id),
    ...changes.replacement_mappings,
  ]).filter(item => !retired.has(item.node_id));
  const before = new Map(existing.map(item => [item.id, item]));
  const after = new Map(proposed.map(item => [item.id, item]));
  const fields = ["material_id", "section_id", "node_id", "relation", "teacher_note", "origin", "confidence"] as const;
  const added = proposed.filter(item => !before.has(item.id)).length;
  const removed = existing.filter(item => !after.has(item.id)).length;
  const edited = proposed.filter(item => {
    const old = before.get(item.id);
    return old && fields.some(field => (old[field] ?? null) !== (item[field] ?? null));
  }).length;
  return `Concepts: ${count("add_node")} added, ${count("update_node")} edited, ${count("retire_node")} retired. `
    + `Concept connections: ${count("add_edge")} added, ${removedEdges.size} removed. `
    + `Chapter connections: ${added} added, ${edited} edited, ${removed} removed.`
    + (retired.size ? " Retiring a concept also removes its concept connections." : "");
}
