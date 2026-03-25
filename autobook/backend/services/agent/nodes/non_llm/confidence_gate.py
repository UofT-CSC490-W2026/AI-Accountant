"""Confidence gate node — routes to posting or clarification.

Pure Python logic, no LLM. Applies Platt scaling calibration to
the approver's raw confidence and compares against threshold.
"""
from config import get_settings
from services.agent.graph.state import PipelineState
from services.agent.utils.calibration import calibrate_confidence


def confidence_gate_node(state: PipelineState) -> dict:
    """Calibrate confidence and set routing decision."""
    i = state["iteration"]
    approver_out = state.get("output_approver", [])

    # When evaluation is off, approver was skipped — auto-post
    if i >= len(approver_out) or not approver_out[i]:
        return {"route": "post"}

    raw_confidence = approver_out[i]["confidence"]
    calibrated = calibrate_confidence(raw_confidence)
    threshold = get_settings().AUTO_POST_THRESHOLD

    return {"route": "post" if calibrated >= threshold else "clarify"}
