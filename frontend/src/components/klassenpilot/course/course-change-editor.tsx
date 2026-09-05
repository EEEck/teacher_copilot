"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { GraphChanges, GraphOperation } from "@/features/course-network/material-types";
import type { LearningBlock, NetworkEdge } from "@/features/course-network/types";

export function CourseChangeEditor({ changes, nodes, onChange }: {
  changes: GraphChanges; nodes: LearningBlock[]; onChange: (changes: GraphChanges) => void;
}) {
  const concepts = [...nodes, ...changes.operations.flatMap(op => op.op === "add_node" ? [op.node] : [])];
  const title = (id: string) => concepts.find(n => n.id === id)?.title || id;
  const replace = (index: number, operation: GraphOperation) => onChange({ ...changes, operations: changes.operations.map((op, i) => i === index ? operation : op) });
  const reject = (index: number) => {
    const rejected = changes.operations[index];
    const id = rejected.op === "add_node" ? rejected.node.id : null;
    onChange({ ...changes,
      operations: changes.operations.filter((op, i) => i !== index && (!id || !(op.op === "add_edge" && [op.edge.source_id, op.edge.target_id].includes(id)) && !("node_id" in op && op.node_id === id))),
      replacement_mappings: id ? changes.replacement_mappings?.filter(m => m.node_id !== id) ?? null : changes.replacement_mappings,
    });
  };
  return <div className="space-y-3">{changes.operations.map((operation, index) => {
    const node = operation.op === "add_node" ? operation.node : operation.op === "update_node" ? { ...concepts.find(n => n.id === operation.node_id), ...Object.fromEntries(Object.entries(operation.changes).filter(([, value]) => value != null)) } : null;
    const editNode = (field: "title" | "description" | "learning_goal", value: string) => {
      if (operation.op === "add_node") replace(index, { ...operation, node: { ...operation.node, [field]: value, origin: "teacher" } });
      if (operation.op === "update_node") replace(index, { ...operation, changes: { ...operation.changes, [field]: value } });
    };
    const edge = operation.op === "add_edge" ? operation.edge : null;
    const editEdge = (patch: Partial<NetworkEdge>) => { if (edge) replace(index, { op: "add_edge", edge: { ...edge, ...patch, origin: "teacher" } }); };
    return <fieldset key={index} className="space-y-2 rounded-lg border border-border p-3">
      <legend className="px-1 text-sm">{operation.op === "update_node" ? `Update concept: ${title(operation.node_id)}` : operation.op.replaceAll("_", " ")}</legend>
      {node && <>
        <Label htmlFor={`concept-title-${index}`}>Concept title</Label><Input id={`concept-title-${index}`} value={node.title || ""} onChange={e => editNode("title", e.target.value)} />
        <Label htmlFor={`concept-goal-${index}`}>Learning goal</Label><Textarea id={`concept-goal-${index}`} aria-label="Learning goal" value={node.learning_goal || ""} onChange={e => editNode("learning_goal", e.target.value)} />
        <Label htmlFor={`concept-description-${index}`}>Description</Label><Textarea id={`concept-description-${index}`} value={node.description || ""} onChange={e => editNode("description", e.target.value)} />
        <p className="text-sm text-muted-foreground">Sources: {[...(node.curriculum_refs || []).map(r => `${r.source_id}/${r.section_id}`), ...(node.material_refs || []).map(r => `${r.material_id}/${r.section_id}`)].join(", ") || "Review the proposal's source support before approving."}</p>
      </>}
      {edge && <>
        <p>{title(edge.source_id)} {edge.relation === "builds_on" ? "requires" : "is related to"} {title(edge.target_id)}</p>
        {(["source_id", "target_id"] as const).map(field => <div key={field}><Label>{field === "source_id" ? "Concept" : "Connected concept"}</Label><Select value={edge[field]} onValueChange={value => editEdge({ [field]: value })}><SelectTrigger aria-label={field === "source_id" ? "Concept" : "Connected concept"}><SelectValue /></SelectTrigger><SelectContent>{concepts.map(n => <SelectItem key={n.id} value={n.id}>{n.title}</SelectItem>)}</SelectContent></Select></div>)}
        <Label>Relationship</Label><Select value={edge.relation} onValueChange={value => editEdge({ relation: value as NetworkEdge["relation"] })}><SelectTrigger aria-label="Relationship"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="builds_on">Requires prerequisite</SelectItem><SelectItem value="related_to">Related content</SelectItem></SelectContent></Select>
        {edge.relation === "builds_on" && <Button variant="outline" onClick={() => editEdge({ source_id: edge.target_id, target_id: edge.source_id })}>Reverse prerequisite</Button>}
      </>}
      {operation.op === "retire_node" && <p>Retire {title(operation.node_id)}</p>}
      {operation.op === "remove_edge" && <p>Remove connection {operation.edge_id}</p>}
      {operation.op === "add_node" && <p className="text-sm text-muted-foreground">Rejecting this concept also removes its dependent proposed connections and material mappings.</p>}
      <Button variant="ghost" onClick={() => reject(index)}>Reject this change</Button>
    </fieldset>;
  })}</div>;
}
