from tasks.rewards.correctness import reward_correctness
from tasks.rewards.format_compliance import reward_format_compliance
from tasks.rewards.numeric_proximity import reward_numeric_proximity
from tasks.rewards.coherence import reward_coherence
from tasks.rewards.entity_grounding import reward_entity_grounding
from tasks.rewards.number_grounding import reward_number_grounding

REWARD_REGISTRY = {
    "correctness": reward_correctness,
    "format_compliance": reward_format_compliance,
    "numeric_proximity": reward_numeric_proximity,
    "coherence": reward_coherence,
    "entity_grounding": reward_entity_grounding,
    "number_grounding": reward_number_grounding,
}
