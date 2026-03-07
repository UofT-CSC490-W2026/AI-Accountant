# A4 P2 Base Model Lock and Workflow

This document freezes the A3 checkpoint used as the Part 2 starting artifact and maps the exact A4 P2 run workflow.

## Canonical Starting Checkpoint

- Checkpoint tag: `nano-baseline-fp8-full`
- Checkpoint step: `4357`
- Modal volume path:
  - `base_checkpoints/nano-baseline-fp8-full/model_004357.pt`
  - `base_checkpoints/nano-baseline-fp8-full/meta_004357.json`
- Tokenizer (shared 65,536-vocab tokenizer):
  - `tokenizer/tokenizer.pkl`
  - `tokenizer/token_bytes.pt`

## Source Script Mapping (nanochat)

- SFT: `scripts.chat_sft`
- Midtraining (continued pretraining): `scripts.base_train`
- Chat-style GSM8K eval helper: `scripts.chat_eval`

## A4 P2 Config Pack

All configs are in `a4/p2/configs/`.

1. `a4p2_pretrained_gsm8k_eval.yaml`
   - Eval-only on pretrained base checkpoint (`nano-baseline-fp8-full@4357`)
   - Runs standard `bpb` + custom GSM8K/BPB
2. `a4p2_sft_original.yaml`
   - SFT run from pretrained checkpoint with original SFT recipe
   - Runs custom GSM8K + custom BPB
3. `a4p2_sft_altmix.yaml`
   - SFT run from pretrained checkpoint with altered supervision mix (`mmlu_epochs`, `gsm8k_epochs`)
   - Runs custom GSM8K + custom BPB
4. `a4p2_midtrain_original.yaml`
   - Midtraining run from pretrained checkpoint using base-train continuation recipe
   - Runs standard `bpb` + custom GSM8K/BPB
5. `a4p2_midtrain_altmix.yaml`
   - Midtraining ablation variant (reduced shard budget via `data_shards: 8`)
   - Runs standard `bpb` + custom GSM8K/BPB

## Custom Eval Hooks

- `a4/p2/evals/gsm8k_eval_base.py`
  - Loads checkpoint source=`base`, evaluates GSM8K, and computes BPB.
- `a4/p2/evals/gsm8k_eval_sft.py`
  - Loads checkpoint source=`sft`, evaluates GSM8K, and computes BPB.

Optional limit for quick checks:

- Set env var `A4P2_GSM8K_MAX_PROBLEMS=<N>` before running.
- Unset (default) means full GSM8K test split.
- Optional BPB budget knobs:
  - `A4P2_BPB_DEVICE_BATCH_SIZE` (default `16`)
  - `A4P2_BPB_SPLIT_TOKENS` (default `4*524288`)

## Run Order

From repo root:

```powershell
modal run --detach a4/shared/scripts/main.py --config a4/p2/configs/a4p2_pretrained_gsm8k_eval.yaml
modal run --detach a4/shared/scripts/main.py --config a4/p2/configs/a4p2_sft_original.yaml
modal run --detach a4/shared/scripts/main.py --config a4/p2/configs/a4p2_sft_altmix.yaml
modal run --detach a4/shared/scripts/main.py --config a4/p2/configs/a4p2_midtrain_original.yaml
modal run --detach a4/shared/scripts/main.py --config a4/p2/configs/a4p2_midtrain_altmix.yaml
```

## Fast Smoke Run (before full jobs)

Use this first to verify setup -> SFT -> midtraining -> eval pipeline:

```powershell
modal run --detach a4/shared/scripts/main.py --config a4/p2/configs/a4p2_pipeline_smoke.yaml
```

This run is deliberately small:
- 20 SFT iterations
- 20 midtraining iterations
- GSM8K eval capped to 32 problems
- small BPB token budget in custom eval

## Runner Notes

- Runner now supports checkpoint branching via training args:
  - `init_from_source`, `init_from_tag`, `init_from_step`
- This allows multiple SFT/midtraining variants without overwriting the original base tag.
- Runner resolves `final_step` from actual checkpoint files after training, which is required for `chat_sft` runs where `num_iterations=-1`.
