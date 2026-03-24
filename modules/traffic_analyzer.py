"""
traffic_analyzer.py
────────────────────
Computes per-lane traffic statistics and congestion pressure scores.

Indian-road weighted scoring:
  - Each vehicle type has a weight
  - Stopped vehicles apply a penalty multiplier
  - Waiting time (seconds since last green) adds bonus pressure
  - Flow rate (vehicles cleared per second) subtracts from pressure
  - Score is normalised to 0–100
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List
from collections import deque

import config
from config import (
    VEHICLE_WEIGHTS,
    STOPPED_PENALTY,
    MOVING_MULTIPLIER,
    WAITING_TIME_WEIGHT,
    CONGESTION_LOW_MAX,
    CONGESTION_HIGH_MIN,
)
from modules.vehicle_detector import Detection


# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class LaneStats:
    name:          str
    total:         int   = 0
    moving:        int   = 0
    stopped:       int   = 0
    emergency:     bool  = False
    raw_pressure:  float = 0.0
    pressure:      float = 0.0   # normalised 0–100
    congestion_level: str = "LOW"   # LOW / MEDIUM / HIGH
    vehicle_counts: Dict[str, int] = field(default_factory=dict)
    # flow rate tracked externally
    waiting_since:  float = field(default_factory=time.time)  # timestamp
    transient_spike: bool = False
    last_event: str = ""

    def reset(self) -> None:
        self.total         = 0
        self.moving        = 0
        self.stopped       = 0
        self.emergency     = False
        self.raw_pressure  = 0.0
        self.pressure      = 0.0
        self.congestion_level = "LOW"
        self.vehicle_counts   = {}
        self.transient_spike  = False
        self.last_event       = ""


# ─────────────────────────────────────────────────────────────────────────────
class TrafficAnalyzer:
    """
    Analyzes per-lane vehicle lists and computes congestion metrics.
    """

    def __init__(self) -> None:
        self._lane_stats: Dict[str, LaneStats] = {
            ln: LaneStats(name=ln) for ln in config.LANE_NAMES
        }
        # flow tracking: count vehicles seen last window per lane
        self._prev_counts: Dict[str, int] = {ln: 0 for ln in config.LANE_NAMES}
        self._flow_rates:  Dict[str, float] = {ln: 0.0 for ln in config.LANE_NAMES}
        self._last_flow_time: float = time.time()

        # max raw pressure seen so far (for normalisation)
        self._max_pressure_seen: float = 1.0

        # Pressure smoothing / sustain logic
        self._stable_raw: Dict[str, float] = {ln: 0.0 for ln in config.LANE_NAMES}
        self._candidate_raw: Dict[str, float] = {ln: 0.0 for ln in config.LANE_NAMES}
        self._candidate_since: Dict[str, float] = {ln: 0.0 for ln in config.LANE_NAMES}
        self._SUSTAIN_SECONDS = 5.0
        self._RAW_EPS = 0.75

    # ── Public API ────────────────────────────────────────────────────────────

    def update(
        self,
        per_lane: Dict[str, List[Detection]],
        current_green: str,
    ) -> Dict[str, LaneStats]:
        """
        Compute LaneStats for every lane.
        `current_green` is used to update waiting_since for non-green lanes.
        """
        now = time.time()
        self._update_flow_rates(per_lane, now)

        for ln in config.LANE_NAMES:
            stats = self._lane_stats[ln]
            stats.reset()

            dets = per_lane.get(ln, [])
            stats.total = len(dets)

            waiting_secs = now - stats.waiting_since

            individual_weight = 0.0
            group_weight = 0.0

            total = len(dets)
            all_stopped = (total >= 3 and all(not d.is_moving for d in dets))
            all_decelerating = (
                total >= 3 and all(bool(getattr(d, "is_decelerating", False)) for d in dets)
            )
            same_pattern_group = all_stopped or all_decelerating

            for det in dets:
                weight = VEHICLE_WEIGHTS.get(det.label, 1.0)
                multiplier = MOVING_MULTIPLIER if det.is_moving else STOPPED_PENALTY
                w = weight * multiplier

                # 3+ same-pattern vehicles contribute as group (100% influence).
                if same_pattern_group:
                    group_weight += w
                else:
                    # Single-vehicle anomaly contributes weakly.
                    individual_weight += w

                if det.is_moving:
                    stats.moving += 1
                else:
                    stats.stopped += 1

                stats.vehicle_counts[det.label] = (
                    stats.vehicle_counts.get(det.label, 0) + 1
                )

                if det.is_ambulance:
                    stats.emergency = True

            # Required formula:
            # pressure = (group_weight * 0.9 + individual_weight * 0.1) * time_factor
            time_factor = 1.0 + min(waiting_secs / 20.0, 1.5)
            candidate_raw = (group_weight * 0.9 + individual_weight * 0.1) * time_factor

            # Waiting time bonus (pressure increases the longer a lane waits)
            if ln != current_green:
                candidate_raw += waiting_secs * WAITING_TIME_WEIGHT
            else:
                # Reset waiting timer for the active green lane
                stats.waiting_since = now

            # Subtract flow bonus
            candidate_raw -= self._flow_rates[ln] * 0.5
            candidate_raw = max(0.0, candidate_raw)

            # Sustained-change gate: pressure change must persist 5+ seconds.
            prev_candidate = self._candidate_raw.get(ln, 0.0)
            if abs(candidate_raw - prev_candidate) > self._RAW_EPS:
                self._candidate_raw[ln] = candidate_raw
                self._candidate_since[ln] = now

                # Single-vehicle spike: log event but don't change stable pressure.
                if total <= 1:
                    stats.transient_spike = True
                    stats.last_event = "SINGLE_VEHICLE_SPIKE_IGNORED"
                    print(f"[Analyzer] {ln}: single-vehicle spike ignored ({candidate_raw:.1f})")
            else:
                if self._candidate_since[ln] == 0.0:
                    self._candidate_since[ln] = now

            # First sample initializes stable pressure immediately.
            if self._stable_raw[ln] == 0.0 and candidate_raw > 0.0:
                self._stable_raw[ln] = candidate_raw
            elif now - self._candidate_since[ln] >= self._SUSTAIN_SECONDS:
                self._stable_raw[ln] = self._candidate_raw[ln]

            stats.raw_pressure = self._stable_raw[ln]

        # ── Normalise all lanes together ──────────────────────────────────
        max_raw = max(
            (s.raw_pressure for s in self._lane_stats.values()), default=1.0
        )
        self._max_pressure_seen = max(self._max_pressure_seen, max_raw)

        for ln in config.LANE_NAMES:
            stats = self._lane_stats[ln]
            # Normalise to 0–100 based on rolling max seen
            stats.pressure = min(
                100.0,
                (stats.raw_pressure / self._max_pressure_seen) * 100.0,
            )
            stats.congestion_level = self._level(stats.pressure)

        return self._lane_stats

    def get_stats(self) -> Dict[str, LaneStats]:
        return self._lane_stats

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _update_flow_rates(
        self, per_lane: Dict[str, List[Detection]], now: float
    ) -> None:
        """Estimate vehicle flow rate (vehicles/second) per lane."""
        dt = max(0.1, now - self._last_flow_time)
        for ln in config.LANE_NAMES:
            cur = len(per_lane.get(ln, []))
            delta = max(0, self._prev_counts[ln] - cur)  # vehicles that left
            self._flow_rates[ln] = delta / dt
            self._prev_counts[ln] = cur
        self._last_flow_time = now

    @staticmethod
    def _level(pressure: float) -> str:
        if pressure <= CONGESTION_LOW_MAX:
            return "LOW"
        if pressure >= CONGESTION_HIGH_MIN:
            return "HIGH"
        return "MEDIUM"
