# P3 → P4 Interface

> What P3 delivers to P4, and what P4 needs it for.

---

## What P3 Delivers

All values are **TBD** — filled in after P3 runs complete (Phase 6).

### Picochat Config

| Field | Value |
|-------|-------|
| Depth | TBD |
| Short seq_len (stage 1) | TBD |
| Extended seq_len (stage 2) | TBD |
| Nanochat branch/tag | TBD |

### Best Checkpoint

| Field | Value |
|-------|-------|
| Model tag | TBD |
| Final step (short-context) | TBD |
| Final step (extended-context) | TBD |
| Path on Modal Volume | TBD |

### Key Metrics

| Metric | Short-Context Checkpoint | Extended-Context Checkpoint |
|--------|--------------------------|----------------------------|
| val_bpb | TBD | TBD |
| Custom eval score | TBD | TBD |

### Cost

| Field | Value |
|-------|-------|
| GPU type | TBD |
| Total runtime (hours) | TBD |
| Estimated cost ($) | TBD |

### Tracking

| Field | Value |
|-------|-------|
| W&B run link (short) | TBD |
| W&B run link (extended) | TBD |
| Git commit hash | TBD |

---

## What P4 Needs This For

### Scaling Law Prediction
- Use picochat param count + val_bpb to predict nanochat (full-size) performance
- Compare predicted vs actual after P4 training

### Emergent Abilities Comparison
- Find 10 questions nanochat answers but picochat cannot
- Use picochat checkpoint from P3 as the "smaller model" baseline
