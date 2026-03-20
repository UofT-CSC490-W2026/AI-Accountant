import logging

from config import get_settings
from queues import dequeue
from services.flywheel.process import process

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("flywheel")


def main() -> None:
    settings = get_settings()
    queue_url = settings.SQS_QUEUE_FLYWHEEL
    logger.info("Flywheel worker starting, polling %s", queue_url)

    while True:
        message = dequeue(queue_url)
        if message is not None:
            process(message)


if __name__ == "__main__":
    main()
