"""
featherless_runner.py
────────────────────────────────────────────────────────────────────────────
Purpose:
    Non-blocking background worker that feeds real Gamana frame snapshots to
    FeatherlessTrafficService.generate_strategy() without touching the frame
    processing loop's timing.

Why it exists:
    The video pipeline runs at 25-30 fps.  A Featherless API call takes
    ~2-5 seconds.  Running it inline would drop every frame.
    This runner decouples them:
        - main loop  → submit_snapshot()  [queue.put_nowait, microseconds]
        - background → processes snapshots one at a time in its own thread

How it works:
    A single daemon thread pulls the LATEST snapshot from a queue of size 1
    (replacing stale data automatically), calls generate_strategy(), logs the
    result, stores it in _last_recommendation, and is accessible via
    get_last_recommendation().

Phase 2 role:
    Instantiated once after run_server() in main.py.
    Receives snapshots via submit_snapshot() every AI_EVERY_N_FRAMES frames.
    Stores recommendations for Phase 3 / API exposure.

Phase 3 readiness:
    server.py can expose GET /api/ai_recommendation returning
    runner.get_last_recommendation().to_dict() without any pipeline changes.
────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import logging
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

# ── Resolve backend/ onto sys.path when run standalone ───────────────────────
_BACKEND_DIR = Path(__file__).parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from services.featherless_service import FeatherlessTrafficService
from services.pipeline_adapter import build_intersection_state
from models.featherless_response import FeatherlessResponse
from services.featherless_config import FEATHERLESS_ENABLED

_log = logging.getLogger("featherless")

# ── How often to query the AI (configurable via env) ─────────────────────────
import os
AI_EVERY_N_FRAMES: int = int(os.getenv("FEATHERLESS_EVERY_N_FRAMES", "90"))


# ─────────────────────────────────────────────────────────────────────────────
class FeatherlessRunner:
    """
    Non-blocking AI advisory runner.

    Usage in main.py
    ----------------
        runner = FeatherlessRunner()
        runner.start()                   # launches background thread once
        ...
        # inside frame loop, every N frames:
        runner.submit_snapshot(
            lane_stats, signal_status,
            behaviour_events, predicted_pressures, frame_count
        )
        ...
        rec = runner.get_last_recommendation()   # latest advisory (never None)
    """

    def __init__(self) -> None:
        self._service: FeatherlessTrafficService = FeatherlessTrafficService()
        # Queue capacity = 1: always hold only the LATEST snapshot.
        # If the worker is busy, put_nowait() will discard the old one silently.
        self._queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
        self._last_rec: FeatherlessResponse = FeatherlessResponse.fallback()
        self._lock  = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._ready = False

        # Metrics for logging
        self._total_calls   = 0
        self._total_fallbacks = 0
        self._last_latency_ms = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """
        Initialise the Featherless service and launch the background worker.
        Returns True if the service is ready, False otherwise.
        If FEATHERLESS_ENABLED is False, does nothing and returns False.
        """
        if not FEATHERLESS_ENABLED:
            _log.info("[FeatherlessRunner] Disabled via FEATHERLESS_ENABLED=false.")
            return False

        self._ready = self._service.initialize()
        if not self._ready:
            _log.warning(
                "[FeatherlessRunner] Service failed to initialise. "
                "AI advisory layer is inactive — Gamana continues normally."
            )
            return False

        self._thread = threading.Thread(
            target=self._worker_loop,
            name="featherless-runner",
            daemon=True,
        )
        self._thread.start()
        _log.info("[FeatherlessRunner] Background worker started.")
        return True

    def submit_snapshot(
        self,
        lane_stats: Dict[str, Any],
        signal_status: Any,
        behaviour_events: Optional[list] = None,
        predicted_pressures: Optional[Dict[str, float]] = None,
        frame_count: int = 0,
    ) -> None:
        """
        Build the Featherless input snapshot from the current frame state and
        enqueue it for the background worker.

        This call is NON-BLOCKING — it never waits for the AI response.
        If the queue is full (worker busy), the old snapshot is discarded and
        replaced with the fresher one.

        Called from the main processing loop every AI_EVERY_N_FRAMES frames.
        """
        if not self._ready:
            return

        try:
            snapshot = build_intersection_state(
                lane_stats          = lane_stats,
                signal_status       = signal_status,
                behaviour_events    = behaviour_events,
                predicted_pressures = predicted_pressures,
                frame_count         = frame_count,
            )
            # Tag with the exact timestamp it was queued to measure staleness
            snapshot["queued_at"] = time.time()
            
            # Drain stale snapshot before putting the fresh one
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            self._queue.put_nowait(snapshot)
        except Exception as exc:
            _log.warning(f"[FeatherlessRunner] submit_snapshot error (ignored): {exc}")

    def get_last_recommendation(self) -> FeatherlessResponse:
        """Return the most recent AI recommendation. Always returns a valid object."""
        with self._lock:
            return self._last_rec

    def stats(self) -> Dict[str, Any]:
        """Return runtime statistics for logging / monitoring."""
        return {
            "total_calls":     self._total_calls,
            "total_fallbacks": self._total_fallbacks,
            "last_latency_ms": self._last_latency_ms,
            "ready":           self._ready,
        }

    # ── Background worker ─────────────────────────────────────────────────────

    def _worker_loop(self) -> None:
        """
        Daemon thread: block-waits for snapshots, calls the AI, stores result.
        Any exception is caught, logged, and the thread continues.
        """
        _log.info("[FeatherlessRunner] Worker loop started.")
        self._processing = False
        while True:
            try:
                snapshot = self._queue.get(timeout=5.0)   # block up to 5 s
            except queue.Empty:
                continue   # no new frame — idle wait
            except Exception as exc:
                _log.error(f"[FeatherlessRunner] Queue error: {exc}")
                continue

            self._processing = True
            try:
                self._process_snapshot(snapshot)
            finally:
                self._processing = False

    def _process_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Call generate_strategy(), store result, log everything."""
        fc = snapshot.get("frame_count", 0)
        queued_at = snapshot.get("queued_at", time.time())
        try:
            t0 = time.time()
            result = self._service.generate_strategy(snapshot)
            t1 = time.time()
            
            elapsed_ms = int((t1 - t0) * 1000)
            snapshot_age_s = t1 - queued_at

            # Inject requested runtime metadata
            result.snapshot_timestamp = queued_at
            result.request_timestamp = t0
            result.response_timestamp = t1
            result.last_updated = t1
            result.inference_time_ms = elapsed_ms
            result.response_latency_ms = elapsed_ms
            
            self._total_calls += 1
            self._last_latency_ms = elapsed_ms

            if result.status == "fallback":
                self._total_fallbacks += 1
                result.backend_status = "error"
                result.api_status = "error"
                _log.warning(
                    f"[FeatherlessRunner] frame={fc} — Fallback response "
                    f"(latency={elapsed_ms}ms, age={snapshot_age_s:.1f}s, "
                    f"fallbacks={self._total_fallbacks}/{self._total_calls})"
                )
            else:
                result.backend_status = "ok"
                result.api_status = "ok"
                _log.info(
                    f"[FeatherlessRunner] frame={fc} "
                    f"lane={result.recommended_lane} "
                    f"green={result.green_duration}s "
                    f"conf={result.confidence:.2f} "
                    f"latency={elapsed_ms}ms age={snapshot_age_s:.1f}s"
                )
                if snapshot_age_s > 10.0:
                    _log.warning(
                        f"[FeatherlessRunner] STALE SNAPSHOT WARNING: Recommendation for frame {fc} "
                        f"was based on data {snapshot_age_s:.1f} seconds old. "
                        f"Queued at: {queued_at:.2f}, Request Started: {t0:.2f}, Received: {t1:.2f}."
                    )
                _log.debug(f"[FeatherlessRunner] reasoning={result.reasoning}")

            with self._lock:
                self._last_rec = result

        except Exception as exc:
            _log.exception(
                f"[FeatherlessRunner] Unexpected error processing frame={fc}: {exc}"
            )
