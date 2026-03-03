"""Declarative infrastructure: constants, Modal app, image, volume, secrets, setup."""

import re

import modal

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WANDB_PROJECT = "490-autobook-a3"
NANOCHAT_DIR = "/root/nanochat"
VOLUME_PATH = "/data/checkpoints"
CKPT_SUBDIR = "base_checkpoints"
EVAL_SUBDIR = "base_eval"
CUSTOM_EVAL_SUBDIR = "custom_evals"
CKPT_STEP_RE = re.compile(r"model_(\d+)\.pt$")

# ---------------------------------------------------------------------------
# App, Image, Volume, Secret
# ---------------------------------------------------------------------------

app = modal.App("a3-nanochat")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git")
    .pip_install(
        "torch==2.9.1",
        index_url="https://download.pytorch.org/whl/cu128",
    )
    .pip_install(
        "datasets>=4.0.0",
        "psutil>=7.1.0",
        "regex>=2025.9.1",
        "rustbpe>=0.1.0",
        "scipy>=1.15.3",
        "setuptools>=80.9.0",
        "tabulate>=0.9.0",
        "tiktoken>=0.11.0",
        "tokenizers>=0.22.0",
        "transformers>=4.57.3",
        "wandb>=0.21.3",
        "zstandard>=0.25.0",
    )
    .run_commands("git clone https://github.com/seonghyunban/nanochat.git /root/nanochat")
    .add_local_python_source("shared", "runners")
)

eval_image = image.add_local_dir("a3/p3/evals", remote_path="/root/evals")

volume = modal.Volume.from_name("a3-checkpoints", create_if_missing=True)

wandb_secret = modal.Secret.from_name("wandb-secret")

# ---------------------------------------------------------------------------
# Tokenizer source
# ---------------------------------------------------------------------------

HF_TOKENIZER_BASE = "https://huggingface.co/sdobson/nanochat/resolve/main"
TOKENIZER_FILES = ["tokenizer.pkl", "token_bytes.pt"]


# ---------------------------------------------------------------------------
# Setup (idempotent): download tokenizer + data shards to Volume
# ---------------------------------------------------------------------------

@app.function(
    image=image,
    volumes={VOLUME_PATH: volume},
    timeout=3600,
)
def setup(nanochat_ref: str):
    """Download tokenizer and data shards to Volume. Idempotent."""
    import os
    import subprocess
    import urllib.request

    from shared.helpers import checkout_ref

    os.environ["NANOCHAT_BASE_DIR"] = VOLUME_PATH
    os.chdir(NANOCHAT_DIR)
    checkout_ref(nanochat_ref)

    # Tokenizer
    tokenizer_dir = os.path.join(VOLUME_PATH, "tokenizer")
    all_exist = all(
        os.path.exists(os.path.join(tokenizer_dir, f)) for f in TOKENIZER_FILES
    )
    if all_exist:
        print("[setup] Tokenizer already exists, skipping.")
    else:
        os.makedirs(tokenizer_dir, exist_ok=True)
        for fname in TOKENIZER_FILES:
            url = f"{HF_TOKENIZER_BASE}/{fname}"
            dest = os.path.join(tokenizer_dir, fname)
            print(f"[setup] Downloading {fname}...")
            urllib.request.urlretrieve(url, dest)
        print("[setup] Tokenizer downloaded.")

    # Data shards
    print("[setup] Ensuring data shards exist...")
    subprocess.run(["python", "-m", "nanochat.dataset", "-n", "8"], check=True)

    volume.commit()
    print("[setup] Done.")
