from __future__ import annotations

import importlib

__all__ = ["process"]


def __getattr__(name: str):
    if name == "process":
        return importlib.import_module(f"{__name__}.service")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
