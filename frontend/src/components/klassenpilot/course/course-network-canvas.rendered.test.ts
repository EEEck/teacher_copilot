// @vitest-environment happy-dom

import * as React from "react";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CourseNetworkCanvas } from "./course-network-canvas";
import type { CourseNetwork } from "@/features/course-network/types";

const NETWORK: CourseNetwork = {
  schema_version: 1,
  class_id: "chemie_9b_2026_27",
  route: { subject: "chemie", grade: 9, branch: "NTG" },
  revision: 1,
  nodes: [
    {
      id: "redox",
      title: "Redox reactions",
      description: "Explain electron transfer.",
      learning_goal: "Identify donor and acceptor roles.",
      curriculum_refs: [],
      material_refs: [],
      origin: "curriculum",
      status: "adopted",
    },
    {
      id: "catalysis",
      title: "Katalyse",
      description: "Compare catalyzed and uncatalyzed pathways.",
      learning_goal: "Explain how catalysts change activation energy.",
      curriculum_refs: [],
      material_refs: [],
      origin: "curriculum",
      status: "adopted",
    },
  ],
  edges: [],
  material_mappings: [],
  positions: {
    redox: { x: 0, y: 0 },
    catalysis: { x: 320, y: 0 },
  },
  updated_at: "2026-08-18T00:00:00Z",
};

class ResizeObserverStub implements ResizeObserver {
  constructor(private readonly callback: ResizeObserverCallback) {}

  observe(target: Element): void {
    this.callback(
      [
        {
          target,
          contentRect: target.getBoundingClientRect(),
        } as ResizeObserverEntry,
      ],
      this,
    );
  }

  disconnect(): void {}
  unobserve(): void {}
}

let mountedRoots: Root[] = [];

async function mount(element: React.ReactElement): Promise<HTMLElement> {
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  mountedRoots.push(root);
  await act(async () => {
    root.render(element);
  });
  return container;
}

async function click(element: Element): Promise<void> {
  await act(async () => {
    element.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
    element.dispatchEvent(
      new MouseEvent("mousedown", { bubbles: true, view: window }),
    );
    element.dispatchEvent(new PointerEvent("pointerup", { bubbles: true }));
    element.dispatchEvent(
      new MouseEvent("mouseup", { bubbles: true, view: window }),
    );
    element.dispatchEvent(
      new MouseEvent("click", { bubbles: true, view: window }),
    );
  });
}

function selectionHarness(onSelection: (nodeId: string | null) => void) {
  function SelectionHarness() {
    const [selectedId, setSelectedId] = React.useState<string | null>(null);
    return createElement(
      React.Fragment,
      null,
      createElement(
        "button",
        { type: "button", onClick: () => setSelectedId("catalysis") },
        "Select Katalyse from inspector",
      ),
      createElement("output", null, selectedId ?? "none"),
      createElement(CourseNetworkCanvas, {
        network: NETWORK,
        selectedId,
        onSelect: (nodeId) => {
          onSelection(nodeId);
          setSelectedId(nodeId);
        },
      }),
    );
  }

  return createElement(SelectionHarness);
}

describe("CourseNetworkCanvas selection", () => {
  beforeEach(() => {
    vi.stubGlobal("React", React);
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    vi.stubGlobal("ResizeObserver", ResizeObserverStub);
    mountedRoots = [];
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(
      new DOMRect(0, 0, 800, 600),
    );
  });

  afterEach(async () => {
    await act(async () => {
      for (const root of mountedRoots) root.unmount();
    });
    document.body.replaceChildren();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("reports one parent selection for an actual React Flow node click", async () => {
    const selections = vi.fn<(nodeId: string | null) => void>();
    const container = await mount(selectionHarness(selections));
    const catalysis = container.querySelector(
      'article[aria-label="Lernbaustein: Katalyse"]',
    );
    expect(catalysis).not.toBeNull();

    await click(catalysis!);

    expect(container.querySelector("output")?.textContent).toBe("catalysis");
    expect(selections.mock.calls).toEqual([["catalysis"]]);
    expect(catalysis?.className).toContain("ring-2");
  });

  it("keeps keyboard node selection synchronized with the parent inspector state", async () => {
    const selections = vi.fn<(nodeId: string | null) => void>();
    const container = await mount(selectionHarness(selections));
    const catalysis = container.querySelector('[data-testid="rf__node-catalysis"]');
    expect(catalysis).not.toBeNull();

    await act(async () => {
      catalysis!.dispatchEvent(
        new KeyboardEvent("keydown", { bubbles: true, key: "Enter" }),
      );
    });

    expect(container.querySelector("output")?.textContent).toBe("catalysis");
    expect(selections.mock.calls).toEqual([["catalysis"]]);
  });

  it("emphasizes the node selected by the parent inspector without a Flow selection callback", async () => {
    const selections = vi.fn<(nodeId: string | null) => void>();
    const container = await mount(selectionHarness(selections));
    const catalysis = container.querySelector(
      'article[aria-label="Lernbaustein: Katalyse"]',
    );
    const inspectorSelection = [...container.querySelectorAll("button")].find(
      (button) => button.textContent === "Select Katalyse from inspector",
    );

    expect(catalysis?.className).not.toContain("ring-2");
    expect(inspectorSelection).toBeInstanceOf(HTMLButtonElement);
    await click(inspectorSelection!);

    expect(catalysis?.className).toContain("ring-2");
    expect(selections).not.toHaveBeenCalled();
  });
});
