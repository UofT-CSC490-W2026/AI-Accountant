"""
One-shot script to initialize all Qdrant collections.
Run via: python -m vectordb.init
Used as the docker-compose qdrant-init service entrypoint.
"""

import sys
import time

from vectordb.client import get_qdrant_client
from vectordb.collections import init_collections


def main() -> None:
    for attempt in range(10):
        try:
            client = get_qdrant_client()
            client.get_collections()
            break
        except Exception as e:
            if attempt == 9:
                print(f"Qdrant not ready after 10 attempts: {e}", file=sys.stderr)
                sys.exit(1)
            time.sleep(2)

    init_collections(client)
    print("Qdrant collections initialized.")


if __name__ == "__main__":
    main()
