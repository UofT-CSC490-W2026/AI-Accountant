import logging

from services.agent.graph.graph import app
from services.agent.graph.state import NOT_RUN, AGENT_NAMES

logger = logging.getLogger(__name__)

# Default ablation config: classify_and_build (best Stage 1 accuracy at lowest cost)
DEFAULT_PIPELINE_CONFIG = {
    "correction_active": False,
    "evaluation_active": False,
}


def _build_initial_state(message: dict) -> dict:
    """Build PipelineState from incoming queue message."""
    state: dict = {
        "transaction_text": message.get("input_text") or message.get("description") or "",
        "user_context": {
            "province": "ON",
            "entity_type": "corporation",
        },
        "ml_enrichment": {
            "intent_label": message.get("intent_label"),
            "bank_category": message.get("bank_category"),
            "entities": message.get("entities"),
        },
        "iteration": 0,
    }
    for name in AGENT_NAMES:
        state[f"output_{name}"] = []
        state[f"status_{name}"] = NOT_RUN
        state[f"fix_context_{name}"] = []
        state[f"rag_cache_{name}"] = []
    state["embedding_transaction"] = None
    state["embedding_error"] = None
    state["embedding_rejection"] = None
    state["validation_error"] = None
    state["decision"] = None
    state["clarification_questions"] = None
    state["stuck_reason"] = None
    return state


def _extract_result(final_state: dict, message: dict) -> dict:
    """Extract proposed entry and pipeline decision from graph output."""
    i = final_state["iteration"]
    entry_out = final_state.get("output_entry_builder", [])
    journal_entry = entry_out[i] if i < len(entry_out) else None

    decision = final_state.get("decision") or "APPROVED"
    clarification_questions = final_state.get("clarification_questions")
    stuck_reason = final_state.get("stuck_reason")

    # Extract approver confidence for calibration logging (if available)
    approver_out = final_state.get("output_approver", [])
    approver_confidence = None
    if approver_out and i < len(approver_out) and approver_out[i]:
        approver_confidence = approver_out[i].get("confidence")

    return {
        **message,
        "decision": decision,
        "proposed_entry": journal_entry,
        "approver_confidence": approver_confidence,
        "clarification_questions": clarification_questions,
        "stuck_reason": stuck_reason,
        "validation_error": final_state.get("validation_error"),
    }


def execute(message: dict) -> dict:
    logger.info("Processing: %s", message.get("parse_id"))

    initial_state = _build_initial_state(message)
    config = {"configurable": DEFAULT_PIPELINE_CONFIG}

    final_state = app.invoke(initial_state, config)

    return _extract_result(final_state, message)
