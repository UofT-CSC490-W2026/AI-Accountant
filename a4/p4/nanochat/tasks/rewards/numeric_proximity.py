"""Reward B: Numeric Proximity — partial credit based on distance to gold answer."""

from tasks.rewards.gsm8k_utils import GSM_RE


def reward_numeric_proximity(conversation, assistant_response):
    assistant_message = conversation['messages'][-1]
    last_text_part = assistant_message['content'][-1]['text']
    ref_match = GSM_RE.search(last_text_part)
    if not ref_match:
        return 0.0
    ref_str = ref_match.group(1).strip().replace(",", "")
    pred_match = GSM_RE.search(assistant_response)
    if not pred_match:
        return 0.0
    pred_str = pred_match.group(1).strip().replace(",", "")
    try:
        ref_num = float(ref_str)
        pred_num = float(pred_str)
    except ValueError:
        return 0.0
    distance = abs(pred_num - ref_num)
    denominator = abs(ref_num) + 1.0
    return max(0.0, 1.0 - distance / denominator)
