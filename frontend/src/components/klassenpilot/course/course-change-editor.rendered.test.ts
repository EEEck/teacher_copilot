// @vitest-environment happy-dom
import * as React from "react";
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { expect, it } from "vitest";
import { CourseChangeEditor } from "./course-change-editor";
import type { GraphChanges } from "@/features/course-network/material-types";
import type { LearningBlock } from "@/features/course-network/types";

it("reverses prerequisite direction and removes dependent suggestions when a new concept is rejected", async () => {
  Object.assign(globalThis, { React, IS_REACT_ACT_ENVIRONMENT: true });
  const node: LearningBlock = { id: "catalysis", title: "Catalysis", learning_goal: "Explain catalysis", description: "An alternative path", curriculum_refs: [], material_refs: [], origin: "material", status: "proposed" };
  const current: LearningBlock = { ...node, id: "activation", title: "Activation energy", status: "adopted" };
  let changes: GraphChanges = { class_id: "chemie", base_revision: 1, summary: "", material_id: "mat_chapter", replacement_mappings: [{ id: "map1", material_id: "mat_chapter", section_id: "sec_a", node_id: "catalysis", relation: "explains", origin: "agent", teacher_note: "", confidence: null }], operations: [
    { op: "add_node", node }, { op: "add_edge", edge: { id: "prereq", source_id: "activation", target_id: "catalysis", relation: "builds_on", origin: "material", curriculum_refs: [], material_refs: [] } },
  ] };
  const container = document.createElement("div"); document.body.append(container);
  const root = createRoot(container);
  const render = () => root.render(createElement(CourseChangeEditor, { changes, nodes: [current], onChange: next => { changes = next; render(); } }));
  try {
    await act(async () => render());
    expect(container.querySelector('textarea[aria-label="Learning goal"]')).not.toBeNull();
    const reverse = [...container.querySelectorAll("button")].find(b => b.textContent === "Reverse prerequisite")!;
    await act(async () => reverse.click());
    expect(container.textContent).toContain("Catalysis requires Activation energy");
    expect(changes.operations[1]).toMatchObject({ edge: { source_id: "catalysis", target_id: "activation" } });
    const reject = [...container.querySelectorAll("button")].find(b => b.textContent === "Reject this change")!;
    await act(async () => reject.click());
    expect(changes.operations).toEqual([]);
    expect(changes.replacement_mappings).toEqual([]);
  } finally { await act(async () => root.unmount()); container.remove(); }
});

it("identifies a description-only update and displays current fields without adding them to the patch", async () => {
  Object.assign(globalThis, { React, IS_REACT_ACT_ENVIRONMENT: true });
  const current: LearningBlock = { id: "catalysis", title: "Catalysis", learning_goal: "Explain catalysis", description: "Original description", curriculum_refs: [], material_refs: [], origin: "teacher", status: "adopted" };
  let changes = JSON.parse(JSON.stringify({ class_id: "chemie", base_revision: 1, summary: "", material_id: null, replacement_mappings: null, operations: [{ op: "update_node", node_id: "catalysis", changes: { title: null, learning_goal: null, description: "Proposed description", curriculum_refs: null, material_refs: null } }] })) as GraphChanges;
  const container = document.createElement("div"); document.body.append(container);
  const root = createRoot(container);
  const render = () => root.render(createElement(CourseChangeEditor, { changes, nodes: [current], onChange: next => { changes = next; render(); } }));
  try {
    await act(async () => render());
    expect(container.querySelector("legend")?.textContent).toBe("Update concept: Catalysis");
    expect((container.querySelector("#concept-title-0") as HTMLInputElement).value).toBe("Catalysis");
    expect((container.querySelector("#concept-goal-0") as HTMLTextAreaElement).value).toBe("Explain catalysis");
    const description = container.querySelector("#concept-description-0") as HTMLTextAreaElement;
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(description, "Teacher correction");
      description.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(changes.operations[0]).toEqual({ op: "update_node", node_id: "catalysis", changes: { title: null, learning_goal: null, description: "Teacher correction", curriculum_refs: null, material_refs: null } });
  } finally { await act(async () => root.unmount()); container.remove(); }
});
