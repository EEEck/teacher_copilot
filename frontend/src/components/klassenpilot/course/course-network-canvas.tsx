"use client";

import {
  useLayoutEffect,
  useMemo,
  useRef,
  type KeyboardEvent as ReactKeyboardEvent,
  type RefObject,
} from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type NodeTypes,
} from "@xyflow/react";

import { LearningBlockNode } from "./learning-block-node";
import { toReactFlowModel } from "@/features/course-network/to-react-flow";
import type { CourseNetwork } from "@/features/course-network/types";

const nodeTypes: NodeTypes = {
  learningBlock: LearningBlockNode,
};

const FIT_VIEW = { padding: 0.16, maxZoom: 1 } as const;

function FitViewOnResize({
  target,
}: {
  target: RefObject<HTMLElement | null>;
}) {
  const { fitView } = useReactFlow();

  useLayoutEffect(() => {
    const pane = target.current;
    if (!pane) return;

    let frame = 0;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        void fitView(FIT_VIEW);
      });
    });
    observer.observe(pane);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [fitView, target]);

  return null;
}

export function CourseNetworkCanvas({
  network,
  selectedId,
  onSelect,
}: {
  network: CourseNetwork;
  selectedId: string | null;
  onSelect: (nodeId: string | null) => void;
}) {
  const frameRef = useRef<HTMLDivElement>(null);
  const model = useMemo(() => {
    const flow = toReactFlowModel(network);
    return {
      nodes: flow.nodes.map((node) => ({
        ...node,
        data: {
          ...node.data,
          inspectorSelected: node.id === selectedId,
        },
        type: "learningBlock",
        ariaLabel: `Lernbaustein: ${node.data.learningBlock.title}`,
        draggable: false,
        deletable: false,
        connectable: false,
        focusable: true,
        selectable: true,
      })),
      edges: flow.edges.map((edge) => ({
        ...edge,
        deletable: false,
        focusable: false,
        reconnectable: false,
      })),
    };
  }, [network, selectedId]);

  const handleGraphKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (!(event.target instanceof Element)) return;

    const nodeId = event.target
      .closest<HTMLElement>(".react-flow__node[data-id]")
      ?.getAttribute("data-id");
    if (!nodeId) return;

    if (event.key === "Enter" || event.key === " ") {
      onSelect(nodeId);
    } else if (event.key === "Escape") {
      onSelect(null);
    }
  };

  return (
    <ReactFlowProvider>
      <div
        ref={frameRef}
        role="region"
        aria-label="Course network graph"
        className="course-network-flow h-full min-h-0 overflow-hidden rounded-xl border border-border bg-background shadow-sm"
        onKeyDownCapture={handleGraphKeyDown}
      >
        <ReactFlow
          nodes={model.nodes}
          edges={model.edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={FIT_VIEW}
          minZoom={0.1}
          maxZoom={1.5}
          zoomOnScroll={false}
          preventScrolling={false}
          nodesDraggable={false}
          nodesConnectable={false}
          nodesFocusable
          edgesFocusable={false}
          edgesReconnectable={false}
          elementsSelectable
          deleteKeyCode={null}
          multiSelectionKeyCode={null}
          onNodeClick={(_, node) => onSelect(node.id)}
          onPaneClick={() => onSelect(null)}
          proOptions={{ hideAttribution: true }}
          aria-label="Read-only course network"
        >
          <FitViewOnResize target={frameRef} />
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
          <Controls showInteractive={false} aria-label="Graph view controls" />
        </ReactFlow>
      </div>
    </ReactFlowProvider>
  );
}
