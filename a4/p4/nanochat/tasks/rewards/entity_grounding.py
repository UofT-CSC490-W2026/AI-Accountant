"""Reward D: Entity Grounding — rewards mentioning entities from the question.

Extracts proper nouns (capitalized words not at sentence start) from the question
and checks what fraction appear in the response. Forces the model to respond to
the actual problem rather than a memorized alternative.

Returns float in [0, 1]:
  - Response about correct entities -> ~1.0
  - Response about different entities -> ~0.0
  - Question with no proper nouns -> 1.0 (conservative fallback)
"""

import re


def _get_entities(text):
    """Extract proper nouns: capitalized words not at sentence start, len > 2."""
    entities = set()
    sentences = re.split(r'[.!?]\s+', text)
    for sent in sentences:
        words = sent.split()
        for i, w in enumerate(words):
            clean = re.sub(r'[^a-zA-Z]', '', w)
            if clean and clean[0].isupper() and len(clean) > 2 and i > 0:
                entities.add(clean.lower())
    return entities


def reward_entity_grounding(conversation, assistant_response):
    question = conversation['messages'][0]['content']

    q_entities = _get_entities(question)
    if not q_entities:
        return 1.0

    r_entities = _get_entities(assistant_response)
    overlap = q_entities & r_entities
    return len(overlap) / len(q_entities)
