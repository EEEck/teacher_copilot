import { describe, expect, it } from "vitest";

import { toReactFlowModel } from "./to-react-flow";

const networkWithoutPositions = {
  schema_version: 1 as const,
  class_id: "chemie-8a",
  route: { subject: "chemie", grade: 8, branch: "NTG" },
  revision: 1,
  nodes: [
    {
      id: "a",
      title: "Reaktionsgleichungen",
      description: "",
      learning_goal: "",
      curriculum_refs: [],
      material_refs: [],
      origin: "curriculum" as const,
      status: "adopted" as const,
    },
    {
      id: "b",
      title: "Atommodell",
      description: "",
      learning_goal: "",
      curriculum_refs: [],
      material_refs: [],
      origin: "curriculum" as const,
      status: "adopted" as const,
    },
  ],
  edges: [
    {
      id: "a-builds-on-b",
      source_id: "a",
      target_id: "b",
      relation: "builds_on" as const,
      curriculum_refs: [],
      material_refs: [],
      origin: "curriculum" as const,
    },
  ],
  material_mappings: [],
  positions: {},
  updated_at: "2026-08-18T12:00:00Z",
};

describe("toReactFlowModel", () => {
  it("preserves domain ids and computes fallback positions", () => {
    const model = toReactFlowModel(networkWithoutPositions);

    expect(model.nodes.map((node) => node.id)).toEqual(["a", "b"]);
    expect(model.nodes[0]?.data.learningBlock.id).toBe("a");
    expect(model.edges[0]?.data?.relation).toBe("builds_on");
    expect(model.nodes.every((node) => Number.isFinite(node.position.x))).toBe(true);
  });

  it("uses deterministic fallback positions for cyclic and unconnected nodes", () => {
    const network = {
      ...networkWithoutPositions,
      nodes: [
        ...networkWithoutPositions.nodes,
        {
          id: "c",
          title: "Kreislauf eins",
          description: "",
          learning_goal: "",
          curriculum_refs: [],
          material_refs: [],
          origin: "teacher" as const,
          status: "adopted" as const,
        },
        {
          id: "d",
          title: "Kreislauf zwei",
          description: "",
          learning_goal: "",
          curriculum_refs: [],
          material_refs: [],
          origin: "teacher" as const,
          status: "adopted" as const,
        },
        {
          id: "e",
          title: "Eigenstaendiger Baustein",
          description: "",
          learning_goal: "",
          curriculum_refs: [],
          material_refs: [],
          origin: "teacher" as const,
          status: "adopted" as const,
        },
      ],
      edges: [
        ...networkWithoutPositions.edges,
        {
          id: "c-builds-on-d",
          source_id: "c",
          target_id: "d",
          relation: "builds_on" as const,
          curriculum_refs: [],
          material_refs: [],
          origin: "teacher" as const,
        },
        {
          id: "d-builds-on-c",
          source_id: "d",
          target_id: "c",
          relation: "builds_on" as const,
          curriculum_refs: [],
          material_refs: [],
          origin: "teacher" as const,
        },
      ],
    };

    const first = toReactFlowModel(network);
    const second = toReactFlowModel(network);

    expect(first.nodes.map((node) => node.position)).toEqual(
      second.nodes.map((node) => node.position),
    );
    expect(first.nodes.slice(2).every((node) => node.position.y > first.nodes[0]!.position.y)).toBe(true);
  });

  it("does not mutate the API record", () => {
    const before = structuredClone(networkWithoutPositions);

    toReactFlowModel(networkWithoutPositions);

    expect(networkWithoutPositions).toEqual(before);
  });

  it("keeps supplied positions and distinguishes relation labels and styles", () => {
    const model = toReactFlowModel({
      ...networkWithoutPositions,
      positions: {
        a: { x: 40, y: 80 },
        b: { x: 360, y: 80 },
      },
      edges: [
        ...networkWithoutPositions.edges,
        {
          id: "a-related-to-b",
          source_id: "a",
          target_id: "b",
          relation: "related_to",
          curriculum_refs: [],
          material_refs: [],
          origin: "curriculum" as const,
        },
      ],
    });

    expect(model.nodes.map((node) => node.position)).toEqual([
      { x: 40, y: 80 },
      { x: 360, y: 80 },
    ]);
    expect(model.edges.map((edge) => edge.label)).toEqual([
      "builds on",
      "related to",
    ]);
    expect(model.edges[0]?.style).not.toEqual(model.edges[1]?.style);
  });
});
