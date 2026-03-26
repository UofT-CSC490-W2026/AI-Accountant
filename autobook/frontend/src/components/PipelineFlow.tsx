import { useEffect, useRef } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Node,
  type Edge,
  type NodeProps,
  Handle,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

type Branch = "precedent" | "ml" | "llm";

export type PipelineState = {
  store: boolean;
  stages: Record<Branch, boolean>;
  post: Record<Branch, boolean>;
};

type PipelineFlowProps = {
  state: PipelineState;
  activeStage: string | null;
  onToggleStore: () => void;
  onToggleStage: (b: Branch) => void;
  onTogglePost: (b: Branch) => void;
};

// --- Custom node ---

type PipelineNodeData = {
  label: string;
  variant: "static" | "enabled" | "off" | "disabled" | "processing";
};

const COLORS = {
  olive: "#606C38",
  forest: "#283618",
  corn: "#FEFAE0",
};

const VARIANT_STYLES: Record<string, React.CSSProperties> = {
  static: {
    background: COLORS.olive,
    color: COLORS.corn,
    cursor: "default",
  },
  enabled: {
    background: COLORS.olive,
    color: COLORS.corn,
    cursor: "pointer",
    boxShadow: "0 6px 14px rgba(40,54,24,0.22)",
  },
  off: {
    background: COLORS.corn,
    color: COLORS.forest,
    border: `1.5px solid ${COLORS.olive}`,
    cursor: "pointer",
  },
  disabled: {
    background: COLORS.forest,
    color: "rgba(254,250,224,0.4)",
    cursor: "not-allowed",
  },
  processing: {
    background: "#DDA15E",
    color: COLORS.forest,
    cursor: "default",
    boxShadow: "0 0 0 3px rgba(221,161,94,0.4)",
    animation: "pulse-node 1.2s ease-in-out infinite",
  },
};

function PipelineNode({ data }: NodeProps<Node<PipelineNodeData>>) {
  return (
    <div
      style={{
        padding: "10px 22px",
        borderRadius: 14,
        fontWeight: 700,
        fontSize: "0.85rem",
        textAlign: "center",
        minWidth: 100,
        userSelect: "none",
        transition: "all 180ms ease",
        ...VARIANT_STYLES[data.variant],
      }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Top} id="top" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={{ opacity: 0 }} />
      {data.label}
    </div>
  );
}

const nodeTypes = { pipeline: PipelineNode };

// --- Layout: equal x-axis step between each stage ---

const STEP = 160;
const X = {
  parse: 0,
  norm: STEP,
  store: STEP * 2.2,
};
const STAGE_X = {
  precedent: STEP * 2,
  ml: STEP * 3,
  llm: STEP * 4,
};
const POST_OFFSET = STEP * 1.2;
const Y = { top: 0, p: 120, m: 240, l: 360 };

// --- Build nodes from state ---

// Map node IDs to stage names used by backend events
const NODE_TO_STAGE: Record<string, string> = {
  norm: "normalizer",
  store: "normalizer",
  precedent: "precedent",
  ml: "ml",
  llm: "llm",
  "post-p": "precedent",
  "post-m": "ml",
  "post-l": "llm",
};

function buildNodes(state: PipelineState, h: PipelineFlowProps): Node<PipelineNodeData>[] {
  const active = h.activeStage;

  const stageVariant = (nodeId: string, isOn: boolean): PipelineNodeData["variant"] => {
    if (active && NODE_TO_STAGE[nodeId] === active) return "processing";
    return isOn ? "enabled" : "off";
  };

  const postVariant = (b: Branch): PipelineNodeData["variant"] => {
    if (!state.stages[b] || !state.store) return "disabled";
    if (active && NODE_TO_STAGE[`post-${b[0]}`] === active) return "processing";
    return state.post[b] ? "enabled" : "off";
  };

  return [
    { id: "parse", type: "pipeline", position: { x: X.parse, y: Y.top }, draggable: false, data: { label: "Parse", variant: "static" } },
    { id: "norm", type: "pipeline", position: { x: X.norm, y: Y.top }, draggable: false, data: { label: "Normalizer", variant: active === "normalizer" ? "processing" : "static" } },
    { id: "store", type: "pipeline", position: { x: X.store, y: Y.top }, draggable: false, data: { label: "Store", variant: stageVariant("store", state.store) } },
    { id: "precedent", type: "pipeline", position: { x: STAGE_X.precedent, y: Y.p }, draggable: false, data: { label: "Precedent", variant: stageVariant("precedent", state.stages.precedent) } },
    { id: "ml", type: "pipeline", position: { x: STAGE_X.ml, y: Y.m }, draggable: false, data: { label: "ML", variant: stageVariant("ml", state.stages.ml) } },
    { id: "llm", type: "pipeline", position: { x: STAGE_X.llm, y: Y.l }, draggable: false, data: { label: "LLM", variant: stageVariant("llm", state.stages.llm) } },
    { id: "post-p", type: "pipeline", position: { x: STAGE_X.precedent + POST_OFFSET, y: Y.p }, draggable: false, data: { label: "Post", variant: postVariant("precedent") } },
    { id: "post-m", type: "pipeline", position: { x: STAGE_X.ml + POST_OFFSET, y: Y.m }, draggable: false, data: { label: "Post", variant: postVariant("ml") } },
    { id: "post-l", type: "pipeline", position: { x: STAGE_X.llm + POST_OFFSET, y: Y.l }, draggable: false, data: { label: "Post", variant: postVariant("llm") } },
  ];
}

// --- Dynamic edges: only show active flow path ---

const EDGE_COLOR = "#9CA3AF";
const ARROW = { type: "arrowclosed" as const, color: EDGE_COLOR };
const EDGE_STYLE = { stroke: EDGE_COLOR, strokeWidth: 2 };

function edge(id: string, source: string, target: string, vertical = false): Edge {
  return {
    id,
    source,
    target,
    type: vertical ? "smoothstep" : undefined,
    sourceHandle: vertical ? "bottom" : undefined,
    style: EDGE_STYLE,
    animated: true,
    markerEnd: ARROW,
  };
}

function buildEdges(state: PipelineState): Edge[] {
  const { store, stages, post } = state;
  const { precedent: p, ml: m, llm: l } = stages;
  const edges: Edge[] = [];

  // Parse → Normalizer: always
  edges.push(edge("e-parse-norm", "parse", "norm"));

  // Normalizer → Store: only when store is on
  if (store) edges.push(edge("e-norm-store", "norm", "store"));

  // Normalizer → first enabled stage
  if (p) edges.push(edge("e-norm-p", "norm", "precedent", true));
  else if (m) edges.push(edge("e-norm-m", "norm", "ml", true));
  else if (l) edges.push(edge("e-norm-l", "norm", "llm", true));

  // Precedent → next enabled stage (only if precedent is on)
  if (p) {
    if (m) edges.push(edge("e-p-m", "precedent", "ml", true));
    else if (l) edges.push(edge("e-p-l", "precedent", "llm", true));
  }

  // ML → LLM (only if both are on)
  if (m && l) edges.push(edge("e-m-l", "ml", "llm", true));

  // Stage → Post: only when both stage and its post are on
  if (p && post.precedent) edges.push(edge("e-p-post", "precedent", "post-p"));
  if (m && post.ml) edges.push(edge("e-m-post", "ml", "post-m"));
  if (l && post.llm) edges.push(edge("e-l-post", "llm", "post-l"));

  return edges;
}

function PipelineFlowInner(props: PipelineFlowProps) {
  const nodes = buildNodes(props.state, props);
  const edges = buildEdges(props.state);
  const { fitView } = useReactFlow();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver(() => {
      fitView({ padding: 0.15 });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [fitView]);

  const handleNodeClick = (_: React.MouseEvent, node: Node) => {
    switch (node.id) {
      case "store":
        props.onToggleStore();
        break;
      case "precedent":
        props.onToggleStage("precedent");
        break;
      case "ml":
        props.onToggleStage("ml");
        break;
      case "llm":
        props.onToggleStage("llm");
        break;
      case "post-p":
        props.onTogglePost("precedent");
        break;
      case "post-m":
        props.onTogglePost("ml");
        break;
      case "post-l":
        props.onTogglePost("llm");
        break;
    }
  };

  return (
    <div ref={containerRef} style={{ width: "100%", height: "clamp(300px, 40vw, 520px)" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        proOptions={{ hideAttribution: true }}
        panOnDrag={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
        preventScrolling={false}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      />
    </div>
  );
}

export function PipelineFlow(props: PipelineFlowProps) {
  return (
    <ReactFlowProvider>
      <PipelineFlowInner {...props} />
    </ReactFlowProvider>
  );
}
