import logging

from config import get_settings
from queues import dequeue
from services.agent.execute import process

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("agent")


def main() -> None:
    settings = get_settings()
    queue_url = settings.SQS_QUEUE_AGENT
    logger.info("Agent worker starting, polling %s", queue_url)

    while True:
        message = dequeue(queue_url)
        if message is not None:
            process(message)


if __name__ == "__main__":
    main()
