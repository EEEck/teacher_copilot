// @vitest-environment happy-dom
import * as React from "react";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { CourseMaterialLibrary } from "./course-material-library";
import { courseApi } from "@/features/course-network/material-api";
import { client } from "@/lib/api";
import type { CourseDraft, ImportArtifact } from "@/features/course-network/material-types";

const row: CourseDraft<ImportArtifact> = { draft_id: "import-1", class_id: "chemie", status: "draft", artifact_revision: 1, artifact_hash: "hash", running: false,
  runtime: { stage: "document_review" }, review: null,
  artifact: { class_id: "chemie", material_id: "mat_chapter", title: "Catalysis", arm: "personal", source_filename: "chapter.pdf", source_hash: "source", sections: [{ id: "sec_a", title: "Activation", page_start: 1, page_end: 1, summary: "", content: "Activation energy", included: true }] } };
let root: Root;
let container: HTMLDivElement;
beforeEach(async () => {
  Object.assign(globalThis, { React, IS_REACT_ACT_ENVIRONMENT: true });
  vi.spyOn(courseApi, "list").mockResolvedValue({ materials: [] });
  vi.spyOn(client, "getCourseNetwork").mockResolvedValue({ class_id: "chemie", network: null });
  vi.spyOn(courseApi, "imports").mockResolvedValue({ drafts: [row] });
  vi.spyOn(courseApi, "changes").mockResolvedValue({ drafts: [] });
  vi.spyOn(courseApi, "import").mockResolvedValue(row);
  container = document.createElement("div"); document.body.appendChild(container); root = createRoot(container);
  await act(async () => root.render(createElement(CourseMaterialLibrary, { classId: "chemie" })));
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.restoreAllMocks(); });
const button = (text: string) => [...container.querySelectorAll("button")].find(b => b.textContent === text)!;

it("resumes extraction review and requires the exact accepted snapshot before approval", async () => {
  await act(async () => button("Catalysis · document review").click());
  expect(button("Approve chapter").disabled).toBe(true);
  vi.spyOn(courseApi, "importAction").mockResolvedValue({ ...row, review: { decision: "accept", summary: "Usable", findings: [], artifact_revision: 1, artifact_hash: "wrong" } });
  await act(async () => button("Review extraction").click());
  expect(button("Approve chapter").disabled).toBe(true);
  vi.mocked(courseApi.importAction).mockResolvedValue({ ...row, review: { decision: "accept", summary: "Usable", findings: [], artifact_revision: 1, artifact_hash: "hash" } });
  await act(async () => button("Review extraction").click());
  expect(button("Approve chapter").disabled).toBe(false);
  await act(async () => button("Exclude section").click());
  expect(button("Approve chapter").disabled).toBe(true);
  expect(button("Review extraction").disabled).toBe(true);
});

it("shows removals even when a replacement proposal has no mappings", async () => {
  const node = { id: "old-concept", title: "Existing concept", description: "", learning_goal: "", curriculum_refs: [], material_refs: [], origin: "teacher" as const, status: "adopted" as const };
  vi.mocked(client.getCourseNetwork).mockResolvedValue({ class_id: "chemie", network: { schema_version: 1, class_id: "chemie", revision: 1, route: { subject: "chemie", grade: 9, branch: "NTG" }, nodes: [node], edges: [], positions: {}, updated_at: "2026-09-04", material_mappings: [{ id: "old-map", material_id: "mat_chapter", section_id: "sec_a", node_id: node.id, relation: "explains", teacher_note: "Teacher link", origin: "teacher", confidence: null }] } });
  vi.mocked(courseApi.changes).mockResolvedValue({ drafts: [{ ...row, draft_id: "changes-1", artifact: { class_id: "chemie", base_revision: 1, summary: "Remove links", operations: [], material_id: "mat_chapter", replacement_mappings: [] } }] });
  await act(async () => root.render(createElement(CourseMaterialLibrary, { classId: "chemie-refreshed" })));
  expect(container.textContent).toContain("These existing connections will be removed");
  expect(container.textContent).toContain("Existing concept (explains)");
  expect(container.querySelector('[aria-label="Proposed changes"]')?.textContent).toContain("Chapter connections: 0 added, 0 edited, 1 removed");
});

it("summarizes actual changes and updates after rejection instead of repeating model claims", async () => {
  vi.mocked(courseApi.changes).mockResolvedValue({ drafts: [{ ...row, draft_id: "changes-1",
    artifact: { class_id: "chemie", base_revision: 1, summary: "Added three chapter links successfully",
      operations: [{ op: "update_node", node_id: "existing", changes: { title: "Clearer concept" } }],
      material_id: "mat_chapter", replacement_mappings: null },
    runtime: { generation: { coverage_notes: ["Every requested mapping is included"], rationales: [], warnings: [] } },
  }] });
  await act(async () => root.render(createElement(CourseMaterialLibrary, { classId: "chemie-summary" })));
  const summary = () => container.querySelector('[aria-label="Proposed changes"]')?.textContent;
  expect(summary()).toContain("Concepts: 0 added, 1 edited, 0 retired");
  expect(summary()).toContain("Chapter connections: 0 added, 0 edited, 0 removed");
  expect(container.textContent).not.toContain("Added three chapter links successfully");
  expect(container.textContent).not.toContain("Every requested mapping is included");
  await act(async () => button("Reject this change").click());
  expect(summary()).toContain("Concepts: 0 added, 0 edited, 0 retired");
  expect(button("Approve map changes").disabled).toBe(true);
});

it("lets the teacher retry a failed generation without losing the approved chapter", async () => {
  vi.mocked(courseApi.list).mockResolvedValue({ materials: [row.artifact] });
  vi.spyOn(courseApi, "generate").mockRejectedValueOnce(new Error("Could not generate a usable map proposal. Try again. Your course map has not changed."));
  await act(async () => root.render(createElement(CourseMaterialLibrary, { classId: "chemie-retry" })));
  await act(async () => button("Connect to course map").click());
  expect(container.textContent).toContain("Try again. Your course map has not changed.");
  expect(button("Connect to course map").disabled).toBe(false);
  expect(container.textContent).toContain("Catalysis");
  vi.mocked(courseApi.generate).mockResolvedValue({ ...row, artifact: { class_id: "chemie", base_revision: 1,
    summary: "Clarify", operations: [], material_id: "mat_chapter", replacement_mappings: [] } });
  vi.mocked(client.getCourseNetwork).mockResolvedValue({ class_id: "chemie", network: { schema_version: 1,
    class_id: "chemie", revision: 1, route: { subject: "chemie", grade: 9, branch: "NTG" },
    nodes: [], edges: [], material_mappings: [], positions: {}, updated_at: "2026-09-05" } });
  await act(async () => button("Connect to course map").click());
  expect(container.textContent).toContain("Review map changes");
  expect(container.textContent).not.toContain("Try again. Your course map has not changed.");
  expect(button("Approve map changes").disabled).toBe(true);
});
