import type {
  CanvasPosition,
  CourseNetwork,
  CourseNetworkEdge,
  CourseNetworkNode,
  ReactFlowModel,
} from "./types";

const LAYER_X_GAP = 320;
const ROW_Y_GAP = 180;
const FINAL_GRID_COLUMNS = 3;

const relationPresentation = {
  builds_on: {
    label: "builds on",
    style: { stroke: "var(--primary)", strokeWidth: 2 },
  },
  related_to: {
    label: "related to",
    style: { stroke: "var(--muted-foreground)", strokeDasharray: "5 5" },
  },
} as const;

function fallbackPositions(network: CourseNetwork): Map<string, CanvasPosition> {
  const missingIds = network.nodes
    .filter((node) => network.positions[node.id] === undefined)
    .map((node) => node.id);
  const missingIdSet = new Set(missingIds);
  const outgoing = new Map(missingIds.map((id) => [id, [] as string[]]));
  const inDegree = new Map(missingIds.map((id) => [id, 0]));
  const connected = new Set<string>();

  for (const edge of network.edges) {
    if (
      edge.relation !== "builds_on" ||
      !missingIdSet.has(edge.source_id) ||
      !missingIdSet.has(edge.target_id)
    ) {
      continue;
    }

    outgoing.get(edge.target_id)!.push(edge.source_id);
    inDegree.set(edge.source_id, inDegree.get(edge.source_id)! + 1);
    connected.add(edge.source_id);
    connected.add(edge.target_id);
  }

  const layerById = new Map<string, number>();
  const ready = missingIds.filter(
    (id) => connected.has(id) && inDegree.get(id) === 0,
  );

  for (let index = 0; index < ready.length; index += 1) {
    const id = ready[index]!;
    const layer = layerById.get(id) ?? 0;
    for (const dependentId of outgoing.get(id)!) {
      layerById.set(
        dependentId,
        Math.max(layerById.get(dependentId) ?? 0, layer + 1),
      );
      const nextInDegree = inDegree.get(dependentId)! - 1;
      inDegree.set(dependentId, nextInDegree);
      if (nextInDegree === 0) {
        ready.push(dependentId);
      }
    }
  }

  const positioned = new Map<string, CanvasPosition>();
  const rowsByLayer = new Map<number, number>();
  for (const id of missingIds) {
    const layer = layerById.get(id);
    if (layer === undefined || !connected.has(id)) continue;

    const row = rowsByLayer.get(layer) ?? 0;
    positioned.set(id, { x: layer * LAYER_X_GAP, y: row * ROW_Y_GAP });
    rowsByLayer.set(layer, row + 1);
  }

  const finalGridStartY =
    (Math.max(0, ...rowsByLayer.values()) + 1) * ROW_Y_GAP;
  const finalGridIds = missingIds.filter((id) => !positioned.has(id));
  for (const [index, id] of finalGridIds.entries()) {
    positioned.set(id, {
      x: (index % FINAL_GRID_COLUMNS) * LAYER_X_GAP,
      y: finalGridStartY + Math.floor(index / FINAL_GRID_COLUMNS) * ROW_Y_GAP,
    });
  }

  return positioned;
}

export function toReactFlowModel(network: CourseNetwork): ReactFlowModel {
  const computedPositions = fallbackPositions(network);
  const nodes: CourseNetworkNode[] = network.nodes.map((learningBlock) => ({
    id: learningBlock.id,
    position:
      network.positions[learningBlock.id] ?? computedPositions.get(learningBlock.id)!,
    data: { learningBlock },
  }));
  const edges: CourseNetworkEdge[] = network.edges.map((edge) => ({
    id: edge.id,
    source: edge.source_id,
    target: edge.target_id,
    data: { relation: edge.relation },
    ...relationPresentation[edge.relation],
  }));

  return { nodes, edges };
}
