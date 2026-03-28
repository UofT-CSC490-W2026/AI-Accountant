"""Prepare A4 P2 alternative datasets directly on the Modal volume.

Examples:
  modal run a4/shared/scripts/prepare_p2_data.py --dataset metamath --smoke
  modal run a4/shared/scripts/prepare_p2_data.py --dataset metamath
  modal run a4/shared/scripts/prepare_p2_data.py --dataset finemath --smoke
  modal run a4/shared/scripts/prepare_p2_data.py --dataset finemath
"""

from __future__ import annotations

import os

from shared.infra import NANOCHAT_DIR, VOLUME_PATH, app, image, volume


@app.function(
    image=image,
    volumes={VOLUME_PATH: volume},
    timeout=8 * 3600,
)
def prepare_dataset(dataset: str, smoke: bool = False) -> str:
    import subprocess

    os.environ["NANOCHAT_BASE_DIR"] = VOLUME_PATH
    os.chdir(NANOCHAT_DIR)

    if dataset == "metamath":
        max_examples = 5000 if smoke else 50000
        out_path = (
            "/data/checkpoints/a4_p2_data/metamathqa_5k.jsonl"
            if smoke
            else "/data/checkpoints/a4_p2_data/metamathqa_50k.jsonl"
        )
        cmd = [
            "python",
            "-m",
            "a4.p2.scripts.prepare_metamath_jsonl",
            f"--max-examples={max_examples}",
            f"--output={out_path}",
        ]
    elif dataset == "finemath":
        max_docs = 20000 if smoke else 200000
        base_mix_docs = 5000 if smoke else 50000
        out_dir = (
            "/data/checkpoints/a4_p2_data/finemath_4plus_mix_smoke"
            if smoke
            else "/data/checkpoints/a4_p2_data/finemath_4plus_mix"
        )
        cmd = [
            "python",
            "-m",
            "a4.p2.scripts.prepare_finemath_parquet",
            f"--max-docs={max_docs}",
            f"--base-mix-dir={VOLUME_PATH}/base_data",
            f"--base-mix-docs={base_mix_docs}",
            f"--output-dir={out_dir}",
        ]
    else:
        raise ValueError(f"Unsupported dataset: {dataset}")

    print(f"[prep] Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    volume.commit()
    return out_path if dataset == "metamath" else out_dir


@app.local_entrypoint()
def main(dataset: str, smoke: bool = False):
    out = prepare_dataset.remote(dataset=dataset, smoke=smoke)
    print(f"[prep] Ready: {out}")
