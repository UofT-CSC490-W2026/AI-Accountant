import logging

from config import get_settings
from db.dao.chart_of_accounts import DEFAULT_COA
from services.agent.graph.graph_v3_simple import app
from services.agent.graph.state import NOT_RUN, AGENT_NAMES

logger = logging.getLogger(__name__)

settings = get_settings()

_APPROVER_CONFIDENCE_SCORES = {
    "VERY_CONFIDENT": 0.99,
    "SOMEWHAT_CONFIDENT": 0.96,
    "SOMEWHAT_UNCERTAIN": 0.90,
    "VERY_UNCERTAIN": 0.75,
}

_ACCOUNT_CODE_BY_NAME = {
    account_name.casefold(): account_code
    for account_code, account_name, _account_type in DEFAULT_COA
}

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


def _account_code_for_name(account_name: str | None) -> str | None:
    if not account_name:
        return None
    return _ACCOUNT_CODE_BY_NAME.get(str(account_name).strip().casefold())


def _normalize_proposed_entry(journal_entry: dict | None, message: dict) -> tuple[dict | None, list[str]]:
    if not isinstance(journal_entry, dict):
        return None, []

    normalized_lines: list[dict] = []
    unmapped_accounts: list[str] = []

    for index, line in enumerate(journal_entry.get("lines") or []):
        if not isinstance(line, dict):
            continue

        account_name = str(line.get("account_name") or "").strip()
        account_code = str(line.get("account_code") or _account_code_for_name(account_name) or "").strip()
        if account_name and not account_code:
            unmapped_accounts.append(account_name)

        normalized_lines.append(
            {
                "account_code": account_code,
                "account_name": account_name,
                "type": str(line.get("type", "debit")).lower(),
                "amount": float(line.get("amount", 0)),
                "line_order": int(line.get("line_order", index)),
            }
        )

    if not normalized_lines:
        return None, unmapped_accounts

    normalized_entry = {
        "entry": {
            "date": journal_entry.get("date") or message.get("transaction_date"),
            "description": journal_entry.get("description") or message.get("input_text") or message.get("description"),
            "rationale": journal_entry.get("rationale"),
            "origin_tier": journal_entry.get("origin_tier", 3),
            "transaction_id": message.get("transaction_id"),
        },
        "lines": normalized_lines,
    }
    return normalized_entry, unmapped_accounts


def _confidence_for_decision(decision: str, approver_confidence: str | None, requires_human_review: bool) -> dict:
    if requires_human_review:
        overall = 0.0
    elif decision == "APPROVED":
        overall = _APPROVER_CONFIDENCE_SCORES.get(approver_confidence or "", settings.AUTO_POST_THRESHOLD)
    else:
        overall = 0.0
    return {
        "overall": overall,
        "auto_post_threshold": settings.AUTO_POST_THRESHOLD,
    }


def _requires_human_review(
    *,
    decision: str,
    proposed_entry: dict | None,
    validation_error,
    unmapped_accounts: list[str],
) -> bool:
    if decision in {"INCOMPLETE_INFORMATION", "STUCK"}:
        return True
    if validation_error:
        return True
    if unmapped_accounts:
        return True
    return proposed_entry is None


def _build_explanation(
    *,
    decision: str,
    proposed_entry: dict | None,
    clarification_questions: list | None,
    stuck_reason: str | None,
    validation_error,
    unmapped_accounts: list[str],
) -> str:
    if validation_error:
        return "; ".join(str(error) for error in validation_error)

    if decision == "INCOMPLETE_INFORMATION":
        questions = [str(question).strip() for question in clarification_questions or [] if str(question).strip()]
        if questions:
            return "Clarification required: " + " ".join(questions)
        return "Clarification required before the transaction can be posted."

    if decision == "STUCK":
        if stuck_reason:
            return stuck_reason
        if validation_error:
            return "; ".join(str(error) for error in validation_error)
        return "Human review required because the LLM pipeline could not finalize the entry."

    if proposed_entry is None:
        return "Human review required because the LLM pipeline did not produce a journal entry."

    if unmapped_accounts:
        joined = ", ".join(unmapped_accounts)
        return f"Human review required because these account names could not be mapped to account codes: {joined}."

    if proposed_entry:
        rationale = ((proposed_entry.get("entry") or {}).get("rationale"))
        if rationale:
            return str(rationale)

    return "LLM pipeline approved the proposed journal entry."


def _build_clarification(
    *,
    requires_human_review: bool,
    explanation: str,
    clarification_questions: list | None,
) -> dict:
    return {
        "required": requires_human_review,
        "clarification_id": None,
        "reason": explanation,
        "questions": list(clarification_questions or []),
        "status": None,
    }


def _extract_result(final_state: dict, message: dict) -> dict:
    """Extract proposed entry and pipeline decision from graph output."""
    i = final_state["iteration"]
    entry_out = final_state.get("output_entry_drafter", [])
    journal_entry = entry_out[i] if i < len(entry_out) else None

    decision = final_state.get("decision") or "APPROVED"
    clarification_questions = final_state.get("clarification_questions")
    stuck_reason = final_state.get("stuck_reason")

    # Extract approver confidence for calibration logging (if available)
    approver_out = final_state.get("output_approver", [])
    approver_confidence = None
    if approver_out and i < len(approver_out) and approver_out[i]:
        approver_confidence = approver_out[i].get("confidence")

    proposed_entry, unmapped_accounts = _normalize_proposed_entry(journal_entry, message)
    requires_human_review = _requires_human_review(
        decision=decision,
        proposed_entry=proposed_entry,
        validation_error=final_state.get("validation_error"),
        unmapped_accounts=unmapped_accounts,
    )
    confidence = _confidence_for_decision(decision, approver_confidence, requires_human_review)
    explanation = _build_explanation(
        decision=decision,
        proposed_entry=proposed_entry,
        clarification_questions=clarification_questions,
        stuck_reason=stuck_reason,
        validation_error=final_state.get("validation_error"),
        unmapped_accounts=unmapped_accounts,
    )
    clarification = _build_clarification(
        requires_human_review=requires_human_review,
        explanation=explanation,
        clarification_questions=clarification_questions,
    )

    return {
        **message,
        "decision": decision,
        "proposed_entry": proposed_entry,
        "approver_confidence": approver_confidence,
        "clarification_questions": clarification_questions,
        "stuck_reason": stuck_reason,
        "validation_error": final_state.get("validation_error"),
        "confidence": confidence,
        "explanation": explanation,
        "clarification": clarification,
    }


def execute(message: dict) -> dict:
    logger.info("Processing: %s", message.get("parse_id"))

    initial_state = _build_initial_state(message)
    config = {"configurable": DEFAULT_PIPELINE_CONFIG}

    final_state = app.invoke(initial_state, config)

    return _extract_result(final_state, message)
