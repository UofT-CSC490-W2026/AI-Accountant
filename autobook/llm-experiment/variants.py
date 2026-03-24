"""Stage 1 ablation variant configs.

Config-driven — same graph, different RunnableConfig flags.
Only single_agent needs a separate graph.

Each config dict is passed via RunnableConfig["configurable"].
Empty dict = all features on (full pipeline).
"""

# Variant configs for RunnableConfig["configurable"]
VARIANTS: dict[str, dict | None] = {
    # None = separate graph (llm-experiment/single_agent/)
    "single_agent": None,

    # Classifiers + entry builder only (no correction, no evaluation)
    "classify_and_build": {
        "correction_pass": False,
        "evaluation_active": False,
    },

    # Classifiers + correctors + entry builder (no evaluation)
    "with_correction": {
        "evaluation_active": False,
    },

    # Classifiers + entry builder + approver/diagnostician (no correction)
    "with_evaluation": {
        "correction_pass": False,
    },

    # Full pipeline — all features on
    "full_pipeline": {},
}
