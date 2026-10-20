"""In-process worker thread.

Render's free plan cannot run a background worker or a cron job, so on that
target the API itself drains the queue. The thread is a thin wrapper around the
same :class:`~app.worker.runner.Worker` used by ``python -m app.worker.main``:

* it never touches Telegram or the database before the application is ready;
* a crash inside the loop is logged and retried after the poll interval instead
  of killing the API process;
* jobs are claimed with ``FOR UPDATE SKIP LOCKED``, so running this thread in
  several API replicas (or alongside the GitHub Actions worker) cannot produce a
  duplicate send.

Set ``EMBEDDED_WORKER=true`` to enable it. Production with a real worker process
should leave it off.
"""

from __future__ import annotations

import logging
import threading
import uuid

from app.adapters.telegram.base import TelegramAdapter
from app.core.config import Settings
from app.worker.runner import Worker

logger = logging.getLogger(__name__)


class EmbeddedWorker:
    def __init__(
        self,
        settings: Settings,
        adapter: TelegramAdapter,
        *,
        worker_id: str | None = None,
        poll_interval: float | None = None,
    ) -> None:
        self.worker = Worker(
            settings=settings,
            adapter=adapter,
            worker_id=worker_id or f"embedded-{uuid.uuid4().hex[:8]}",
        )
        self.poll_interval = poll_interval or settings.worker_poll_interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = False

    # ------------------------------------------------------------------
    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._thread = threading.Thread(
            target=self._loop, name="netnova-embedded-worker", daemon=True
        )
        self._thread.start()
        logger.info(
            "Embedded worker started (poll=%ss, adapter=%s)",
            self.poll_interval,
            self.worker.adapter.mode,
        )

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        logger.info("Embedded worker stopped")

    # ------------------------------------------------------------------
    def _loop(self) -> None:
        # A short delay lets the lifespan finish before the first database access.
        while not self._stop.wait(1.0):
            try:
                processed = self.worker.run_once()
            except Exception:  # noqa: BLE001 - the thread must survive any job failure
                logger.exception("Embedded worker iteration failed")
            else:
                if processed:
                    logger.info("Embedded worker processed %s job(s)", processed)
            if self._stop.wait(self.poll_interval):
                break
