from __future__ import annotations

import modal


WANDB_PROJECT = "490-autobook-ml"
VOLUME_PATH = "/ml_artifacts"

app = modal.App("autobook-ml-training")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git")
    .pip_install(
        "torch==2.5.1",
        index_url="https://download.pytorch.org/whl/cu124",
    )
    .pip_install(
        "accelerate==1.1.1",
        "datasets==3.1.0",
        "evaluate==0.4.3",
        "numpy==1.26.4",
        "pyyaml==6.0.2",
        "scikit-learn==1.5.2",
        "sentencepiece==0.2.0",
        "seqeval>=1.2.2",
        "tiktoken==0.9.0",
        "transformers==4.46.3",
        "wandb==0.18.7",
    )
    .add_local_python_source("ml_workspace")
)

volume = modal.Volume.from_name("autobook-ml-artifacts", create_if_missing=True)
wandb_secret = modal.Secret.from_name("wandb-secret")
