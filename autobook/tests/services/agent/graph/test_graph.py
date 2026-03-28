"""Test that the agent pipeline graph module loads and compiles correctly."""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, call


def test_graph_compiles():
    """Import graph.py and verify it calls StateGraph.compile()."""
    # The graph module is all module-level code. Importing it exercises
    # every line: StateGraph(), add_node(), add_edge(), compile().
    # We just need langgraph mocked.

    mock_builder = MagicMock()
    mock_builder.compile.return_value = MagicMock()

    mock_state_graph_cls = MagicMock(return_value=mock_builder)

    lg_graph = sys.modules.get("langgraph.graph")
    if lg_graph is None:
        lg_graph = ModuleType("langgraph.graph")
        sys.modules.setdefault("langgraph", ModuleType("langgraph"))
        sys.modules["langgraph.graph"] = lg_graph
    lg_graph.StateGraph = mock_state_graph_cls
    lg_graph.END = "__end__"

    lg_types = sys.modules.get("langgraph.types")
    if lg_types is None:
        lg_types = ModuleType("langgraph.types")
        sys.modules["langgraph.types"] = lg_types
    lg_types.RetryPolicy = MagicMock()

    # Force re-import to execute module-level code
    mod_key = "services.agent.graph.graph"
    sys.modules.pop(mod_key, None)

    import services.agent.graph.graph as graph_mod

    # Verify the graph was built
    assert mock_builder.add_node.call_count >= 11  # 8 LLM + 3 non-LLM nodes
    assert mock_builder.add_edge.call_count >= 4   # direct edges
    assert mock_builder.add_conditional_edges.call_count >= 6  # conditional routing
    mock_builder.compile.assert_called_once()
    assert graph_mod.app is not None
