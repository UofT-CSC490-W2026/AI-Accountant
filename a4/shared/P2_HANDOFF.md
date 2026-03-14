# P2 Handoff

This note is for teammates working on P3 and P4 who need the final P2 artifacts.

## What Is In `a4/shared`

```text
a4/shared/
  configs/
    a4p2/
      a4p2_midtrain_finemath.yaml
      a4p2_midtrain_original.yaml
      a4p2_midtrain_original_eval_only.yaml
      a4p2_sft_metamath.yaml
      a4p2_sft_original.yaml
      a4p2_sft_original_eval_only.yaml
  results/
    a4p2/
      final_pretrained_swiglu_eval.json
      final_midtrain_original_eval.json
      final_midtrain_finemath_eval.json
      final_sft_original_eval.json
      final_sft_metamath_eval.json
  P2_HANDOFF.md
```

## Canonical Checkpoint For Teammates

The canonical checkpoint to share with teammates is the final MetaMath SFT checkpoint:

- `model_tag`: `a4p2-sft-metamath-swiglu`
- `source`: `sft`
- `final_step`: `24633`

Required files:

- `model_024633.pt`
- `meta_024633.json`
- `optim_024633_rank0.pt` if they want optimizer-state continuation

This checkpoint matches the final eval result in:

- [final_sft_metamath_eval.json](CSC490/AI-Accountant/a4/shared/results/a4p2/final_sft_metamath_eval.json)

## What Should And Should Not Go In GitHub

Commit these to GitHub:

- configs in `a4/shared/configs/a4p2/`
- eval JSONs in `a4/shared/results/a4p2/`
- this handoff note
- small metadata files like `meta_024633.json` if useful

Do not commit these to GitHub:

- `model_*.pt`
- `optim_*.pt`

Reason:

- the checkpoint binaries are multiple GB each
- they are too large for normal GitHub use
- they should be shared through OneDrive, Google Drive, or another external file-sharing method

## What Each Shared Item Is For

- `configs/a4p2/`
  - These are the configs used for the final P2 runs.
  - Use them as the reference for hyperparameters, tags, and eval setup.

- `results/a4p2/`
  - These are the final eval outputs used for comparisons in P2.
  - Use them for report context or to compare against later runs.

- external checkpoint share
  - This is where teammates should get `model_024633.pt` and `optim_024633_rank0.pt`
  - `model + meta` are enough for eval-only or for training with `load_optimizer: 0`
  - `optim_024633_rank0.pt` is only needed if they want to continue with optimizer state

## If You Are On A Different Modal Workspace

You will not see my Modal volume automatically.

You should get the checkpoint binaries from the external shared drive, not from GitHub.

You need to upload the checkpoint files into your own workspace's Modal volume under the SFT checkpoint directory:

```text
/data/checkpoints/chatsft_checkpoints/a4p2-sft-metamath-swiglu/
  model_024633.pt
  meta_024633.json
  optim_024633_rank0.pt   # optional unless resuming optimizer
```

The important part is the directory name. It must match the `model_tag`:

```text
a4p2-sft-metamath-swiglu
```

## How To Start From This Checkpoint

If you want to initialize a new run from this P2 checkpoint, use:

```yaml
init_from_source: sft
init_from_tag: a4p2-sft-metamath-swiglu
init_from_step: 24633
```

Use `load_optimizer: 0` unless you explicitly want to continue from the optimizer state.

## Recommended Starting Assumptions

- For evaluation only:
  - Upload `model_024633.pt` and `meta_024633.json`
  - Point your eval config at checkpoint `a4p2-sft-metamath-swiglu` and step `24633`

- For new training initialized from the P2 SFT model:
  - Upload `model_024633.pt` and `meta_024633.json`
  - Use `init_from_source: sft`
  - Use `init_from_tag: a4p2-sft-metamath-swiglu`
  - Use `init_from_step: 24633`
  - Set `load_optimizer: 0`

- For exact continuation from the saved optimizer state:
  - Upload all three files
  - Keep `load_optimizer: 1` only if your script supports continuing from that optimizer state

## Final P2 Results To Reference

- Pretrained baseline:
  - [final_pretrained_swiglu_eval.json](AI-Accountant/a4/shared/results/a4p2/final_pretrained_swiglu_eval.json)

- Original midtraining:
  - [final_midtrain_original_eval.json](AI-Accountant/a4/shared/results/a4p2/final_midtrain_original_eval.json)

- FineMath midtraining:
  - [final_midtrain_finemath_eval.json](AI-Accountant/a4/shared/results/a4p2/final_midtrain_finemath_eval.json)

- Original SFT:
  - [final_sft_original_eval.json](AI-Accountant/a4/shared/results/a4p2/final_sft_original_eval.json)

- MetaMath SFT:
  - [final_sft_metamath_eval.json](AI-Accountant/a4/shared/results/a4p2/final_sft_metamath_eval.json)

## Recommended First Step For Teammates

1. Read the final MetaMath SFT config:
   - [a4p2_sft_metamath.yaml](AI-Accountant/a4/shared/configs/a4p2/a4p2_sft_metamath.yaml)
2. Upload the checkpoint files into your own Modal volume under `chatsft_checkpoints/a4p2-sft-metamath-swiglu/`.
3. Decide whether you only need eval or want to initialize new training from it.
4. For any new run that starts from this checkpoint, use `init_from_source: sft`, `init_from_tag: a4p2-sft-metamath-swiglu`, `init_from_step: 24633`, and usually `load_optimizer: 0`.

## Notes

- The canonical P2 checkpoint is the MetaMath SFT final checkpoint, not the original SFT checkpoint.
- The final original SFT eval result is still included in `results/a4p2/`.
- The large `.pt` checkpoint files should be shared outside GitHub.
- If you need another checkpoint from P2 that is not already on the external shared drive, ask before starting a long run.

## Git Workflow For P3 And P4

Use separate branches in the two repos.

- In `AI-Accountant`:
  - Branch from `a4`
  - Do P3 work in `a4/p3/`
  - Do P4 work in `a4/p4/`
  - Keep shared artifacts and handoff material in `a4/shared/`

- In `nanochat`:
  - Branch from `a4-p2`, not from `main`
  - Reason: the P2 runs and shared checkpoint were produced against the `a4-p2` code path
  - Branching from `main` risks losing code changes needed for compatibility with the P2 checkpoint and configs

Recommended naming:

- `AI-Accountant`: `a4-p3-<name>` or `a4-p4-<name>`
- `nanochat`: `a4-p3-<name>` or `a4-p4-<name>`, created from `a4-p2`

## Important Modal Note

Modal does not use your laptop copy of `nanochat`.

The Modal image clones `https://github.com/seonghyunban/nanochat.git` and then checks out whatever branch name is in `nanochat_ref`.

That means:

- Any `nanochat` branch used in a config must already be pushed to the remote repo before launching Modal
- The YAML should set `nanochat_ref` to the exact branch name teammates want Modal to run

Example:

- `AI-Accountant` branch: `a4-p3-alice`
- `nanochat` branch: `a4-p3-alice` created from `a4-p2`
- config entry: `nanochat_ref: a4-p3-alice`
