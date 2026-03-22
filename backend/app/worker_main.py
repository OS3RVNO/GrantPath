from __future__ import annotations

import logging
import signal
import threading

from app.runtime import runtime

logger = logging.getLogger(__name__)


def main() -> None:
    stop_event = threading.Event()

    def _stop(*_args) -> None:
        runtime.shutdown()
        stop_event.set()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    logger.info(
        "Starting EIP background worker runtime on %s with role=%s",
        runtime.runtime_status().host,
        runtime.runtime_role,
    )
    try:
        while not stop_event.wait(3600):
            continue
    finally:
        runtime.shutdown()


if __name__ == "__main__":
    main()
