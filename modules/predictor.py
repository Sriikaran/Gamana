"""
predictor.py
─────────────
Short-term traffic congestion predictor.

Maintains a 120-frame rolling history of pressure scores per lane.
Every 10 frames fits linear regression on the last 30 values.

predicted_60s = current_pressure + slope * 60 * fps

If predicted_60s > 75 AND slope > 0.5 → JAM WARNING.
time_to_jam = (75 - current_pressure) / slope  (seconds)
"""

from __future__ import annotations

from collections import deque
from typing import Dict

import numpy as np

import config
from config import SPIKE_THRESHOLD
from modules.traffic_analyzer import LaneStats


# ─────────────────────────────────────────────────────────────────────────────
class CongestionPredictor:
    """
    Maintains per-lane 120-frame rolling pressure history and predicts
    future congestion using linear regression every 10 frames.
    """

    HISTORY_LEN            = 120     # rolling history length (frames)
    REGRESSION_WINDOW      = 30      # frames used in each regression fit
    REGRESSION_EVERY_N     = 10      # re-compute regression every N frames
    JAM_PRESSURE_THRESHOLD = 75.0    # predicted_60s > this → consider jam
    JAM_SLOPE_MIN          = 0.5     # slope must also exceed this (pressure/frame)
    FPS                    = float(getattr(config, 'TARGET_FPS', 25))

    def __init__(self) -> None:
        self._history: Dict[str, deque] = {}
        # Cached regression results, refreshed every REGRESSION_EVERY_N frames
        self._predictions: Dict[str, dict] = {}
        self._frame_counter: int = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self, lane_stats: Dict[str, LaneStats]) -> Dict[str, float]:
        """
        Feed the current frame's pressure scores into history.
        Returns dict of predicted_60s pressure per lane (0–100 range).
        """
        self._frame_counter += 1
        run_regression = (self._frame_counter % self.REGRESSION_EVERY_N == 0)

        predicted: Dict[str, float] = {}

        for ln in lane_stats:
            if ln not in self._history:
                self._history[ln] = deque(maxlen=self.HISTORY_LEN)

            cur_pressure = lane_stats[ln].pressure
            self._history[ln].append(float(cur_pressure))

            if run_regression or ln not in self._predictions:
                pred_p, slope, ttj, jam_warn = self._predict_full(ln, cur_pressure)
                self._predictions[ln] = {
                    "predicted_pressure": round(pred_p, 2),
                    "slope":              round(slope, 4),
                    "time_to_jam_seconds": round(ttj, 1),
                    "jam_warning":        jam_warn,
                }

            predicted[ln] = self._predictions[ln]["predicted_pressure"]

        return predicted

    def get_history(self, lane: str) -> list:
        """Return raw pressure history list for a lane (used by dashboard)."""
        return list(self._history.get(lane, []))

    def get_prediction_data(self, lane: str) -> dict:
        """Return full prediction data for a lane (for API and HUD)."""
        return self._predictions.get(lane, {
            "predicted_pressure":  0.0,
            "slope":               0.0,
            "time_to_jam_seconds": 999.0,
            "jam_warning":         False,
        })

    def is_spike_predicted(self, lane: str, predicted_pressure: float) -> bool:
        """True if the predicted pressure jumps by > SPIKE_THRESHOLD from current."""
        hist = self._history.get(lane, deque())
        if not hist:
            return False
        current = hist[-1]
        return (predicted_pressure - current) > SPIKE_THRESHOLD

    def trend_direction(self, lane: str) -> str:
        """Returns 'rising', 'falling', or 'stable' for HUD arrows."""
        pred = self._predictions.get(lane, {})
        slope = pred.get("slope", 0.0)
        if slope > 0.5:
            return "rising"
        if slope < -0.5:
            return "falling"
        return "stable"

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _predict_full(self, lane: str, current: float):
        """
        Fit linear regression on last REGRESSION_WINDOW pressure values.

        predicted_60s = current + slope * 60 * fps
        jam_warning   = predicted_60s > 75 AND slope > 0.5
        time_to_jam   = (75 - current) / slope  [seconds]

        Returns: (predicted_60s, slope, time_to_jam_seconds, jam_warning)
        """
        hist = list(self._history[lane])
        if len(hist) < 5:
            return current, 0.0, 999.0, False

        # Fit over last 30 values
        window = hist[-self.REGRESSION_WINDOW:]
        slope = self._slope(window)

        # 60-second lookahead: slope is in pressure-per-frame units
        predicted_60s = current + slope * 60.0 * self.FPS
        predicted_60s = float(np.clip(predicted_60s, 0.0, 100.0))

        # Jam warning: predicted pressure > 75 AND slope actively rising
        jam_warning = (
            predicted_60s > self.JAM_PRESSURE_THRESHOLD
            and slope > self.JAM_SLOPE_MIN
        )

        # Time to jam: seconds until pressure hits the threshold (75)
        time_to_jam_s = 999.0
        if jam_warning and slope > 0:
            # frames until threshold, then convert to seconds
            frames_to_threshold = (self.JAM_PRESSURE_THRESHOLD - current) / slope
            time_to_jam_s = max(0.0, frames_to_threshold / self.FPS)

        return predicted_60s, slope, time_to_jam_s, jam_warning

    @staticmethod
    def _slope(values: list) -> float:
        """Ordinary-least-squares slope over the given sequence."""
        n = len(values)
        if n < 2:
            return 0.0
        x = np.arange(n, dtype=float)
        y = np.array(values, dtype=float)
        sx  = x.sum()
        sy  = y.sum()
        sxy = (x * y).sum()
        sx2 = (x * x).sum()
        denom = n * sx2 - sx * sx
        if abs(denom) < 1e-9:
            return 0.0
        return float((n * sxy - sx * sy) / denom)
