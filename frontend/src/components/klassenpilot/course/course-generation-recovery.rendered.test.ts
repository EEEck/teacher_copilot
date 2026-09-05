// @vitest-environment happy-dom
import * as React from "react";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { CourseMaterialLibrary } from "./course-material-library";
import { courseApi } from "@/features/course-network/material-api";
import { client } from "@/lib/api";
import type { CourseDraft, GraphChanges } from "@/features/course-network/material-types";

const pending: CourseDraft<unknown> = {
  draft_id: "saved-job", class_id: "chemie", status: "draft", artifact_revision: 0,
  artifact_hash: "saved-input", artifact: { request: { purpose: "correction", teacher_request: "Saved original request" } },
  runtime: { stage: "generating" }, running: true, review: null,
};
const edit: CourseDraft<GraphChanges> = {
  ...pending, draft_id: "generated-edit", artifact_revision: 1, artifact_hash: "changes", running: false,
  runtime: {}, artifact: { class_id: "chemie", base_revision: 1, summary: "Clarify", operations: [], material_id: null, replacement_mappings: null },
};
let root: Root;
let container: HTMLDivElement;
beforeEach(() => {
  Object.assign(globalThis, { React, IS_REACT_ACT_ENVIRONMENT: true });
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  vi.spyOn(courseApi, "list").mockResolvedValue({ materials: [] });
  vi.spyOn(courseApi, "imports").mockResolvedValue({ drafts: [] });
  vi.spyOn(courseApi, "changes").mockResolvedValue({ drafts: [], generation: pending });
  vi.spyOn(client, "getCourseNetwork").mockResolvedValue({ class_id: "chemie", network: null });
  vi.spyOn(courseApi, "retryGeneration").mockResolvedValue(edit);
  vi.spyOn(courseApi, "generate").mockResolvedValue(edit);
  container = document.createElement("div"); document.body.appendChild(container); root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount()); container.remove(); vi.restoreAllMocks(); vi.useRealTimers();
});
async function mount() { await act(async () => root.render(createElement(CourseMaterialLibrary, { classId: "chemie" }))); }
const button = (label: string) => [...container.querySelectorAll("button")].find(item => item.textContent === label)!;

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

it("shows an initial request immediately, polls while waiting, and exposes its saved failure without reopening", async () => {
  vi.mocked(courseApi.changes).mockResolvedValue({ drafts: [], generation: null });
  vi.mocked(courseApi.list).mockResolvedValue({ materials: [{ material_id: "chapter", title: "Chapter", sections: [] } as never] });
  const request = deferred<CourseDraft<GraphChanges>>();
  vi.mocked(courseApi.generate).mockReturnValue(request.promise);
  await mount();
  await act(async () => button("Connect to course map").click());
  expect(container.querySelector('[role="status"]')?.textContent).toContain("Generating a map proposal");
  vi.mocked(courseApi.changes).mockResolvedValue({ drafts: [], generation: pending });
  await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
  expect(courseApi.changes).toHaveBeenCalledTimes(2);
  vi.mocked(courseApi.changes).mockResolvedValue({ drafts: [], generation: { ...pending, running: false, runtime: { stage: "failed", error: "Saved failure" } } });
  await act(async () => request.reject(new Error("Could not generate")));
  expect(button("Retry saved map request")).toBeDefined();
  expect(container.textContent).toContain("Saved failure");
  expect(container.querySelector('[role="status"]')).toBeNull();
});

it("shows retry progress immediately instead of the old failure", async () => {
  vi.mocked(courseApi.changes).mockResolvedValue({ drafts: [], generation: { ...pending, running: false, runtime: { stage: "failed", error: "Old failure" } } });
  const request = deferred<CourseDraft<GraphChanges>>();
  vi.mocked(courseApi.retryGeneration).mockReturnValue(request.promise);
  await mount();
  await act(async () => button("Retry saved map request").click());
  expect(container.querySelector('[role="status"]')?.textContent).toContain("Generating a map proposal");
  expect(container.textContent).not.toContain("Old failure");
  vi.mocked(courseApi.changes).mockResolvedValue({ drafts: [edit], generation: null });
  await act(async () => request.resolve(edit));
  expect(container.textContent).toContain("Review map changes");
});

it("prevents a new chapter generation while a saved request is running", async () => {
  vi.mocked(courseApi.list).mockResolvedValue({ materials: [{ material_id: "chapter", title: "Chapter", sections: [] } as never] });
  await mount();
  expect(button("Connect to course map").disabled).toBe(true);
});

it("shows correction progress immediately and preserves edits first recovered by polling", async () => {
  vi.mocked(courseApi.changes).mockResolvedValue({ drafts: [], generation: null });
  vi.mocked(client.getCourseNetwork).mockResolvedValue({ class_id: "chemie", network: {
    schema_version: 1, class_id: "chemie", revision: 1, route: { subject: "chemie", grade: 9, branch: "NTG" },
    nodes: [{ id: "one", title: "Concept", description: "", learning_goal: "", curriculum_refs: [], material_refs: [], origin: "teacher", status: "adopted" }],
    edges: [], material_mappings: [], positions: {}, updated_at: "2026-09-05",
  } });
  const request = deferred<CourseDraft<GraphChanges>>();
  vi.spyOn(courseApi, "correct").mockReturnValue(request.promise);
  await mount();
  const textarea = container.querySelector<HTMLTextAreaElement>("#course-correction")!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(textarea, "Clarify the concept");
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => button("Suggest correction").click());
  expect(courseApi.correct).toHaveBeenCalledExactlyOnceWith("chemie", "Clarify the concept");
  expect(container.querySelector('[role="status"]')?.textContent).toContain("Generating a map proposal");
  const proposal = { ...edit, artifact: { ...edit.artifact, operations: [
    { op: "update_node" as const, node_id: "one", changes: { title: "Clearer concept" } },
  ] } };
  vi.mocked(courseApi.changes).mockResolvedValue({ drafts: [proposal], generation: null });
  await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
  await act(async () => button("Reject this change").click());
  await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
  expect(container.querySelector('[aria-label="Proposed changes"]')?.textContent).toContain("0 edited");
  await act(async () => request.resolve(proposal));
  expect(container.querySelector('[aria-label="Proposed changes"]')?.textContent).toContain("0 edited");
  expect(button("Save map corrections").disabled).toBe(false);
});

it("resumes a persisted pending job and polls for its normal edit without starting another model call", async () => {
  await mount();
  expect(container.textContent).toContain("Generating a map proposal");
  expect(container.textContent).toContain("You can leave and return");
  expect(courseApi.generate).not.toHaveBeenCalled();
  expect(courseApi.retryGeneration).not.toHaveBeenCalled();
  vi.mocked(courseApi.changes).mockResolvedValue({ drafts: [edit], generation: null });
  await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
  expect(container.textContent).toContain("Review map changes");
  expect(container.textContent).not.toContain("Generating a map proposal");
  expect(courseApi.retryGeneration).not.toHaveBeenCalled();
});

it("shows the saved failure on reopen and retries only after the teacher selects retry", async () => {
  vi.mocked(courseApi.changes).mockResolvedValue({ drafts: [], generation: {
    ...pending, running: false, runtime: { stage: "failed", error: "Generation was interrupted. Retry the saved request." },
  } });
  await mount();
  expect(container.textContent).toContain("Generation was interrupted");
  expect(courseApi.retryGeneration).not.toHaveBeenCalled();
  vi.mocked(courseApi.changes).mockResolvedValue({ drafts: [edit], generation: null });
  await act(async () => button("Retry saved map request").click());
  expect(courseApi.retryGeneration).toHaveBeenCalledExactlyOnceWith("chemie");
  expect(container.textContent).toContain("Review map changes");
  expect(container.textContent).not.toContain("Generation was interrupted");
  expect(courseApi.generate).not.toHaveBeenCalled();
});
