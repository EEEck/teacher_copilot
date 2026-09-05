// @vitest-environment happy-dom
import * as React from "react";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { CreateClassCard } from "./create-class-card";
import { client } from "@/lib/api";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
let root: Root;
let container: HTMLDivElement;
beforeEach(async () => {
  Object.assign(globalThis, { React, IS_REACT_ACT_ENVIRONMENT: true });
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2029, 8, 5));
  vi.spyOn(client, "getCurriculumRoutes").mockResolvedValue({ routes: [{ subject: "chemie", grade: 8, branch: "NTG" }] });
  vi.spyOn(client, "createClass").mockResolvedValue({ id: "chemie_8c_2029_30", label: "My own class", subject: "chemie" });
  container = document.createElement("div"); document.body.appendChild(container); root = createRoot(container);
  await act(async () => root.render(createElement(CreateClassCard)));
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.restoreAllMocks(); vi.useRealTimers(); });
const input = (id: string) => container.querySelector<HTMLInputElement>(`#${id}`)!;
async function change(id: string, value: string) {
  const element = input(id);
  expect(element).not.toBeNull();
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(element, value);
    element.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
async function submit() {
  await act(async () => container.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
}

it("derives the school year from the date and lets the teacher submit a label without a roster", async () => {
  expect(input("new-class-year").value).toBe("2029_30");
  await change("new-class-label", "My own class");
  await change("new-class-section", "c");
  await change("new-class-year", "2030/31");
  await submit();
  expect(client.createClass).toHaveBeenCalledWith(expect.objectContaining({ label: "My own class", section: "c", school_year: "2030/31", student_names: [] }));
  expect(container.textContent).toContain("No taught lessons yet");
  expect(container.querySelector('a[href="/classes/chemie_8c_2029_30/course"]')?.textContent).toContain("Course");
  expect(container.querySelector('a[href="/classes/chemie_8c_2029_30/course/materials"]')?.textContent).toContain("Materials");
});

it("uses the previous starting year before the September school-year boundary", async () => {
  vi.setSystemTime(new Date(2030, 6, 1));
  await act(async () => root.render(createElement(CreateClassCard, { key: "summer" })));
  expect(input("new-class-year").value).toBe("2029_30");
});

it("keeps entered values and gives a usable duplicate recovery instruction", async () => {
  vi.mocked(client.createClass).mockRejectedValue(new Error("API 409: Class 'chemie_8a_2029_30' already exists."));
  await submit();
  expect(container.textContent).toContain("Change the section or school year");
  expect(input("new-class-section").value).toBe("a");
  expect(container.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(false);
});

it("does not offer unsupported subjects and explains the supported route", async () => {
  vi.mocked(client.getCurriculumRoutes).mockResolvedValue({ routes: [{ subject: "physik", grade: 8, branch: "NTG" }] });
  await act(async () => root.render(createElement(CreateClassCard, { key: "unsupported" })));
  expect(container.textContent).toContain("Chemie 8 or 9 NTG");
  expect(container.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(true);
});

it("explains how to recover when the chosen route is no longer supported", async () => {
  vi.mocked(client.createClass).mockRejectedValue(new Error("No shared teaching framework covers chemie grade 8 NTG. Add the shared framework before creating classes on this route."));
  await submit();
  expect(container.textContent).toContain("Choose an available Chemie 8 or 9 NTG route");
  expect(container.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(false);
});
