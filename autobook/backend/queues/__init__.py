import importlib


def __getattr__(name):
    if name == "sqs":
        return importlib.import_module("queues.sqs")
    if name == "pubsub":
        return importlib.import_module("queues.pubsub")
    raise AttributeError(f"module 'queues' has no attribute {name!r}")
