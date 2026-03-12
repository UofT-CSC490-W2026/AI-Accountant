"""Reward C: Coherence — penalizes gibberish / token soup, rewards structured text.

Combines anti-gibberish signals (camelCase detection, mega-token penalty) with
pro-coherence signals (sentence structure, math content, reasoning words).

Returns float in [0, 1]:
  - Pure gibberish ("diplomatsCrimeKoreanuador...") -> ~0.2
  - Token soup ("LorLD Giants Habit...") -> ~0.2
  - Coherent math response -> ~0.9-1.0
"""

import re


def reward_coherence(conversation, assistant_response):
    text = assistant_response.strip()
    if len(text) < 20:
        return 0.0

    tokens = text.split()
    if len(tokens) < 3:
        return 0.0

    # --- Anti-gibberish signals ---

    # CamelCase / concatenated token detection
    # LLM gibberish often produces "diplomatsCrimeKoreanuador"
    camel_count = 0
    for t in tokens:
        clean = re.sub(r'[^a-zA-Z]', '', t)
        if len(clean) > 3:
            internal_caps = sum(1 for c in clean[1:] if c.isupper())
            if internal_caps >= 1:
                camel_count += 1
    camel_frac = camel_count / len(tokens)

    # Mega-token penalty (alpha tokens > 15 chars are likely concatenated)
    mega_frac = sum(
        1 for t in tokens if len(re.sub(r'[^a-zA-Z]', '', t)) > 15
    ) / len(tokens)

    # --- Pro-coherence signals ---

    # Sentence structure: period/question followed by space + capital
    sentence_breaks = len(re.findall(r'[.?!]\s+[A-Z]', text))
    has_sentences = min(1.0, sentence_breaks / 2)

    # Mathematical content (equations and numbers)
    has_equations = bool(re.search(r'\d+\s*[+\-*/=]\s*\d+', text))
    num_count = len(re.findall(r'\b\d+\b', text))
    has_numbers = min(1.0, num_count / 3)

    # Common math/reasoning words
    math_words = len(re.findall(
        r'\b(?:so|therefore|thus|if|then|each|total|per|more|less|than|'
        r'how|many|much|left|remaining|bought|sold|gave|has|have|had|'
        r'gets|earned|paid|cost|spent|times|twice|half)\b',
        text, re.I
    ))
    math_word_score = min(1.0, math_words / 3)

    # --- Combine ---
    anti_gibberish = (
        0.60 * (1.0 - min(1.0, camel_frac * 4))
        + 0.40 * (1.0 - min(1.0, mega_frac * 5))
    )
    pro_coherence = (
        0.30 * has_sentences
        + 0.35 * (0.5 * float(has_equations) + 0.5 * has_numbers)
        + 0.35 * math_word_score
    )

    score = 0.4 * anti_gibberish + 0.6 * pro_coherence
    return max(0.0, min(1.0, score))
