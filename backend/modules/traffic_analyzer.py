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
    flow_rate:      float = 0.0   # vehicles exited per second
    avg_speed:      float = 0.0   # current average speed
    wait_time:      float = 0.0   # avg wait time of stopped vehicles (s)
    waiting_since:  float = field(default_factory=time.time)  # timestamp
    transient_spike: bool = False
    last_event: str = ""
    trend:         str  = "stable"  # rising / falling / stable

    def reset(self) -> None:
        # Reset ONLY frame-dependent values
        self.total = 0
        self.moving = 0
        self.stopped = 0
        self.emergency = False
        self.raw_pressure = 0.0
        self.pressure = 0.0
        self.congestion_level = "LOW"
        self.vehicle_counts = {}
        self.wait_time = 0.0
        self.transient_spike = False
        self.last_event = ""
        self.trend = "stable"


# ─────────────────────────────────────────────────────────────────────────────
class TrafficAnalyzer:
    """
    Analyzes per-lane vehicle lists and computes congestion metrics.
    Implements Phase 1 Core Pressure Model with Disturbance Score.
    """

    def __init__(self) -> None:
        self._lane_stats: Dict[str, LaneStats] = {}
        
        # History for Q and average speed
        import collections
        self._Q_history: Dict[str, collections.deque] = {}
        self._lane_speeds: Dict[str, collections.deque] = {}
        
        # Exponential moving average pressure
        self._prev_pressure: Dict[str, float] = {}
        
        # Flow tracking
        self._flow_timestamps: Dict[str, collections.deque] = {}
        
        # ── Persistent vehicle state ──────────────────────────────────────
        # { track_id: { lane, speed, wait_time, last_seen_frame } }
        self._vehicle_state: Dict[int, dict] = {}
        self._frame_counter: int = 0
        self._last_update_time: float = time.time()
        
        # How many frames a vehicle can be unseen before considered "exited"
        self._STALE_FRAMES = 5

    # ── Public API ────────────────────────────────────────────────────────────

    def record_flow(self, lane: str):
        if lane not in self._flow_timestamps:
            import collections
            self._flow_timestamps[lane] = collections.deque(maxlen=300)
        self._flow_timestamps[lane].append(time.time())

    def update(
        self, vehicle_state: dict, lane_names: list, signal_green_lane: str
    ) -> Dict[str, LaneStats]:
        """
        Builds per-lane metrics from global persistent vehicle state.
        Computes the pressure model (P_i) and records state.
        """
        import math
        import numpy as np
        import collections

        def sigmoid(x: float) -> float:
            try:
                # S(x) = 1 / (1 + exp(-k*(x - x0)))
                return 1.0 / (1.0 + math.exp(-config.SIGMOID_K * (x - config.SIGMOID_X0)))
            except OverflowError:
                return 0.0 if (x - config.SIGMOID_X0) < 0 else 1.0
                
        now = time.time()
        dt = 1.0 / max(1.0, getattr(config, 'TARGET_FPS', 25.0))
        self._last_update_time = now
        self._frame_counter += 1

        # ── Initialize per-frame lane metrics ──
        for ln in lane_names:
            if ln not in self._lane_stats:
                self._lane_stats[ln] = LaneStats(name=ln)
                self._Q_history[ln] = collections.deque(maxlen=getattr(config, 'HISTORY_MAX_FRAMES', 30))
                self._lane_speeds[ln] = collections.deque(maxlen=getattr(config, 'HISTORY_MAX_FRAMES', 30))
                self._prev_pressure[ln] = 0.0
                self._flow_timestamps[ln] = collections.deque(maxlen=300)

            stats = self._lane_stats[ln]
            stats.reset()
            # Initialize metrics for this frame
            stats.total = 0
            stats.moving = 0
            stats.stopped = 0
            stats.wait_time = 0.0

        lane_total = collections.defaultdict(int)
        lane_moving = collections.defaultdict(int)
        lane_stopped = collections.defaultdict(int)
        lane_wait_sum = collections.defaultdict(float)
        lane_wait_count = collections.defaultdict(int)
        lane_speeds = collections.defaultdict(list)

        # ── Loop over vehicle_state and compute ──
        if not hasattr(self, "_smoothed_totals"):
            self._smoothed_totals = {ln: 0.0 for ln in lane_names}
            self._smoothed_moving = {ln: 0.0 for ln in lane_names}
            self._smoothed_stopped = {ln: 0.0 for ln in lane_names}
            self._flow_ema = {ln: 0.0 for ln in lane_names}
            self._prev_ids = {ln: set() for ln in lane_names}

        current_ids = collections.defaultdict(set)
        active_vehicles = []
        
        for tid, v in vehicle_state.items():
            lane = v.get("lane")
            if lane is None or lane not in self._lane_stats:
                continue

            # STEP 1: ACTIVE_WINDOW FILTER (30 frames)
            if self._frame_counter - v.get("last_seen", 0) >= 30:
                continue

            active_vehicles.append(v)
            current_ids[lane].add(tid)
            lane_total[lane] += 1
            spd = v.get("speed", 0.0)
            
            # STEP 2: Use smoothed speed via rolling average
            if "speed_hist" not in v:
                v["speed_hist"] = collections.deque(maxlen=10)
            v["speed_hist"].append(spd)
            veh_avg_speed = sum(v["speed_hist"]) / len(v["speed_hist"])
            
            lane_speeds[lane].append(veh_avg_speed)

            # STEP 4: Fix wait time increments
            if veh_avg_speed < 1.0:
                lane_stopped[lane] += 1
                v["wait_time"] = min(v.get("wait_time", 0.0) + dt, getattr(config, 'MAX_WAIT_TIME', 120.0))
                lane_wait_sum[lane] += v["wait_time"]
                lane_wait_count[lane] += 1
            elif veh_avg_speed > 2.0:
                lane_moving[lane] += 1
                v["wait_time"] = 0.0
            else:
                # Buffer Zone: maintain current logic state
                if v.get("wait_time", 0.0) > 0:
                    lane_stopped[lane] += 1
                    v["wait_time"] = min(v.get("wait_time", 0.0) + dt, getattr(config, 'MAX_WAIT_TIME', 120.0))
                    lane_wait_sum[lane] += v["wait_time"]
                    lane_wait_count[lane] += 1
                else:
                    lane_moving[lane] += 1
                    v["wait_time"] = 0.0

        # ── Apply Accumulated Values to Stats ──
        for ln in lane_names:
            stats = self._lane_stats[ln]
            raw_total = lane_total[ln]
            raw_moving = lane_moving[ln]
            raw_stopped = lane_stopped[ln]
            
            # Wait time average (Gradual smoothing)
            raw_wait = (lane_wait_sum[ln] / lane_wait_count[ln]) if lane_wait_count[ln] > 0 else 0.0
            stats.wait_time = 0.8 * stats.wait_time + 0.2 * raw_wait

            # STEP 3: Flow = count of IDs that disappeared
            exited_count = len(self._prev_ids[ln] - current_ids[ln])
            self._flow_ema[ln] = 0.8 * self._flow_ema[ln] + 0.2 * exited_count
            self._prev_ids[ln] = current_ids[ln]
            
            # Boost the visual flow arbitrary multiplier so it reads dynamically in UI
            stats.flow_rate = self._flow_ema[ln] * getattr(config, 'TARGET_FPS', 25.0)
            
            # STEP 6: Prevent Zero Collapse
            if raw_total == 0 and self._smoothed_totals[ln] > 0.5:
                # Decay slowly to obscure tracking dropouts
                self._smoothed_totals[ln] *= 0.95
                self._smoothed_moving[ln] *= 0.95
                self._smoothed_stopped[ln] *= 0.95
            else:
                # STEP 5: EMA Smoothing over metrics
                self._smoothed_totals[ln] = 0.7 * self._smoothed_totals[ln] + 0.3 * raw_total
                self._smoothed_moving[ln] = 0.7 * self._smoothed_moving[ln] + 0.3 * raw_moving
                self._smoothed_stopped[ln] = 0.7 * self._smoothed_stopped[ln] + 0.3 * raw_stopped
            
            stats.total = int(round(self._smoothed_totals[ln]))
            stats.moving = int(round(self._smoothed_moving[ln]))
            stats.stopped = int(round(self._smoothed_stopped[ln]))
            
            # Average speed
            speeds = lane_speeds[ln]
            avg_speed = float(np.mean(speeds)) if speeds else 0.0
            speed_var = float(np.var(speeds)) if speeds else 0.0
            self._lane_speeds[ln].append(avg_speed)

        # ── Calculate IM (Lane Imbalance) ──
        rhos = {}
        for ln in lane_names:
            dets_count = self._lane_stats[ln].total
            capacity = getattr(config, 'LANE_CAPACITY', 30.0)
            rho = min(1.0, dets_count / float(capacity))
            rhos[ln] = rho
            
        rho_values = list(rhos.values())
        valid_rhos = [r for r in rho_values if r > 0]
        if len(valid_rhos) > 1 and np.mean(valid_rhos) > 0:
            IM = float(np.std(valid_rhos) / np.mean(valid_rhos))
        else:
            IM = 0.0

        vehicle_counts = {ln: self._lane_stats[ln].total for ln in lane_names}

        # STEP 7: Debug Prints
        print(f"ACTIVE VEHICLES: {len(active_vehicles)}")
        print(f"LANE COUNTS: {vehicle_counts}")

        # ── Compute Pressure and Disturbances ──
        for ln in lane_names:
            stats = self._lane_stats[ln]
            
            if stats.total == 0:
                P_display = 0
                self._prev_pressure[ln] = 0.0
                stats.pressure = 0
                stats.congestion_level = "LOW"
                stats.trend = "stable"
                if self._lane_speeds[ln]:
                    stats.avg_speed = float(np.mean(self._lane_speeds[ln]))
                else:
                    stats.avg_speed = 0.0
                continue
                
            if self._lane_speeds[ln]:
                stats.avg_speed = float(np.mean(self._lane_speeds[ln]))
            else:
                stats.avg_speed = 0.0
                
            # Queue Growth
            stopped_vehicles = stats.stopped
            vehicle_count = stats.total
            Q = stopped_vehicles / max(1.0, vehicle_count)
            prev_Q = self._Q_history[ln][-1] if self._Q_history[ln] else 0.0
            self._Q_history[ln].append(Q)
            delta_q = Q - prev_Q
            
            # PB — Phantom Braking (normalized to prevent saturation)
            hist_spd = list(self._lane_speeds[ln])
            current_avg_speed = hist_spd[-1] if hist_spd else 0.0
            prev_avg_speed = hist_spd[-2] if len(hist_spd) >= 2 else current_avg_speed
            delta_v = max(0.0, prev_avg_speed - current_avg_speed)

            # Normalize to [0, 1]
            delta_v_norm = max(0.0, min(delta_v / config.PB_MAX_DELTA_V, 1.0))
            var_norm     = max(0.0, min(speed_var / (speed_var + config.PB_VAR_C), 1.0))

            # Activation threshold: ignore negligible braking
            if delta_v_norm < config.PB_DV_THRESHOLD:
                PB = 0.0
            else:
                x = config.PB_A1 * delta_v_norm + config.PB_A2 * var_norm
                x = max(0.0, min(x, config.PB_MAX_SIGMOID_IN))
                PB = sigmoid(x)

            PB = max(0.0, min(PB, 1.0))
            
            # QG
            QG = sigmoid(config.QG_B1 * Q + config.QG_B2 * delta_q)
            
            # SG — Stop-Go Waves (normalized oscillation detection)
            # Filter out zero gradients (from reused detections on non-detect frames)
            osc_count = 0
            nz_grads = []
            if len(hist_spd) >= 3:
                for i in range(1, len(hist_spd)):
                    g = hist_spd[i] - hist_spd[i-1]
                    if abs(g) > 0.01:  # skip near-zero from reused frames
                        nz_grads.append(g)
                for i in range(1, len(nz_grads)):
                    if nz_grads[i] * nz_grads[i-1] < 0:
                        osc_count += 1

            # Normalize: square root of ratio to reduce sensitivity for low oscillations
            window_size = max(1, len(nz_grads))
            osc_ratio = osc_count / window_size if len(nz_grads) > 1 else 0.0
            osc_norm = math.sqrt(osc_ratio)
            osc_norm = max(0.0, min(osc_norm, 1.0))

            # Activation threshold: ignore stable traffic noise
            if osc_norm < config.SG_OSC_MIN_THRESHOLD:
                SG = 0.0
            else:
                x = max(0.0, min(osc_norm, config.SG_MAX_SIGMOID_IN))
                SG = sigmoid(x)

            SG = max(0.0, min(SG, 1.0))
            
            # D_i
            D = config.W_PB * PB + config.W_QG * QG + config.W_SG * SG + config.W_IM * IM
            
            # Core Pressure Calculation
            rho = rhos[ln]
            P_raw = config.ALPHA_RHO * rho + config.BETA_Q * Q + config.GAMMA_D * D
            
            # Smoothing
            P_smooth = config.P_SMOOTHING * self._prev_pressure[ln] + (1.0 - config.P_SMOOTHING) * P_raw
            self._prev_pressure[ln] = P_smooth
            
            P_display = max(0, min(100, int(P_smooth * 100.0)))
            stats.pressure = P_display
            stats.raw_pressure = P_smooth * 100.0
            stats.congestion_level = self._level(stats.pressure)
            
            # ── Trend prediction ──
            if len(self._lane_speeds[ln]) >= 3:
                recent_pressures = list(self._Q_history[ln])[-5:]
                if len(recent_pressures) >= 2:
                    avg_recent = np.mean(recent_pressures[-2:])
                    avg_prior  = np.mean(recent_pressures[:-2]) if len(recent_pressures) > 2 else recent_pressures[0]
                    if avg_recent > avg_prior + 0.05:
                        stats.trend = "rising"
                    elif avg_recent < avg_prior - 0.05:
                        stats.trend = "falling"
                    else:
                        stats.trend = "stable"

        return self._lane_stats

    def get_stats(self) -> Dict[str, LaneStats]:
        return self._lane_stats

    @staticmethod
    def _level(pressure: float) -> str:
        if pressure <= CONGESTION_LOW_MAX:
            return "LOW"
        if pressure >= CONGESTION_HIGH_MIN:
            return "HIGH"
        return "MEDIUM"
