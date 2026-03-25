"""
tracker.py
───────────
Motion-history / movement-classification layer on top of YOLO's BOT-SORT.

BOT-SORT already runs inside VehicleDetector.detect().
This module maintains a per-track position history and classifies each
tracked vehicle as MOVING or STOPPED based on cumulative displacement.
"""

from __future__ import annotations

from collections import deque, defaultdict
from typing import Dict, List, Tuple

from config import MOTION_HISTORY_LEN, STOPPED_THRESHOLD, MOTION_FRAMES_MIN
from modules.vehicle_detector import Detection


# ─────────────────────────────────────────────────────────────────────────────
class MotionTracker:
    """
    Tracks per-vehicle motion history.
    Updates Detection.is_moving in place.
    """

    def __init__(self) -> None:
        # track_id → deque of (cx, cy) positions
        self._history: Dict[int, deque] = defaultdict(
            lambda: deque(maxlen=MOTION_HISTORY_LEN)
        )
        # track_id → deque of speeds (pixels/frame)
        self._speed_history: Dict[int, deque] = defaultdict(
            lambda: deque(maxlen=MOTION_HISTORY_LEN)
        )
        # track_id → frame count since last seen (for stale cleanup)
        self._last_seen: Dict[int, int] = {}
        self._frame_idx: int = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self, detections: List[Detection], vehicle_state: dict, frame_idx: int) -> List[Detection]:
        """
        Update motion history for all current detections.
        Sets Detection.is_moving, Detection.speed, Detection.speed_history and returns the list.
        Also updates the global vehicle_state dictionary.
        """
        self._frame_idx = frame_idx
        active_ids = set()

        for det in detections:
            tid = det.track_id
            active_ids.add(tid)
            self._last_seen[tid] = self._frame_idx
            
            # Compute speed from previous frame
            hist = self._history[tid]
            if len(hist) > 0:
                last_pt = hist[-1]
                dx = det.cx - last_pt[0]
                dy = det.cy - last_pt[1]
                speed = (dx * dx + dy * dy) ** 0.5
                if abs(dx) < 1 and abs(dy) < 1:
                    speed *= 0.5
            else:
                speed = 0.0
                
            self._history[tid].append((det.cx, det.cy))
            self._speed_history[tid].append(speed)

            det.speed = speed
            det.speed_history = list(self._speed_history[tid])
            det.is_moving = self._is_moving(tid)

            # ── Update global vehicle state ──
            if tid not in vehicle_state:
                vehicle_state[tid] = {
                    "lane": None,
                    "speed": speed,
                    "is_moving": det.is_moving,
                    "wait_time": 0.0,
                    "last_seen": frame_idx
                }
            else:
                vehicle_state[tid]["speed"] = speed
                vehicle_state[tid]["is_moving"] = det.is_moving
                vehicle_state[tid]["last_seen"] = frame_idx

        # ── Garbage-collect stale tracks ──────────────────────────────────
        stale_ids = [
            tid for tid, last in self._last_seen.items()
            if self._frame_idx - last > MOTION_HISTORY_LEN * 3
        ]
        for tid in stale_ids:
            self._history.pop(tid, None)
            self._speed_history.pop(tid, None)
            self._last_seen.pop(tid, None)

        return detections

    def get_history(self, track_id: int) -> List[Tuple[int, int]]:
        """Return list of (cx, cy) positions for a given track."""
        return list(self._history.get(track_id, []))

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _is_moving(self, track_id: int) -> bool:
        """
        MOVING if total displacement over history window exceeds threshold.
        Requires at least MOTION_FRAMES_MIN frames of history.
        """
        hist = self._history[track_id]
        if len(hist) < MOTION_FRAMES_MIN:
            # Not enough history yet — assume moving (safer default)
            return True

        # Compute total path length (sum of step distances)
        total_disp = 0.0
        pts = list(hist)
        for a, b in zip(pts, pts[1:]):
            dx = b[0] - a[0]
            dy = b[1] - a[1]
            total_disp += (dx * dx + dy * dy) ** 0.5

        return total_disp > STOPPED_THRESHOLD * 1.5
