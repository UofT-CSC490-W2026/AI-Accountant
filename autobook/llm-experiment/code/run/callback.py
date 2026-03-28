"""Per-node usage callback — tracks token usage per LangGraph node."""
from __future__ import annotations

from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

_KNOWN_NODES: set[str] = {
    "disambiguator",
    "debit_classifier", "credit_classifier",
    "debit_corrector", "credit_corrector",
    "corrector_passthrough",
    "entry_builder",
    "validation",
    "approver",
    "diagnostician",
    "fix_scheduler",
    "confidence_gate",
    "single_agent",
}


class PerNodeUsageCallback(BaseCallbackHandler):
    """Tracks token usage per LangGraph node using run_id parent chain."""

    def __init__(self):
        self._node_of: dict[str, str] = {}
        self._parent: dict[str, str] = {}
        self.llm_calls: list[dict] = []
        self.stop_reasons: dict[str, str] = {}

    def _resolve_node(self, run_id: Any) -> str:
        seen: set[str] = set()
        current = str(run_id) if run_id else None
        while current and current not in seen:
            if current in self._node_of:
                return self._node_of[current]
            seen.add(current)
            current = self._parent.get(current)
        return "unknown"

    def on_chain_start(self, serialized: Any, inputs: Any, *,
                       run_id: Any = None, parent_run_id: Any = None,
                       name: str | None = None, **kwargs) -> None:
        if run_id is not None:
            rid = str(run_id)
            if parent_run_id is not None:
                self._parent[rid] = str(parent_run_id)
            if name and name in _KNOWN_NODES:
                self._node_of[rid] = name

    def on_llm_start(self, serialized: Any, prompts: Any, *,
                     run_id: Any = None, parent_run_id: Any = None,
                     **kwargs) -> None:
        if run_id is not None and parent_run_id is not None:
            self._parent[str(run_id)] = str(parent_run_id)

    def on_llm_end(self, response: Any, *, run_id: Any = None, **kwargs) -> None:
        if not response.generations:
            return
        msg = response.generations[0][0].message
        node = self._resolve_node(run_id)
        stop_reason = msg.response_metadata.get("stopReason", "unknown")
        self.stop_reasons[node] = stop_reason
        usage = dict(msg.usage_metadata) if hasattr(msg, "usage_metadata") and msg.usage_metadata else {}
        details = usage.get("input_token_details") or {}
        self.llm_calls.append({
            "node": node,
            "stop_reason": stop_reason,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "input_token_details": {
                "cache_read": details.get("cache_read", 0),
                "cache_creation": details.get("cache_creation", 0),
            },
        })

    def reset(self) -> None:
        self._node_of.clear()
        self._parent.clear()
        self.llm_calls.clear()
        self.stop_reasons.clear()
