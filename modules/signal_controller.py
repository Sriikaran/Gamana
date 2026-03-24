"""
signal_controller.py
─────────────────────
Finite-state machine for traffic signal control.

States
──────
  NORMAL             — give green to highest-pressure lane, min 12 s, max 60 s
  AMBULANCE_OVERRIDE — immediate override; hold until ambulance clears
  COOLDOWN           — brief pause after switching; prevents rapid toggling
  FAILSAFE           — fixed round-robin rotation (triggered on detection failure)

Switch rule
───────────
  Switch only if new winner leads current lane by 15+ points,
  sustained for 5+ consecutive seconds.

Behaviour modifiers
───────────────────
  PHANTOM_BRAKE  detected on active lane → extend current green +8 s (capped at MAX)
  STARTUP_DELAY  detected on active lane → end current green immediately
  QUEUE_BUILDUP  detected on any lane    → immediately re-evaluate best lane
  LANE_IMBALANCE detected               → boost underserved lane pressure +20 pts (decaying)

Ambulance
─────────
  Immediate override to ambulance lane.
  Flash red border in renderer. Hold override until ambulance clears.

Single-vehicle rule
───────────────────
  A single-vehicle anomaly (LANE_CUTTING, WRONG_SIDE, SPEED_VARIATION, BUS_STOP_BLOCKING)
  NEVER triggers a signal change on its own.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Optional

import numpy as np

import config
from config import (
    MIN_GREEN_TIME, MAX_GREEN_TIME, COOLDOWN_TIME,
    GREEN_LOW_TIME, GREEN_MED_TIME, GREEN_HIGH_TIME,
    SWITCH_THRESHOLD,
    FAILSAFE_GREEN_TIME,
)
from modules.traffic_analyzer import LaneStats


# ─────────────────────────────────────────────────────────────────────────────
class SignalState(Enum):
    NORMAL             = auto()
    AMBULANCE_OVERRIDE = auto()
    COOLDOWN           = auto()
    FAILSAFE           = auto()


@dataclass
class SignalStatus:
    signals:          Dict[str, str]   # lane → "GREEN" | "RED"
    active_lane:      str
    state:            str              # human-readable state name
    time_remaining:   float            # seconds until next possible switch
    green_duration:   int              # planned green length for active lane
    congestion_level: str              # LOW / MEDIUM / HIGH of active lane
    switch_reason:    str = ""         # reason for last switch (for banner)
    prev_lane:        str = ""         # lane before last switch (for banner)


# ─────────────────────────────────────────────────────────────────────────────
# Behaviour types that concern single vehicles only — never trigger a switch
_SINGLE_VEHICLE_ANOMALIES = {
    "lane_cutting", "wrong_side", "speed_variation", "bus_blocking",
}

# Minimum number of vehicles involved for a behaviour to trigger a switch
# (group behaviours like phantom_brake, queue_buildup, startup_delay already
#  enforce group evidence in behaviour_detector.py; this is a defence-in-depth)
_GROUP_BEHAVIOURS = {
    "phantom_brake", "startup_delay", "queue_buildup", "lane_imbalance",
}


# ─────────────────────────────────────────────────────────────────────────────
class SignalController:
    """Traffic signal state machine."""

    # Sustained-lead window before allowing a switch (seconds)
    SWITCH_SUSTAIN_S   = 5.0
    # Pressure boost applied to underserved lane on LANE_IMBALANCE
    IMBALANCE_BOOST    = 20.0
    # Per-frame decay of pressure boosts (so stale events expire naturally)
    BOOST_DECAY_RATE   = 0.3
    # Extension added per PHANTOM_BRAKE event on active lane
    PHANTOM_BRAKE_EXT_S = 8

    def __init__(self) -> None:
        self._state:           SignalState = SignalState.NORMAL
        self._active:          str         = config.LANE_NAMES[0]
        self._green_start:     float       = time.time()
        self._green_duration:  int         = GREEN_LOW_TIME
        self._cooldown_end:    float       = 0.0
        self._failsafe_idx:    int         = 0
        self._detection_fail_count: int    = 0

        # Failsafe after N consecutive empty-detection frames
        self._FAIL_THRESHOLD = 30

        # Switch banner
        self._switch_banner_text:    str   = ""
        self._switch_banner_expires: float = 0.0
        self._prev_active:           str   = ""

        # Decaying per-lane pressure boosts from behaviour events
        self._pressure_boosts: Dict[str, float] = {}

        # ── Sustained-lead tracking ─────────────────────────────────────────
        # candidate_lane: the lane that currently leads by 15+ pts
        # candidate_since: wall-clock time when it first took the lead
        self._candidate_lane:  Optional[str]   = None
        self._candidate_since: float           = 0.0

        # ── Phantom-brake extension tracker ────────────────────────────────
        # Track how much extension has been added this green phase so we
        # don't keep extending on every frame the event fires.
        self._phantom_ext_applied: float = 0.0   # total seconds already added

    # ── Public API ────────────────────────────────────────────────────────────

    def update(
        self,
        lane_stats: Dict[str, LaneStats],
        detection_ok: bool,
        predicted_pressures: Optional[Dict[str, float]] = None,
        behaviour_events: Optional[list] = None,
        frame: Optional[np.ndarray] = None,
    ) -> SignalStatus:
        """
        Called every frame. Returns the current SignalStatus.
        `detection_ok`        — False if current frame had NO detections
        `predicted_pressures` — optional dict of predicted pressure per lane
        `behaviour_events`    — new BehaviourEvent objects from this frame
        `frame`               — current video frame (for HSV ambulance check)
        """
        now = time.time()

        # ── Failsafe check ─────────────────────────────────────────────────
        if not detection_ok:
            self._detection_fail_count += 1
        else:
            self._detection_fail_count = 0

        if self._detection_fail_count >= self._FAIL_THRESHOLD:
            if self._state != SignalState.FAILSAFE:
                self._green_start    = now
                self._green_duration = FAILSAFE_GREEN_TIME
                self._phantom_ext_applied = 0.0
            self._state = SignalState.FAILSAFE
        elif self._state == SignalState.FAILSAFE and detection_ok:
            self._state = SignalState.NORMAL
            self._detection_fail_count = 0

        # ── Decay pressure boosts ──────────────────────────────────────────
        for ln in list(self._pressure_boosts):
            self._pressure_boosts[ln] = max(
                0.0, self._pressure_boosts[ln] - self.BOOST_DECAY_RATE
            )

        # ── State machine ──────────────────────────────────────────────────
        if self._state == SignalState.FAILSAFE:
            self._run_failsafe(now)

        elif self._state == SignalState.AMBULANCE_OVERRIDE:
            self._run_ambulance(lane_stats, now, frame)

        elif self._state == SignalState.COOLDOWN:
            if now >= self._cooldown_end:
                self._state = SignalState.NORMAL
            # stay on current green during cooldown; still apply events

        else:  # NORMAL
            # Ambulance check first (YOLO label → emergency flag)
            amb_lane = self._find_ambulance(lane_stats, frame)
            if amb_lane:
                prev = self._active
                self._switch_to(amb_lane, now, emergency=True)
                self._state = SignalState.AMBULANCE_OVERRIDE
                self._set_switch_banner(prev, amb_lane, "Ambulance override", now)
            else:
                self._run_normal(
                    lane_stats, predicted_pressures, now,
                    behaviour_events or []
                )

        # ── Build status ───────────────────────────────────────────────────
        signals = {
            ln: ("GREEN" if ln == self._active else "RED")
            for ln in config.LANE_NAMES
        }

        elapsed   = now - self._green_start
        remaining = max(0.0, self._green_duration - elapsed)

        active_stats = lane_stats.get(self._active)
        cong_level   = active_stats.congestion_level if active_stats else "LOW"

        switch_reason = ""
        if now < self._switch_banner_expires:
            switch_reason = self._switch_banner_text

        return SignalStatus(
            signals          = signals,
            active_lane      = self._active,
            state            = self._state.name,
            time_remaining   = remaining,
            green_duration   = self._green_duration,
            congestion_level = cong_level,
            switch_reason    = switch_reason,
            prev_lane        = self._prev_active,
        )

    # ── State handlers ────────────────────────────────────────────────────────

    def _run_normal(
        self,
        lane_stats: Dict[str, LaneStats],
        predicted: Optional[Dict[str, float]],
        now: float,
        behaviour_events: list,
    ) -> None:
        elapsed = now - self._green_start

        # ── Apply GROUP behaviour events ────────────────────────────────────
        force_reevaluate = self._apply_behaviour_events(
            behaviour_events, lane_stats, now, elapsed
        )

        # ── Enforce minimum green time ──────────────────────────────────────
        if elapsed < MIN_GREEN_TIME and not force_reevaluate:
            return

        # ── Check if the timer has expired (or forced by STARTUP_DELAY) ────
        timer_expired = elapsed >= self._green_duration

        if not timer_expired and not force_reevaluate:
            return

        # ── Find best lane with boosted pressures ───────────────────────────
        best, best_score, cur_score = self._best_lane_with_scores(
            lane_stats, predicted
        )

        lead = best_score - cur_score

        # ── Sustained-lead hysteresis: must lead by 15+ pts for 5+ seconds ─
        if best != self._active and lead >= SWITCH_THRESHOLD:
            if self._candidate_lane != best:
                # New candidate — start the clock
                self._candidate_lane  = best
                self._candidate_since = now
            sustained = now - self._candidate_since
            if sustained >= self.SWITCH_SUSTAIN_S or force_reevaluate:
                # Cleared hysteresis (or forced by QUEUE_BUILDUP)
                prev   = self._active
                reason = f"{best} pressure {best_score:.0f} vs {cur_score:.0f}"
                self._switch_to(best, now)
                self._set_switch_banner(prev, best, reason, now)
                self._candidate_lane = None
        else:
            # Lead lost or same lane — reset candidate
            if timer_expired and best == self._active:
                # Refresh the green timer for the same lane
                self._green_start = now
                self._phantom_ext_applied = 0.0
            self._candidate_lane = None

    def _run_ambulance(
        self, lane_stats: Dict[str, LaneStats], now: float,
        frame: Optional[np.ndarray] = None
    ) -> None:
        """Stay in ambulance override until the ambulance lane clears."""
        amb_lane = self._find_ambulance(lane_stats, frame)
        if amb_lane:
            if amb_lane != self._active:
                self._switch_to(amb_lane, now, emergency=True)
        else:
            # Ambulance cleared — return to NORMAL with a fresh cycle
            self._state = SignalState.NORMAL
            self._green_start = now
            self._phantom_ext_applied = 0.0
            self._candidate_lane = None

    def _run_failsafe(self, now: float) -> None:
        """Round-robin rotation with fixed timing (FAILSAFE_GREEN_TIME per lane)."""
        elapsed = now - self._green_start
        if elapsed >= FAILSAFE_GREEN_TIME:
            names = config.LANE_NAMES
            self._failsafe_idx = (self._failsafe_idx + 1) % len(names)
            self._active       = names[self._failsafe_idx]
            self._green_start  = now
            self._green_duration = FAILSAFE_GREEN_TIME
            self._phantom_ext_applied = 0.0

    # ── Behaviour event processing ────────────────────────────────────────────

    def _apply_behaviour_events(
        self,
        events: list,
        lane_stats: Dict[str, LaneStats],
        now: float,
        elapsed: float,
    ) -> bool:
        """
        Process GROUP behaviour events and modify timing state.

        Returns True if a forced re-evaluation is needed (QUEUE_BUILDUP or
        STARTUP_DELAY caused the timer to expire early).

        Single-vehicle anomalies (_SINGLE_VEHICLE_ANOMALIES) are silently
        ignored — they never trigger a signal change.
        """
        force = False

        for ev in events:
            et = self._event_type(ev)
            ln = self._event_lane(ev)

            # ── Guard: single-vehicle anomaly → skip entirely ───────────────
            if et in _SINGLE_VEHICLE_ANOMALIES:
                continue

            # ── Only act on recognised group behaviours ─────────────────────
            if et not in _GROUP_BEHAVIOURS:
                continue

            if et == "phantom_brake" and ln == self._active:
                # Extend green +8 s, but only once per event (not per frame).
                # We track total extension applied this phase.
                headroom = MAX_GREEN_TIME - self._green_duration
                add = min(self.PHANTOM_BRAKE_EXT_S, headroom)
                if add > 0:
                    self._green_duration += add
                    self._phantom_ext_applied += add
                    print(
                        f"[Signal] PHANTOM_BRAKE on {ln} → "
                        f"extend green +{add}s (total {self._green_duration}s)"
                    )

            elif et == "startup_delay" and ln == self._active:
                # End the current green phase immediately
                self._green_duration = int(elapsed)   # expire the timer
                force = True
                print(f"[Signal] STARTUP_DELAY on {ln} → forcing early switch")

            elif et == "queue_buildup":
                # Flag for immediate re-evaluation IF minimum time has been served
                if elapsed >= MIN_GREEN_TIME:
                    force = True
                    print(f"[Signal] QUEUE_BUILDUP on {ln} → forcing re-evaluation")

            elif et == "lane_imbalance":
                # Boost underserved lane +20 pts (decaying)
                if ln:
                    self._pressure_boosts[ln] = (
                        self._pressure_boosts.get(ln, 0.0) + self.IMBALANCE_BOOST
                    )
                    print(f"[Signal] LANE_IMBALANCE → boost {ln} +{self.IMBALANCE_BOOST} pts")

        return force

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _switch_to(self, lane: str, now: float, emergency: bool = False) -> None:
        """Perform a lane switch, resetting all per-phase state."""
        self._prev_active = self._active
        self._active      = lane
        self._green_start = now
        self._phantom_ext_applied = 0.0
        self._candidate_lane = None

        # Compute fresh green duration for the new lane
        # (will be recalculated properly in next normal iteration;
        #  use a safe medium default for now)
        self._green_duration = GREEN_MED_TIME

        self._cooldown_end = now + COOLDOWN_TIME
        if not emergency:
            self._state = SignalState.COOLDOWN

    def _set_switch_banner(
        self, prev: str, new: str, reason: str, now: float
    ) -> None:
        self._switch_banner_text    = f"SIGNAL: {prev}→{new}  Reason: {reason}"
        self._switch_banner_expires = now + 3.0

    def _best_lane_with_scores(
        self,
        lane_stats: Dict[str, LaneStats],
        predicted: Optional[Dict[str, float]],
    ) -> tuple:
        """
        Returns (best_lane, best_score, current_lane_score).
        Score = actual_pressure + 0.4 * predicted_pressure + boost.
        """
        scores: Dict[str, float] = {}
        for ln in config.LANE_NAMES:
            actual = (lane_stats[ln].pressure if ln in lane_stats else 0.0)
            pred   = (predicted or {}).get(ln, 0.0)
            boost  = self._pressure_boosts.get(ln, 0.0)
            scores[ln] = actual + pred * 0.4 + boost

        best      = max(scores, key=scores.__getitem__)
        best_sc   = scores[best]
        cur_sc    = scores.get(self._active, 0.0)

        # Set green duration based on the ACTIVE lane's congestion level
        active_stats = lane_stats.get(self._active)
        if active_stats:
            self._green_duration = self._calc_duration(active_stats.congestion_level)

        return best, best_sc, cur_sc

    def _find_ambulance(
        self, lane_stats: Dict[str, LaneStats],
        frame: Optional[np.ndarray] = None,
    ) -> Optional[str]:
        """
        Detect ambulance: primary = YOLO emergency flag on LaneStats.
        (HSV backup is handled inside vehicle_detector.py via is_ambulance flag.)
        """
        for ln, stats in lane_stats.items():
            if getattr(stats, 'emergency', False):
                return ln
        return None

    @staticmethod
    def _calc_duration(level: str) -> int:
        """Map congestion level → green duration within [MIN, MAX]."""
        base = {
            "LOW":    GREEN_LOW_TIME,
            "MEDIUM": GREEN_MED_TIME,
            "HIGH":   GREEN_HIGH_TIME,
        }.get(level, GREEN_MED_TIME)
        return max(MIN_GREEN_TIME, min(MAX_GREEN_TIME, base))

    @staticmethod
    def _event_type(ev) -> str:
        if hasattr(ev, "behaviour"):
            return getattr(ev.behaviour, "value", str(ev.behaviour))
        if isinstance(ev, dict):
            return str(ev.get("type", ""))
        return ""

    @staticmethod
    def _event_lane(ev) -> str:
        if hasattr(ev, "lane"):
            return str(ev.lane)
        if isinstance(ev, dict):
            return str(ev.get("lane", ""))
        return ""
