# Eval Design: Decisions After Research (3.3)

## Checkpoints Under Evaluation

| # | Checkpoint | Training Strategy | Purpose |
|---|-----------|-------------------|---------|
| A | Short (`pico-short`, step ~929) | Trained at seq_len=512 to completion (auto-compute) | Baseline — no long-context ability |
| B | Extended (`pico-short`, step ~1429) | Trained at 512 to completion, then 500 steps at 2048 | Cheap path — did extension work? |
| C | Full (`pico-full`, step ~929) | Trained at seq_len=2048 from scratch (auto-compute) | Gold standard — what "real" 2048 training looks like |

## Decisions

| # | Decision | Value | Justification | Confirm |
|---|----------|-------|---------------|---------|
| 1 | Custom eval task | Positional perplexity | Directly measures the effect of context extension — can the model handle positions beyond its training length? Standard benchmarks (HellaSwag, PIQA) measure general capability, not context length, so they can't isolate whether extension worked. | |
| 2 | Built-in evals | BPB + CORE (22 tasks) | Free to run (already in nanochat). BPB measures overall language modeling quality; CORE measures general task capability. Together they show whether extension or full training affected anything beyond positional handling. | |
| 3 | Custom eval dataset | PG19 test split | Avoids data contamination (nanochat trains on FineWeb-edu), standard in context extension literature (PI, YaRN, LongRoPE), every document is far longer than 2048 tokens. | |
| 4 | Bucketing | 128-token windows (16 buckets for 2048 tokens) | Enough spatial resolution to see where the loss spike begins while averaging enough tokens per bucket for smooth curves. | |
| 5 | Sample size | All PG19 test split documents | Use the full test split — no reason to subsample when compute is cheap. | |
| 6 | Output deliverables | 1 line plot (3 lines) + 1 BPB table (3 checkpoints) + 1 CORE table (3 checkpoints) | Line plot shows positional perplexity for all three checkpoints; BPB and CORE tables show overall quality and task capability comparisons. | |
| 7 | Success criteria (part 1) | Spike vs smooth: short checkpoint spikes after position 512; extended and full checkpoints are smooth | Proves context extension mechanically worked — RoPE adapted, loss recovered. | |
| 8 | Success criteria (part 2) | Cheap vs expensive: extended checkpoint matches full-from-scratch on all evals | Proves the cheap path (train short, extend later) is a viable alternative to training at full context from the start. | |
| 9 | Third training run | Full-from-scratch: depth=6, seq_len=2048, auto-compute ~929 iters, model_tag `pico-full` | Fair comparison — same model, same data budget (auto-compute gives same iteration count). Without this baseline, we can only show extension doesn't break — not that it's a good strategy. | |
