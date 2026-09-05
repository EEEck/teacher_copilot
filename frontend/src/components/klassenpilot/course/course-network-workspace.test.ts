import { readFileSync } from "node:fs";

import { afterEach, describe, expect, it, vi } from "vitest";

import { isExactPassingReview } from "./course-network-adoption";
import { client } from "@/lib/api";

function source(fileName: string): string {
  return readFileSync(new URL(`./${fileName}`, import.meta.url), "utf8");
}

describe("course network workspace composition", () => {
  it("keeps the canvas, narrow outline, and inspector in the workspace", () => {
    const workspace = source("course-network-workspace.tsx");

    expect(workspace).toContain("CourseNetworkCanvas");
    expect(workspace).toContain("CourseNetworkOutline");
    expect(workspace).toContain("LearningBlockInspector");
    expect(workspace).toContain("sm:grid-cols-");
    expect(readFileSync(new URL("../../layout/app-shell.tsx", import.meta.url), "utf8")).toContain(
      'flush ? "overflow-y-auto px-3 py-2"',
    );
  });

  it("keeps the React Flow canvas affordances together", () => {
    const canvas = source("course-network-canvas.tsx");

    expect(canvas).toContain("ReactFlow");
    expect(canvas).toContain("ReactFlowProvider");
    expect(canvas).toContain("Background");
    expect(canvas).toContain("Controls");
    expect(canvas).toContain("minZoom={0.1}");
    expect(canvas).toContain("FitViewOnResize");
    expect(canvas).toContain("preventScrolling={false}");
    expect(canvas).toContain("zoomOnScroll={false}");
  });

  it("lets inspector details grow with the page instead of a nested pane", () => {
    const inspector = source("learning-block-inspector.tsx");

    expect(inspector).not.toContain("overflow-y-auto");
    expect(inspector).not.toContain("min-h-[20rem]");
  });

  it("does not hide graph handles with display none", () => {
    const styles = readFileSync(
      new URL("../../../app/globals.css", import.meta.url),
      "utf8",
    );
    const handleBlock = styles.slice(styles.indexOf(".course-network-handle"));

    expect(handleBlock).toContain("pointer-events: none");
    expect(handleBlock).not.toMatch(/display:\s*none/);
  });
});

describe("course network API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses the A2 draft, review, and exact adoption routes", async () => {
    const network = {
      schema_version: 1,
      class_id: "chemie_8a",
      route: { subject: "chemie", grade: 8, branch: "NTG" },
      revision: 0,
      nodes: [],
      edges: [],
      material_mappings: [],
      positions: {},
      updated_at: "2026-08-18T00:00:00Z",
    };
    const draft = {
      draft_id: "draft-8a",
      class_id: "chemie_8a",
      status: "draft",
      artifact_markdown: "{}",
      artifact_revision: 4,
      artifact_hash: "sha256:exact",
      backend_session_id: "session-8a",
      network,
      review: null,
    };
    const adoptedNetwork = { ...network, revision: 1 };
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const path = new URL(String(input)).pathname;
      const body = path.endsWith("/adopt")
        ? {
            class_id: "chemie_8a",
            draft_id: "draft-8a",
            log_entry_id: "log-1",
            network: adoptedNetwork,
          }
        : path.endsWith("/network")
          ? { class_id: "chemie_8a", network: null }
          : draft;
      return new Response(JSON.stringify(body), {
        status: path.endsWith("/drafts") && init?.method === "POST" ? 201 : 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    await client.getCourseNetwork("chemie_8a");
    await client.getCourseNetworkSourceSection(
      "chemie_8a",
      "source/with spaces",
      "section#exact",
    );
    await client.openCourseNetworkSeedDraft("chemie_8a");
    await client.getCourseNetworkDraft("chemie_8a", "draft-8a");
    await client.reviewCourseNetworkSeed("chemie_8a", "draft-8a");
    await client.adoptCourseNetworkSeed("chemie_8a", "draft-8a", {
      expected_revision: 4,
      expected_hash: "sha256:exact",
    });

    expect(
      fetchMock.mock.calls.map(([input, init]) => ({
        path: new URL(String(input)).pathname,
        method: init?.method ?? "GET",
        body: init?.body ? JSON.parse(String(init.body)) : null,
      })),
    ).toEqual([
      { path: "/api/classes/chemie_8a/course/network", method: "GET", body: null },
      {
        path:
          "/api/classes/chemie_8a/course/network/sources/source%2Fwith%20spaces/sections/section%23exact",
        method: "GET",
        body: null,
      },
      { path: "/api/classes/chemie_8a/course/network/drafts", method: "POST", body: null },
      {
        path: "/api/classes/chemie_8a/course/network/drafts/draft-8a",
        method: "GET",
        body: null,
      },
      {
        path: "/api/classes/chemie_8a/course/network/drafts/draft-8a/review",
        method: "POST",
        body: null,
      },
      {
        path: "/api/classes/chemie_8a/course/network/drafts/draft-8a/adopt",
        method: "POST",
        body: { expected_revision: 4, expected_hash: "sha256:exact" },
      },
    ]);
  });
});

describe("course network adoption gate", () => {
  const draft = {
    draft_id: "draft-8a",
    class_id: "chemie_8a",
    status: "draft",
    artifact_markdown: "{}",
    artifact_revision: 4,
    artifact_hash: "sha256:exact",
    backend_session_id: "session-8a",
    network: {
      schema_version: 1 as const,
      class_id: "chemie_8a",
      route: { subject: "chemie", grade: 8, branch: "NTG" },
      revision: 0,
      nodes: [],
      edges: [],
      material_mappings: [],
      positions: {},
      updated_at: "2026-08-18T00:00:00Z",
    },
    review: {
      decision: "accept" as const,
      summary: "Ready to adopt.",
      findings: [],
      artifact_revision: 4,
      artifact_hash: "sha256:exact",
      deterministic: false,
    },
  };

  it("accepts only a passing review bound to the current draft snapshot", () => {
    expect(isExactPassingReview(draft)).toBe(true);
    expect(
      isExactPassingReview({
        ...draft,
        review: { ...draft.review, artifact_revision: 3 },
      }),
    ).toBe(false);
    expect(
      isExactPassingReview({
        ...draft,
        review: { ...draft.review, artifact_hash: "sha256:stale" },
      }),
    ).toBe(false);
    expect(
      isExactPassingReview({
        ...draft,
        review: { ...draft.review, decision: "revise" },
      }),
    ).toBe(false);
    expect(isExactPassingReview({ ...draft, status: "discarded" })).toBe(false);
  });
});
