import json
import logging

from config import get_settings
from queues import dequeue
from services.normalizer.aws import handler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("normalizer")


def main() -> None:
    settings = get_settings()
    queue_url = settings.SQS_QUEUE_NORMALIZER
    logger.info("Normalizer worker starting, polling %s", queue_url)

    while True:
        message = dequeue(queue_url)
        if message is not None:
            handler({"Records": [{"body": json.dumps(message)}]}, None)


if __name__ == "__main__":
    main()
