from __future__ import annotations

import queues


def test_queues_exports_local_worker_compat_symbols() -> None:
    assert callable(queues.dequeue)
    assert callable(queues.enqueue)
