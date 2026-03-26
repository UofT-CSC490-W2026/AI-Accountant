import { createContext, useCallback, useContext, useEffect, useRef } from "react";
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
  completedStages: Set<string>;
  skippedStages: Set<string>;
  locked: boolean;
  onToggleStore: () => void;
  onToggleStage: (b: Branch) => void;
  onTogglePost: (b: Branch) => void;
};

// --- Context: nodes read variant from here, bypassing React Flow's memo ---

type PipelineCtx = {
  state: PipelineState;
  activeStage: string | null;
  completedStages: Set<string>;
  skippedStages: Set<string>;
  locked: boolean;
};

const PipelineContext = createContext<PipelineCtx>({
  state: { store: false, stages: { precedent: false, ml: false, llm: false }, post: { precedent: false, ml: false, llm: false } },
  activeStage: null,
  completedStages: new Set(),
  skippedStages: new Set(),
  locked: false,
});

// --- Variant resolution ---

const COLORS = {
  olive: "#606C38",
  forest: "#283618",
  corn: "#FEFAE0",
};

const VARIANT_STYLES: Record<string, React.CSSProperties> = {
  static: { background: COLORS.olive, color: COLORS.corn, cursor: "default" },
  enabled: { background: COLORS.olive, color: COLORS.corn, cursor: "pointer", boxShadow: "0 6px 14px rgba(40,54,24,0.22)" },
  off: { background: COLORS.corn, color: COLORS.forest, border: `1.5px solid ${COLORS.olive}`, cursor: "pointer" },
  disabled: { background: COLORS.forest, color: "rgba(254,250,224,0.4)", cursor: "not-allowed" },
  processing: { background: "#DDA15E", color: COLORS.forest, cursor: "default", boxShadow: "0 0 0 3px rgba(221,161,94,0.4)", animation: "pulse-node 1.2s ease-in-out infinite" },
  completed: { background: "#BC6C25", color: "#ffffff", cursor: "default", boxShadow: "0 4px 10px rgba(188,108,37,0.3)" },
  skipped: { background: "#9E2A2B", color: "#ffffff", cursor: "default", boxShadow: "0 4px 10px rgba(158,42,43,0.3)" },
};

const NODE_TO_STAGE: Record<string, string> = {
  norm: "normalizer",
  store: "store",
  precedent: "precedent",
  ml: "ml",
  llm: "llm",
  "post-p": "post-precedent",
  "post-m": "post-ml",
  "post-l": "post-llm",
};

function resolveVariant(nodeId: string, ctx: PipelineCtx): string {
  const stageName = NODE_TO_STAGE[nodeId];
  const { state, activeStage, completedStages, skippedStages } = ctx;

  // Progress states take priority
  if (activeStage === stageName) return "processing";
  if (skippedStages.has(stageName)) return "skipped";
  if (completedStages.has(stageName)) return "completed";

  // Base variant per node type
  if (nodeId === "parse") return "static";
  if (nodeId === "norm") return "static";
  if (nodeId === "store") return state.store ? "enabled" : "off";
  if (nodeId === "post-p") return (!state.stages.precedent || !state.store) ? "disabled" : state.post.precedent ? "enabled" : "off";
  if (nodeId === "post-m") return (!state.stages.ml || !state.store) ? "disabled" : state.post.ml ? "enabled" : "off";
  if (nodeId === "post-l") return (!state.stages.llm || !state.store) ? "disabled" : state.post.llm ? "enabled" : "off";
  if (nodeId === "precedent") return state.stages.precedent ? "enabled" : "off";
  if (nodeId === "ml") return state.stages.ml ? "enabled" : "off";
  if (nodeId === "llm") return state.stages.llm ? "enabled" : "off";
  return "off";
}

// --- Custom node: reads variant from context ---

type PipelineNodeData = { label: string; nodeId: string };

function PipelineNode({ data }: NodeProps<Node<PipelineNodeData>>) {
  const ctx = useContext(PipelineContext);
  const variant = resolveVariant(data.nodeId, ctx);

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
        transition: "background 180ms ease, box-shadow 180ms ease",
        ...VARIANT_STYLES[variant],
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

// --- Layout ---

const STEP = 160;
const X = { parse: 0, norm: STEP, store: STEP * 2.2 };
const STAGE_X = { precedent: STEP * 2, ml: STEP * 3, llm: STEP * 4 };
const POST_OFFSET = STEP * 1.2;
const Y = { top: 0, p: 120, m: 240, l: 360 };

// --- Static nodes (positions + labels only, no variant) ---

const STATIC_NODES: Node<PipelineNodeData>[] = [
  { id: "parse", type: "pipeline", position: { x: X.parse, y: Y.top }, draggable: false, data: { label: "Parse", nodeId: "parse" } },
  { id: "norm", type: "pipeline", position: { x: X.norm, y: Y.top }, draggable: false, data: { label: "Normalizer", nodeId: "norm" } },
  { id: "store", type: "pipeline", position: { x: X.store, y: Y.top }, draggable: false, data: { label: "Store", nodeId: "store" } },
  { id: "precedent", type: "pipeline", position: { x: STAGE_X.precedent, y: Y.p }, draggable: false, data: { label: "Precedent", nodeId: "precedent" } },
  { id: "ml", type: "pipeline", position: { x: STAGE_X.ml, y: Y.m }, draggable: false, data: { label: "ML", nodeId: "ml" } },
  { id: "llm", type: "pipeline", position: { x: STAGE_X.llm, y: Y.l }, draggable: false, data: { label: "LLM", nodeId: "llm" } },
  { id: "post-p", type: "pipeline", position: { x: STAGE_X.precedent + POST_OFFSET, y: Y.p }, draggable: false, data: { label: "Post", nodeId: "post-p" } },
  { id: "post-m", type: "pipeline", position: { x: STAGE_X.ml + POST_OFFSET, y: Y.m }, draggable: false, data: { label: "Post", nodeId: "post-m" } },
  { id: "post-l", type: "pipeline", position: { x: STAGE_X.llm + POST_OFFSET, y: Y.l }, draggable: false, data: { label: "Post", nodeId: "post-l" } },
];

// --- Dynamic edges ---

const EDGE_COLOR = "#9CA3AF";
const ARROW = { type: "arrowclosed" as const, color: EDGE_COLOR };
const EDGE_STYLE = { stroke: EDGE_COLOR, strokeWidth: 2 };

function mkEdge(id: string, source: string, target: string, vertical = false): Edge {
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

  edges.push(mkEdge("e-parse-norm", "parse", "norm"));
  if (store) edges.push(mkEdge("e-norm-store", "norm", "store"));

  if (p) edges.push(mkEdge("e-norm-p", "norm", "precedent", true));
  else if (m) edges.push(mkEdge("e-norm-m", "norm", "ml", true));
  else if (l) edges.push(mkEdge("e-norm-l", "norm", "llm", true));

  if (p) {
    if (m) edges.push(mkEdge("e-p-m", "precedent", "ml", true));
    else if (l) edges.push(mkEdge("e-p-l", "precedent", "llm", true));
  }

  if (m && l) edges.push(mkEdge("e-m-l", "ml", "llm", true));

  if (p && post.precedent) edges.push(mkEdge("e-p-post", "precedent", "post-p"));
  if (m && post.ml) edges.push(mkEdge("e-m-post", "ml", "post-m"));
  if (l && post.llm) edges.push(mkEdge("e-l-post", "llm", "post-l"));

  return edges;
}

// --- Inner component ---

function PipelineFlowInner(props: PipelineFlowProps) {
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

  const handleNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    if (props.locked) return;
    switch (node.id) {
      case "store": props.onToggleStore(); break;
      case "precedent": props.onToggleStage("precedent"); break;
      case "ml": props.onToggleStage("ml"); break;
      case "llm": props.onToggleStage("llm"); break;
      case "post-p": props.onTogglePost("precedent"); break;
      case "post-m": props.onTogglePost("ml"); break;
      case "post-l": props.onTogglePost("llm"); break;
    }
  }, [props.locked, props.onToggleStore, props.onToggleStage, props.onTogglePost]);

  return (
    <PipelineContext.Provider value={{
      state: props.state,
      activeStage: props.activeStage,
      completedStages: props.completedStages,
      skippedStages: props.skippedStages,
      locked: props.locked,
    }}>
      <div ref={containerRef} style={{ width: "100%", height: "clamp(300px, 40vw, 520px)" }}>
        <ReactFlow
          nodes={STATIC_NODES}
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
    </PipelineContext.Provider>
  );
}

export function PipelineFlow(props: PipelineFlowProps) {
  return (
    <ReactFlowProvider>
      <PipelineFlowInner {...props} />
    </ReactFlowProvider>
  );
}
