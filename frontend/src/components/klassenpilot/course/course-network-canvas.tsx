"use client";

import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  type NodeTypes,
} from "@xyflow/react";

import { LearningBlockNode } from "./learning-block-node";
import { toReactFlowModel } from "@/features/course-network/to-react-flow";
import type { CourseNetwork } from "@/features/course-network/types";

const nodeTypes: NodeTypes = {
  learningBlock: LearningBlockNode,
};

export function CourseNetworkCanvas({
  network,
  selectedId,
  onSelect,
}: {
  network: CourseNetwork;
  selectedId: string | null;
  onSelect: (nodeId: string | null) => void;
}) {
  const model = useMemo(() => {
    const flow = toReactFlowModel(network);
    return {
      nodes: flow.nodes.map((node) => ({
        ...node,
        type: "learningBlock",
        ariaLabel: `Lernbaustein: ${node.data.learningBlock.title}`,
        draggable: false,
        deletable: false,
        connectable: false,
        focusable: true,
        selectable: true,
        selected: node.id === selectedId,
      })),
      edges: flow.edges.map((edge) => ({
        ...edge,
        deletable: false,
        focusable: false,
        reconnectable: false,
      })),
    };
  }, [network, selectedId]);

  return (
    <div
      role="region"
      aria-label="Course network graph"
      className="course-network-flow h-full min-h-[32rem] overflow-hidden rounded-xl border border-border bg-background shadow-sm"
    >
      <ReactFlow
        nodes={model.nodes}
        edges={model.edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 1 }}
        minZoom={0.25}
        maxZoom={1.5}
        nodesDraggable={false}
        nodesConnectable={false}
        nodesFocusable
        edgesFocusable={false}
        edgesReconnectable={false}
        elementsSelectable
        deleteKeyCode={null}
        multiSelectionKeyCode={null}
        onNodeClick={(_, node) => onSelect(node.id)}
        onSelectionChange={({ nodes }) => onSelect(nodes.at(-1)?.id ?? null)}
        onPaneClick={() => onSelect(null)}
        proOptions={{ hideAttribution: true }}
        aria-label="Read-only course network"
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
        <Controls showInteractive={false} aria-label="Graph view controls" />
      </ReactFlow>
    </div>
  );
}
