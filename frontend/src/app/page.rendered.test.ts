// @vitest-environment happy-dom
import * as React from "react";
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import HomePage from "./page";
import { client } from "@/lib/api";

vi.mock("@/components/klassenpilot/home-landing", () => ({ HomeLanding: () => null }));

it("clears an earlier loading error after creating a class and refreshing the list", async () => {
  Object.assign(globalThis, { React, IS_REACT_ACT_ENVIRONMENT: true });
  const created = { id: "chemie_8a", label: "My own class", subject: "chemie" };
  vi.spyOn(client, "getClasses").mockRejectedValueOnce(new Error("Temporary outage")).mockResolvedValue({ classes: [created] });
  vi.spyOn(client, "getCurriculumRoutes").mockResolvedValue({ routes: [{ subject: "chemie", grade: 8, branch: "NTG" }] });
  vi.spyOn(client, "createClass").mockResolvedValue(created);
  const container = document.createElement("div"); document.body.appendChild(container);
  const root = createRoot(container);
  try {
    await act(async () => root.render(createElement(HomePage)));
    expect(container.textContent).toContain("Temporary outage");
    await act(async () => [...container.querySelectorAll("button")].find(button => button.textContent === "New class")!.click());
    await act(async () => container.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
    expect(container.textContent).toContain("My own class");
    expect(container.textContent).not.toContain("Temporary outage");
    expect(container.textContent).not.toContain("Backend not reachable");
  } finally {
    await act(async () => root.unmount()); container.remove(); vi.restoreAllMocks();
  }
});
