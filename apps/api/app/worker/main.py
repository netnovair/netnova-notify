from __future__ import annotations

import argparse
import logging
import sys

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.worker.runner import Worker

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NetNova Notify background worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process currently due jobs and exit (useful for development and CI).",
    )
    parser.add_argument("--worker-id", default=None, help="Optional worker identifier.")
    args = parser.parse_args(argv)

    setup_logging()
    settings = get_settings()
    try:
        settings.validate_runtime()
    except RuntimeError as exc:
        logger.critical("Invalid configuration: %s", exc)
        return 2

    worker = Worker(settings=settings, worker_id=args.worker_id)
    if args.once:
        processed = worker.run_once(max_batches=100)
        logger.info("Processed %s job(s).", processed)
        return 0
    worker.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
