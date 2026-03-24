"""
risk_predictor.py — Congestion seed prediction for Pragati AI.
Combines behaviour event frequency with pressure slope to compute
a CongestionRisk score (0–100) per lane with time-to-jam estimate.
"""

import time
import numpy as np
from collections import deque, defaultdict
from dataclasses import dataclass, field
from modules.behaviour_detector import BehaviourType, RISK_HIGH, RISK_MEDIUM, BehaviourEvent


# Weight of each behaviour type toward congestion risk score
BEHAVIOUR_CONGESTION_WEIGHT = {
    BehaviourType.PHANTOM_BRAKE:      20,
    BehaviourType.LANE_CUTTING:       15,
    BehaviourType.WRONG_SIDE_DRIVING: 25,
    BehaviourType.STARTUP_DELAY:      10,
    BehaviourType.BUS_STOP_BLOCKING:  18,
    BehaviourType.PEDESTRIAN_SURGE:   12,
    BehaviourType.QUEUE_BUILDUP:      22,
    BehaviourType.SPEED_VARIATION:     8,
}

# Decay half-life: older events matter less
EVENT_DECAY_HALF_LIFE_S = 20.0


@dataclass
class CongestionRisk:
    lane: str
    score: float           # 0–100
    level: str             # LOW / MEDIUM / HIGH / CRITICAL
    time_to_jam_s: float   # estimated seconds until full congestion
    top_cause: str         # dominant behaviour driving the risk
    pressure_trend: str    # rising / stable / falling
    timestamp: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "lane": self.lane,
            "score": round(self.score, 1),
            "level": self.level,
            "time_to_jam_s": round(self.time_to_jam_s, 0),
            "top_cause": self.top_cause,
            "pressure_trend": self.pressure_trend,
        }


class RiskPredictor:
    def __init__(self, lane_names: list[str]):
        self.lane_names = lane_names
        self._pressure_history: dict[str, deque] = {
            ln: deque(maxlen=60) for ln in lane_names
        }
        self._event_buffer: dict[str, list] = defaultdict(list)

    def update_pressure(self, lane: str, pressure: float):
        self._pressure_history[lane].append((time.time(), pressure))

    def add_events(self, events: list[BehaviourEvent]):
        for ev in events:
            self._event_buffer[ev.lane].append(ev)

    def compute_risks(self) -> dict[str, CongestionRisk]:
        now = time.time()
        risks = {}
        for lane in self.lane_names:
            risks[lane] = self._compute_lane_risk(lane, now)
        # Trim old events
        cutoff = now - 60.0
        for lane in self.lane_names:
            self._event_buffer[lane] = [
                e for e in self._event_buffer[lane] if e.timestamp >= cutoff
            ]
        return risks

    def _compute_lane_risk(self, lane: str, now: float) -> CongestionRisk:
        # 1. Behaviour score with exponential decay
        events = self._event_buffer.get(lane, [])
        behaviour_score = 0.0
        cause_weights: dict[str, float] = defaultdict(float)
        for ev in events:
            age = now - ev.timestamp
            decay = 0.5 ** (age / EVENT_DECAY_HALF_LIFE_S)
            weight = BEHAVIOUR_CONGESTION_WEIGHT.get(ev.behaviour, 5) * decay
            behaviour_score += weight
            cause_weights[ev.behaviour.value] += weight

        behaviour_score = min(behaviour_score, 60.0)

        # 2. Pressure slope score
        p_hist = list(self._pressure_history.get(lane, []))
        pressure_score = 0.0
        trend = "stable"
        current_pressure = p_hist[-1][1] if p_hist else 0.0

        if len(p_hist) >= 6:
            pressures = [p for _, p in p_hist[-20:]]
            x = np.arange(len(pressures), dtype=float)
            slope, _ = np.polyfit(x, pressures, 1)
            if slope > 1.0:
                trend = "rising"
                pressure_score = min(slope * 5, 40.0)
            elif slope < -0.5:
                trend = "falling"
            # Current pressure contribution
            pressure_score += current_pressure * 0.2

        # 3. Combined risk score
        score = min(100.0, behaviour_score + pressure_score)

        # 4. Risk level
        if score >= 75:
            level = "CRITICAL"
        elif score >= 55:
            level = "HIGH"
        elif score >= 30:
            level = "MEDIUM"
        else:
            level = "LOW"

        # 5. Time to jam estimate
        # Based on how fast pressure is rising toward 100
        remaining_capacity = max(1.0, 100.0 - current_pressure)
        p_vals = [p for _, p in p_hist[-10:]] if len(p_hist) >= 10 else [current_pressure]
        if len(p_vals) >= 2:
            rate = max(0.01, (p_vals[-1] - p_vals[0]) / len(p_vals))
        else:
            rate = 0.5
        time_to_jam_s = remaining_capacity / rate if trend == "rising" else 999.0

        # 6. Top cause
        top_cause = max(cause_weights.items(), key=lambda x: x[1])[0] if cause_weights else "none"

        return CongestionRisk(
            lane=lane,
            score=score,
            level=level,
            time_to_jam_s=time_to_jam_s,
            top_cause=top_cause,
            pressure_trend=trend,
        )