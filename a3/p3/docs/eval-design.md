# Eval Design: Positional Perplexity

## Task

Measure per-position cross-entropy loss on long documents to demonstrate that context extension worked. The short checkpoint (trained at `max_seq_len=512`) should show catastrophic loss beyond position 512, while the extended checkpoint (resumed at `max_seq_len=2048`) should show smooth loss across the full range.

This is the standard evaluation method for context extension — used by Position Interpolation (Chen et al., 2023), YaRN (Peng et al., 2023), and LongRoPE (Ding et al., 2024).

## Why This Task

1. **Scale-independent**: The signal comes from positional encoding (RoPE) working or failing, not from model intelligence. A 10M-param model with broken positional encodings beyond position 512 will show dramatically higher loss there — just as reliably as a 7B model.

2. **Dramatic expected signal**: When a RoPE model encounters positions it never trained on, attention scores become unstable and perplexity spikes by orders of magnitude. The PI paper reports >10^3 perplexity for direct extrapolation.

3. **No generation required**: Forward passes and loss recording only. No prompt engineering, no output parsing.

## Why Not Alternatives

- **Needle-in-a-haystack**: Requires instruction following and fact recall. Models at 10–50M params cannot do this — both checkpoints would score 0%.
- **Long-range cloze**: Harder, noisier version of perplexity that requires capabilities small models lack. High implementation cost, poor data availability.

## Metric

Per-position cross-entropy loss, bucketed into 128-token windows (16 buckets for a 2048-token sequence).

**Outputs**:
- Line plot: mean loss per position bucket, two lines (short checkpoint, extended checkpoint)
- Scalar table: mean loss at positions 0–512 vs 512–2048 for each checkpoint
- Delta: the difference between the two regions for each checkpoint

## Data Source

**PG19 test split** (books from Project Gutenberg, guaranteed long documents).

Why not FineWeb-edu: nanochat trains on `HuggingFaceFW/fineweb-edu` (`sample-100BT`). Using the same source for eval risks data contamination. PG19 is a different domain (books vs web), standard in the literature (used by PI, YaRN, LongRoPE), and every document is far longer than 2048 tokens.

**Eval set**: ~200 documents from PG19 test split, each truncated to 2048 tokens. This provides enough averaging to produce smooth curves.

## Success Criteria

1. **Short checkpoint**: Mean loss at positions 512–2048 is significantly higher than at positions 0–512 (expect >2x or catastrophic spike).
2. **Extended checkpoint**: Mean loss at positions 512–2048 is comparable to or lower than at positions 0–512 (longer context = more information = lower loss).
3. **Visual**: The two loss curves are obviously different in the plot — no statistical test needed, the gap should be dramatic.

## Implementation Sketch

```python
import torch
from nanochat.checkpoint_manager import load_model

def positional_perplexity(model_tag, step, documents, seq_len=2048, device="cuda"):
    """
    Compute per-position cross-entropy loss for a nanochat checkpoint.

    Args:
        model_tag: checkpoint directory name (e.g., "d6-i2000-s512")
        step: training step to load
        documents: list of token ID tensors, each >= seq_len tokens
        seq_len: sequence length to evaluate at
        device: "cuda", "cpu", or "mps"

    Returns:
        loss_by_position: tensor of shape (seq_len,), mean loss at each position
    """
    # load_model returns (model, tokenizer, meta_data)
    # source="base" looks in base_checkpoints/
    # phase="eval" sets model.eval() and disables dropout
    model, tokenizer, meta = load_model(
        "base", device, phase="eval", model_tag=model_tag, step=step
    )

    # accumulate per-position loss
    total_loss = torch.zeros(seq_len, device=device)
    count = 0

    with torch.no_grad():
        for doc_tokens in documents:
            # truncate to seq_len + 1 (need next-token targets)
            input_ids = doc_tokens[:seq_len].unsqueeze(0).to(device)
            targets = doc_tokens[1:seq_len + 1].unsqueeze(0).to(device)

            # forward pass — GPT returns (logits, loss) when targets provided,
            # but for per-position loss we compute it manually
            logits = model(input_ids)  # (1, seq_len, vocab_size)
            if isinstance(logits, tuple):
                logits = logits[0]

            # per-position cross-entropy
            loss = torch.nn.functional.cross_entropy(
                logits.squeeze(0),  # (seq_len, vocab_size)
                targets.squeeze(0),  # (seq_len,)
                reduction="none"     # (seq_len,) — loss at each position
            )
            total_loss += loss
            count += 1

    return total_loss / count  # mean loss at each position


def bucket_losses(loss_by_position, bucket_size=128):
    """Bucket per-position losses into windows."""
    n_buckets = len(loss_by_position) // bucket_size
    buckets = loss_by_position[:n_buckets * bucket_size].reshape(n_buckets, bucket_size)
    return buckets.mean(dim=1)  # (n_buckets,)
```

### Loading data

```python
from datasets import load_dataset

# PG19 test split — every document is a full book (>> 2048 tokens)
ds = load_dataset("pg19", split="test")

# tokenize with nanochat's tokenizer (GPT-2 BPE)
# filter for docs with at least seq_len + 1 tokens
eval_docs = []
for doc in ds:
    tokens = tokenizer.encode(doc["text"])
    if len(tokens) >= 2049:
        eval_docs.append(torch.tensor(tokens[:2049]))
    if len(eval_docs) >= 200:
        break
```

### Producing the plot

```python
import matplotlib.pyplot as plt

short_loss = bucket_losses(positional_perplexity("d6-i2000-s512", step=2000, ...))
extended_loss = bucket_losses(positional_perplexity("d6-i2000-s2048", step=3000, ...))

positions = [f"{i*128}-{(i+1)*128}" for i in range(len(short_loss))]

plt.figure(figsize=(10, 5))
plt.plot(short_loss.cpu(), label="Short checkpoint (512)", marker="o")
plt.plot(extended_loss.cpu(), label="Extended checkpoint (2048)", marker="s")
plt.axvline(x=4, color="gray", linestyle="--", label="Position 512")
plt.xlabel("Position bucket (128 tokens each)")
plt.ylabel("Cross-entropy loss")
plt.title("Per-position loss: short vs extended context")
plt.legend()
plt.savefig("positional_perplexity.png", dpi=150, bbox_inches="tight")
```

## Notes

- Model tag names and step numbers in the sketch are placeholders — actual values come from training runs.
- The `model(input_ids)` forward pass API needs verification at implementation time — nanochat's GPT may return `(logits, loss)` or just `logits` depending on whether targets are passed. The sketch handles both cases.
- PG19 uses GPT-2 tokenization by default. Nanochat also uses GPT-2 BPE (via `rustbpe`), so tokenizer alignment is not an issue.
- RoPE frequencies are pre-computed at 10x the training `max_seq_len` (Phase 2 verification). Both checkpoints can process 2048-token inputs at inference time.

## References

1. Chen, S., Wong, S., Chen, L., & Tian, Y. (2023). *Extending Context Window of Large Language Models via Positional Interpolation*. arXiv:2306.15595.

2. Peng, B., Quesnelle, J., Fan, H., & Shippole, E. (2023). *YaRN: Efficient Context Window Extension of Large Language Models*. ICLR 2024. arXiv:2309.00071.

3. Ding, Y., Zhang, L., Jia, C., et al. (2024). *LongRoPE: Extending LLM Context Window Beyond 2 Million Tokens*. arXiv:2402.13753.
