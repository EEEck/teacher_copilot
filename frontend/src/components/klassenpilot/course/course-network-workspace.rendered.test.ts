// @vitest-environment happy-dom

import * as React from "react";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CourseNetworkWorkspace } from "./course-network-workspace";
import {
  CurriculumSourceLinks,
  LearningBlockInspector,
} from "./learning-block-inspector";
import type { CourseNetwork } from "@/features/course-network/types";
import {
  client,
  type CourseNetworkDraftResponse,
  type CourseNetworkSourceSectionResponse,
} from "@/lib/api";

const navigation = vi.hoisted(() => ({
  router: {
    push: vi.fn(),
    refresh: vi.fn(),
    replace: vi.fn(),
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => navigation.router,
}));

vi.mock("next/dynamic", () => ({
  default: () => () => null,
}));

const CLASS_ID = "chemie_9b_2026_27";

const PROPOSED_NETWORK: CourseNetwork = {
  schema_version: 1,
  class_id: CLASS_ID,
  route: { subject: "chemie", grade: 9, branch: "NTG" },
  revision: 0,
  nodes: [
    {
      id: "redox",
      title: "Redox reactions",
      description: "Use electron transfer to explain reactions.",
      learning_goal: "Explain donor and acceptor roles.",
      curriculum_refs: [
        {
          source_id: "by-lehrplanplus-chemie-9-ntg",
          section_id: "c9_ionen_redox",
        },
      ],
      material_refs: [],
      origin: "curriculum",
      status: "proposed",
    },
  ],
  edges: [],
  material_mappings: [],
  positions: { redox: { x: 0, y: 0 } },
  updated_at: "2026-08-18T00:00:00Z",
};

const ACCEPTED_DRAFT: CourseNetworkDraftResponse = {
  draft_id: "draft-9b",
  class_id: CLASS_ID,
  status: "draft",
  artifact_markdown: "{}",
  artifact_revision: 4,
  artifact_hash: "sha256:exact",
  backend_session_id: "session-9b",
  network: PROPOSED_NETWORK,
  review: {
    decision: "accept",
    summary: "Ready to adopt.",
    findings: [],
    artifact_revision: 4,
    artifact_hash: "sha256:exact",
    deterministic: false,
  },
};

const ADOPTED_NETWORK: CourseNetwork = {
  ...PROPOSED_NETWORK,
  revision: 1,
  nodes: PROPOSED_NETWORK.nodes.map((node) => ({
    ...node,
    status: "adopted" as const,
  })),
};

const SOURCE_SECTION: CourseNetworkSourceSectionResponse = {
  source_id: "by-lehrplanplus-chemie-9-ntg",
  source_title: "LehrplanPLUS Chemie 9 NTG",
  section_id: "c9_ionen_redox",
  section_title: "Donator-Akzeptor-Konzept (Ionen und Redox)",
  content: "Students explain ion formation through electron transfer.",
  provenance: {
    authority: "official_curriculum",
    jurisdiction: "BY",
    canonical_url:
      "https://www.lehrplanplus.bayern.de/fachlehrplan/gymnasium/9/chemie/ch-ntg",
    retrieved_at: "2026-07-18",
    version_label: "current_snapshot",
    content_hash: "sha256:genuine",
  },
};

const CATALYSIS_NODE: CourseNetwork["nodes"][number] = {
  ...PROPOSED_NETWORK.nodes[0]!,
  id: "catalysis",
  title: "Katalyse",
  curriculum_refs: [
    {
      source_id: "by-lehrplanplus-chemie-9-ntg",
      section_id: "c9_katalyse",
    },
  ],
};

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

async function settle(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

function buttonNamed(container: ParentNode, label: string): HTMLButtonElement {
  const button = [...container.querySelectorAll("button")].find((candidate) =>
    candidate.textContent?.includes(label),
  );
  if (!(button instanceof HTMLButtonElement)) {
    throw new Error(`Button not found: ${label}`);
  }
  return button;
}

async function click(button: HTMLButtonElement): Promise<void> {
  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
}

describe("course network source evidence", () => {
  beforeEach(() => {
    vi.stubGlobal("React", React);
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    mountedRoots = [];
  });

  afterEach(async () => {
    await act(async () => {
      for (const root of mountedRoots) root.unmount();
    });
    document.body.replaceChildren();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("loads and renders the exact section body and provenance", async () => {
    let resolveSource!: (source: CourseNetworkSourceSectionResponse) => void;
    const getSource = vi
      .spyOn(client, "getCourseNetworkSourceSection")
      .mockReturnValue(
        new Promise((resolve) => {
          resolveSource = resolve;
        }),
      );
    const container = await mount(
      createElement(CurriculumSourceLinks, {
        classId: CLASS_ID,
        references: [
          {
            source_id: SOURCE_SECTION.source_id,
            section_id: SOURCE_SECTION.section_id,
          },
        ],
      }),
    );

    await click(buttonNamed(container, "c9_ionen_redox"));
    expect(container.textContent).toContain("Loading curriculum source section");

    resolveSource(SOURCE_SECTION);
    await settle();

    expect(getSource).toHaveBeenCalledWith(
      CLASS_ID,
      SOURCE_SECTION.source_id,
      SOURCE_SECTION.section_id,
    );
    expect(container.textContent).toContain(SOURCE_SECTION.section_title);
    expect(container.textContent).toContain(SOURCE_SECTION.content);
    expect(container.textContent).toContain("official_curriculum");
    expect(container.textContent).toContain("2026-07-18");
    expect(container.querySelector('a[href^="https://www.lehrplanplus"]')).not.toBeNull();
  });

  it("shows a recoverable error when the authorized section cannot be loaded", async () => {
    vi.spyOn(client, "getCourseNetworkSourceSection").mockRejectedValue(
      new Error("Source service unavailable"),
    );
    const container = await mount(
      createElement(CurriculumSourceLinks, {
        classId: CLASS_ID,
        references: [
          {
            source_id: SOURCE_SECTION.source_id,
            section_id: SOURCE_SECTION.section_id,
          },
        ],
      }),
    );

    await click(buttonNamed(container, "c9_ionen_redox"));
    await settle();

    expect(container.textContent).toContain("Source service unavailable");
    expect(buttonNamed(container, "Try again").disabled).toBe(false);
  });

  it("clears inspected source evidence when the selected learning block changes", async () => {
    vi.spyOn(client, "getCourseNetworkSourceSection").mockResolvedValue(
      SOURCE_SECTION,
    );

    function InspectorHarness() {
      const [selectedId, setSelectedId] = React.useState("redox");
      return createElement(
        React.Fragment,
        null,
        createElement(
          "button",
          { type: "button", onClick: () => setSelectedId(CATALYSIS_NODE.id) },
          "Select Katalyse",
        ),
        createElement(LearningBlockInspector, {
          classId: CLASS_ID,
          nodes: [PROPOSED_NETWORK.nodes[0]!, CATALYSIS_NODE],
          edges: [],
          selectedId,
          onSelect: setSelectedId,
        }),
      );
    }

    const container = await mount(createElement(InspectorHarness));
    await click(buttonNamed(container, SOURCE_SECTION.section_id));
    await settle();
    expect(container.textContent).toContain(SOURCE_SECTION.content);

    await click(buttonNamed(container, "Select Katalyse"));

    expect(container.textContent).toContain("c9_katalyse");
    expect(container.textContent).not.toContain(SOURCE_SECTION.content);
  });
});

describe("course network workspace live states", () => {
  beforeEach(() => {
    vi.stubGlobal("React", React);
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    mountedRoots = [];
    navigation.router.push.mockReset();
    navigation.router.refresh.mockReset();
    navigation.router.replace.mockReset();
  });

  afterEach(async () => {
    await act(async () => {
      for (const root of mountedRoots) root.unmount();
    });
    document.body.replaceChildren();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("reconciles an uncertain adoption response to the canonical adopted network", async () => {
    const getNetwork = vi
      .spyOn(client, "getCourseNetwork")
      .mockResolvedValueOnce({ class_id: CLASS_ID, network: null })
      .mockResolvedValueOnce({ class_id: CLASS_ID, network: ADOPTED_NETWORK });
    vi.spyOn(client, "openCourseNetworkSeedDraft").mockResolvedValue(ACCEPTED_DRAFT);
    const adopt = vi
      .spyOn(client, "adoptCourseNetworkSeed")
      .mockRejectedValue(new Error("Response lost after adoption"));
    const container = await mount(
      createElement(CourseNetworkWorkspace, { classId: CLASS_ID }),
    );
    await settle();

    await click(buttonNamed(container, "Adopt course network"));
    await settle();

    expect(adopt).toHaveBeenCalledTimes(1);
    expect(getNetwork).toHaveBeenCalledTimes(2);
    expect(container.textContent).toContain("Adopted");
    expect(container.textContent).toContain("revision 1");
    expect(container.textContent).not.toContain("Action not completed");
  });

  it("keeps a true adoption failure recoverable and blocks duplicate submits", async () => {
    let rejectAdoption!: (reason: Error) => void;
    vi.spyOn(client, "getCourseNetwork")
      .mockResolvedValueOnce({ class_id: CLASS_ID, network: null })
      .mockResolvedValueOnce({ class_id: CLASS_ID, network: null });
    vi.spyOn(client, "openCourseNetworkSeedDraft").mockResolvedValue(ACCEPTED_DRAFT);
    vi.spyOn(client, "getCourseNetworkDraft").mockResolvedValue(ACCEPTED_DRAFT);
    const adopt = vi
      .spyOn(client, "adoptCourseNetworkSeed")
      .mockReturnValue(
        new Promise((_resolve, reject) => {
          rejectAdoption = reject;
        }),
      );
    const container = await mount(
      createElement(CourseNetworkWorkspace, { classId: CLASS_ID }),
    );
    await settle();

    const adoptButton = buttonNamed(container, "Adopt course network");
    await act(async () => {
      adoptButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      adoptButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(adopt).toHaveBeenCalledTimes(1);

    rejectAdoption(new Error("Adoption service unavailable"));
    await settle();

    expect(container.textContent).toContain("Adoption service unavailable");
    expect(buttonNamed(container, "Refresh state").disabled).toBe(false);
    expect(buttonNamed(container, "Adopt course network").disabled).toBe(false);
  });

  it("keeps Materials visibly coming soon and non-navigating", async () => {
    vi.spyOn(client, "getCourseNetwork").mockResolvedValue({
      class_id: CLASS_ID,
      network: ADOPTED_NETWORK,
    });
    const container = await mount(
      createElement(CourseNetworkWorkspace, { classId: CLASS_ID }),
    );
    await settle();

    const materials = buttonNamed(container, "Materials");
    expect(materials.textContent).toContain("Coming soon");
    expect(materials.disabled).toBe(true);
    await click(materials);
    expect(navigation.router.push).not.toHaveBeenCalled();
  });

  it("renders narrow-screen graph guidance, searchable outline, and inspector together", async () => {
    vi.spyOn(client, "getCourseNetwork").mockResolvedValue({
      class_id: CLASS_ID,
      network: ADOPTED_NETWORK,
    });
    const container = await mount(
      createElement(CourseNetworkWorkspace, { classId: CLASS_ID }),
    );
    await settle();

    expect(container.textContent).toContain(
      "The searchable outline is the graph view on smaller screens",
    );
    expect(container.textContent).toContain("The canvas appears on wider screens");
    expect(container.querySelector('[aria-label="Course network outline"]')).not.toBeNull();
    expect(container.querySelector('[aria-label="Learning block inspector"]')).not.toBeNull();
  });
});
