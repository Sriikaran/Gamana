"""
behaviour_detector.py — Pragati AI core module.
Detects Indian road micro-behaviours using vehicle tracking history.
No extra ML model needed — pure geometric + temporal logic on top of existing tracks.
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
import time
import numpy as np


class BehaviourType(Enum):
    PHANTOM_BRAKE       = "phantom_brake"       # sudden deceleration wave
    LANE_CUTTING        = "lane_cutting"         # abrupt lateral movement
    WRONG_SIDE_DRIVING  = "wrong_side"           # movement against flow direction
    STARTUP_DELAY       = "startup_delay"        # slow reaction to green
    BUS_STOP_BLOCKING   = "bus_blocking"         # stationary large vehicle blocking lane
    PEDESTRIAN_SURGE    = "pedestrian_surge"     # sudden ped count spike in road
    QUEUE_BUILDUP       = "queue_buildup"        # rapidly growing stopped cluster
    SPEED_VARIATION     = "speed_variation"      # high variance in speeds same lane
    LANE_IMBALANCE      = "lane_imbalance"       # one lane 3x vehicles of adjacent lane
    BIKE_GAP_FILLING    = "bike_gap_filling"     # motorcycle fills gap between stopped vehicles


# Risk levels
RISK_HIGH   = "HIGH"
RISK_MEDIUM = "MEDIUM"
RISK_LOW    = "LOW"

BEHAVIOUR_RISK = {
    BehaviourType.PHANTOM_BRAKE:      RISK_HIGH,
    BehaviourType.LANE_CUTTING:       RISK_HIGH,
    BehaviourType.WRONG_SIDE_DRIVING: RISK_HIGH,
    BehaviourType.STARTUP_DELAY:      RISK_MEDIUM,
    BehaviourType.BUS_STOP_BLOCKING:  RISK_MEDIUM,
    BehaviourType.PEDESTRIAN_SURGE:   RISK_MEDIUM,
    BehaviourType.QUEUE_BUILDUP:      RISK_HIGH,
    BehaviourType.SPEED_VARIATION:    RISK_LOW,
    BehaviourType.LANE_IMBALANCE:     RISK_MEDIUM,
    BehaviourType.BIKE_GAP_FILLING:   RISK_LOW,
}


@dataclass
class BehaviourEvent:
    behaviour: BehaviourType
    lane: str
    risk: str
    timestamp: float = field(default_factory=time.time)
    detail: str = ""

    def to_dict(self):
        return {
            "type": self.behaviour.value,
            "lane": self.lane,
            "risk": self.risk,
            "timestamp": self.timestamp,
            "detail": self.detail,
            "age_s": round(time.time() - self.timestamp, 1),
        }


class BehaviourDetector:
    """
    Consumes vehicle tracking history and lane metrics per frame.
    Emits BehaviourEvent objects when patterns are detected.
    """

    # Thresholds — tuned for Indian traffic
    PHANTOM_BRAKE_DECEL_THRESHOLD   = 0.30   # speed drops to <30% of prior speed (70%+ drop)
    PHANTOM_BRAKE_WINDOW_FRAMES     = 8      # check over last 8 frames
    PHANTOM_BRAKE_MIN_VEHICLES      = 3      # at least 3 decelerating in same lane (GROUP)
    LANE_CUT_LATERAL_PX             = 20     # lateral displacement per frame
    LANE_CUT_FRAMES                 = 3      # consecutive frames
    WRONG_SIDE_FRAMES               = 8      # frames moving opposite to expected
    STARTUP_DELAY_THRESHOLD_S       = 3.0    # seconds after green before checking
    STARTUP_DELAY_MIN_SLOW          = 2      # min vehicles with speed <1px/frame (GROUP)
    STARTUP_DELAY_SPEED_PX          = 1.0    # speed threshold px/frame for "not moving"
    BUS_BLOCK_MIN_AREA              = 30000  # px² — large vehicle
    BUS_BLOCK_STOPPED_FRAMES        = 40     # frames stationary
    QUEUE_BUILD_MIN_RISE            = 3      # stopped count must rise by this much
    QUEUE_BUILD_WINDOW_S            = 8.0    # within 8 seconds
    QUEUE_BUILD_MIN_GROUP           = 2      # must have at least 2 stopped vehicles (GROUP)
    SPEED_VARIANCE_THRESHOLD        = 400    # variance in speed (px/frame)²
    LANE_IMBALANCE_RATIO            = 3.0    # one lane has 3x vehicles of adjacent
    LANE_IMBALANCE_SUSTAIN_S        = 5.0    # imbalance must persist for 5 seconds
    BIKE_GAP_LATERAL_PX             = 15     # motorcycle lateral movement px threshold

    def __init__(self, lane_names: list, expected_flow_direction: str = "down"):
        """
        expected_flow_direction: 'down' | 'up' | 'left' | 'right'
        For typical top-mounted camera, vehicles usually move 'down' or 'right'.
        """
        self.lane_names = lane_names
        self.flow_dir = expected_flow_direction

        # Per-vehicle state
        self._positions: dict    = defaultdict(lambda: deque(maxlen=30))
        self._velocities: dict   = defaultdict(lambda: deque(maxlen=15))
        self._labels: dict       = {}
        self._lanes: dict        = {}
        self._stopped_since: dict = {}

        # Per-lane counters: (timestamp, stopped_count)
        self._lane_stopped_history: dict = {
            ln: deque(maxlen=240) for ln in lane_names
        }
        self._lane_green_time: dict = {ln: 0.0 for ln in lane_names}

        # Lane imbalance first-seen tracker for sustained check
        self._imbalance_first_seen: dict = {}  # key: (ln_heavy, ln_light) → timestamp

        # Event log (last 60 seconds)
        self._events: deque = deque(maxlen=200)

        # Cooldown per behaviour per lane to avoid spam — 8s as specified
        self._last_fired: dict = {}
        self._COOLDOWN = 8.0  # seconds

    # ── Main update ──────────────────────────────────────────────────────────

    def update(
        self,
        detections,          # list of Detection from vehicle_detector
        lane_map: dict,
        metrics: dict,
        current_green: str,
        green_changed: bool,
    ) -> list:
        """
        Call every frame. Returns list of NEW BehaviourEvent this frame.
        """
        now = time.time()
        new_events = []

        # Update tracking history
        for det in detections:
            if det.track_id < 0:
                continue
            self._positions[det.track_id].append((det.cx, det.cy))
            self._labels[det.track_id] = det.label
            if getattr(det, 'lane', None):
                self._lanes[det.track_id] = det.lane

            # Compute instantaneous velocity
            pos = list(self._positions[det.track_id])
            if len(pos) >= 2:
                dx = pos[-1][0] - pos[-2][0]
                dy = pos[-1][1] - pos[-2][1]
                speed = np.hypot(dx, dy)
                self._velocities[det.track_id].append((dx, dy, speed))

        # Update lane stopped history
        for ln in self.lane_names:
            m = metrics.get(ln)
            if m is not None:
                stopped_count = m.stopped if hasattr(m, 'stopped') else m.get('stopped', 0)
                self._lane_stopped_history[ln].append((now, int(stopped_count)))

        # Note green switch time
        if green_changed:
            self._lane_green_time[current_green] = now

        # Run each detector
        new_events += self._detect_phantom_brake(now, lane_map, metrics)
        new_events += self._detect_lane_cutting(now)
        new_events += self._detect_wrong_side(now, lane_map)
        new_events += self._detect_startup_delay(now, metrics, current_green)
        new_events += self._detect_bus_blocking(now, detections)
        new_events += self._detect_queue_buildup(now, metrics)
        new_events += self._detect_speed_variation(now, lane_map)
        new_events += self._detect_lane_imbalance(now, lane_map)
        new_events += self._detect_bike_gap_filling(now, lane_map, detections)

        # Add to log
        for ev in new_events:
            self._events.append(ev)

        return new_events

    # ── Individual detectors ─────────────────────────────────────────────────

    def _detect_phantom_brake(self, now, lane_map, metrics) -> list:
        """
        Detects deceleration shockwaves: 3+ vehicles (GROUP) rapidly decelerating
        (speed drops 70%+ → remains <30% of peak) in same lane over 8 frames → HIGH.
        Single vehicle never triggers alone.
        """
        events = []
        for lane_name, dets in lane_map.items():
            decelerating = []
            for det in dets:
                vels = list(self._velocities.get(det.track_id, []))
                if len(vels) < 4:
                    continue
                # Check speed drop over last 8 frames
                window = min(len(vels), self.PHANTOM_BRAKE_WINDOW_FRAMES)
                speeds = [v[2] for v in vels[-window:]]
                # Vehicle must have been moving, then dropped to <30% (70%+ drop)
                peak = max(speeds[:-1]) if len(speeds) > 1 else speeds[0]
                current_speed = speeds[-1]
                if peak > 3.0 and current_speed < peak * self.PHANTOM_BRAKE_DECEL_THRESHOLD:
                    decelerating.append(det.track_id)

            # GROUP evidence required: at least 3 vehicles
            if len(decelerating) >= self.PHANTOM_BRAKE_MIN_VEHICLES:
                if self._can_fire(BehaviourType.PHANTOM_BRAKE, lane_name, now):
                    events.append(BehaviourEvent(
                        behaviour=BehaviourType.PHANTOM_BRAKE,
                        lane=lane_name,
                        risk=RISK_HIGH,
                        detail=f"{len(decelerating)} vehicles sudden brake (70%+ speed drop)",
                    ))
        return events

    def _detect_lane_cutting(self, now) -> list:
        """
        Detects abrupt lateral position change over consecutive frames.
        """
        events = []
        for tid, pos_deque in self._positions.items():
            pos = list(pos_deque)
            if len(pos) < self.LANE_CUT_FRAMES + 1:
                continue
            recent = pos[-self.LANE_CUT_FRAMES - 1:]
            lateral = [abs(recent[i+1][0] - recent[i][0]) for i in range(len(recent)-1)]
            if all(l > self.LANE_CUT_LATERAL_PX for l in lateral):
                lane = self._lanes.get(tid, "?")
                if self._can_fire(BehaviourType.LANE_CUTTING, lane, now):
                    events.append(BehaviourEvent(
                        behaviour=BehaviourType.LANE_CUTTING,
                        lane=lane,
                        risk=RISK_HIGH,
                        detail=f"Vehicle #{tid} abrupt lateral move",
                    ))
        return events

    def _detect_wrong_side(self, now, lane_map) -> list:
        """
        Detects vehicles moving against expected traffic direction.
        Expected: 'down' means dy should be positive.
        """
        events = []
        dir_map = {"down": (1, 1), "up": (-1, 1), "left": (-1, 0), "right": (1, 0)}
        sign, axis = dir_map.get(self.flow_dir, (1, 1))

        for tid, vel_deque in self._velocities.items():
            vels = list(vel_deque)
            if len(vels) < self.WRONG_SIDE_FRAMES:
                continue
            recent = vels[-self.WRONG_SIDE_FRAMES:]
            components = [v[axis] for v in recent]
            if all(c * sign < -1.5 for c in components):
                lane = self._lanes.get(tid, "?")
                if self._can_fire(BehaviourType.WRONG_SIDE_DRIVING, lane, now):
                    events.append(BehaviourEvent(
                        behaviour=BehaviourType.WRONG_SIDE_DRIVING,
                        lane=lane,
                        risk=RISK_HIGH,
                        detail=f"Vehicle #{tid} moving against traffic",
                    ))
        return events

    def _detect_startup_delay(self, now, metrics, current_green) -> list:
        """
        After signal turns green 3s+, 2+ vehicles (GROUP) with speed <1px/frame → MEDIUM.
        Checks individual vehicle speeds, not aggregate stopped count.
        """
        events = []
        green_since = self._lane_green_time.get(current_green, now)
        elapsed = now - green_since
        if elapsed < self.STARTUP_DELAY_THRESHOLD_S:
            return events

        # Count individual vehicles in the green lane with speed < 1px/frame (GROUP check)
        slow_vehicles = 0
        for tid, lane in self._lanes.items():
            if lane != current_green:
                continue
            vels = list(self._velocities.get(tid, []))
            if not vels:
                continue
            current_speed = vels[-1][2]  # speed magnitude px/frame
            if current_speed < self.STARTUP_DELAY_SPEED_PX:
                slow_vehicles += 1

        if slow_vehicles >= self.STARTUP_DELAY_MIN_SLOW:
            if self._can_fire(BehaviourType.STARTUP_DELAY, current_green, now):
                events.append(BehaviourEvent(
                    behaviour=BehaviourType.STARTUP_DELAY,
                    lane=current_green,
                    risk=RISK_MEDIUM,
                    detail=f"{slow_vehicles} vehicles <1px/frame after {elapsed:.0f}s on green",
                ))
        return events

    def _detect_bus_blocking(self, now, detections) -> list:
        """
        Large stationary vehicle (bus/truck) blocking lane for extended period.
        """
        events = []
        for det in detections:
            if det.label not in ("bus", "truck"):
                continue
            x1, y1, x2, y2 = det.x1, det.y1, det.x2, det.y2
            area = (x2 - x1) * (y2 - y1)
            if area < self.BUS_BLOCK_MIN_AREA:
                continue
            vels = list(self._velocities.get(det.track_id, []))
            if len(vels) >= self.BUS_BLOCK_STOPPED_FRAMES:
                recent_speeds = [v[2] for v in vels[-self.BUS_BLOCK_STOPPED_FRAMES:]]
                if np.mean(recent_speeds) < 1.5:
                    lane = getattr(det, 'lane', None) or "?"
                    if self._can_fire(BehaviourType.BUS_STOP_BLOCKING, lane, now):
                        events.append(BehaviourEvent(
                            behaviour=BehaviourType.BUS_STOP_BLOCKING,
                            lane=lane,
                            risk=RISK_MEDIUM,
                            detail=f"{det.label} #{det.track_id} blocking lane",
                        ))
        return events

    def _detect_queue_buildup(self, now, metrics) -> list:
        """
        Stopped count rises 3+ in 8 seconds AND current stopped count ≥ 2 (GROUP) → HIGH.
        Single vehicle alone never triggers this alert.
        """
        events = []
        for lane_name in self.lane_names:
            history = self._lane_stopped_history.get(lane_name)
            if history is None or len(history) < 2:
                continue
            # Keep only points within the 8-second window
            window = [(t, c) for (t, c) in history if now - t <= self.QUEUE_BUILD_WINDOW_S]
            if len(window) < 2:
                continue
            rise = window[-1][1] - window[0][1]
            current_stopped = window[-1][1]
            # GROUP evidence: rise of 3+ AND at least 2 vehicles currently stopped
            if rise >= self.QUEUE_BUILD_MIN_RISE and current_stopped >= self.QUEUE_BUILD_MIN_GROUP:
                if self._can_fire(BehaviourType.QUEUE_BUILDUP, lane_name, now):
                    events.append(BehaviourEvent(
                        behaviour=BehaviourType.QUEUE_BUILDUP,
                        lane=lane_name,
                        risk=RISK_HIGH,
                        detail=f"Queue grew by {rise} (now {current_stopped} stopped) in 8s",
                    ))
        return events

    def _detect_speed_variation(self, now, lane_map) -> list:
        """
        High speed variance within a lane = erratic driving, accident precursor.
        """
        events = []
        for lane_name, dets in lane_map.items():
            speeds = []
            for det in dets:
                vels = list(self._velocities.get(det.track_id, []))
                if vels:
                    speeds.append(vels[-1][2])
            if len(speeds) >= 4:
                variance = float(np.var(speeds))
                if variance >= self.SPEED_VARIANCE_THRESHOLD:
                    if self._can_fire(BehaviourType.SPEED_VARIATION, lane_name, now):
                        events.append(BehaviourEvent(
                            behaviour=BehaviourType.SPEED_VARIATION,
                            lane=lane_name,
                            risk=RISK_LOW,
                            detail=f"Speed variance {variance:.0f}",
                        ))
        return events

    def _detect_lane_imbalance(self, now, lane_map) -> list:
        """
        One lane has 3x vehicles of an adjacent lane, sustained for 5s → MEDIUM risk.
        Imbalance must persist continuously before firing.
        """
        events = []
        names = [ln for ln in self.lane_names if ln in lane_map]
        counts = {ln: len(lane_map.get(ln, [])) for ln in names}

        # Track which pairs are currently imbalanced
        active_pairs = set()

        for i in range(len(names) - 1):
            ln_a = names[i]
            ln_b = names[i + 1]
            ca = counts.get(ln_a, 0)
            cb = counts.get(ln_b, 0)

            heavy, light, ch, cl = None, None, 0, 0
            if ca > 0 and cb > 0:
                if ca >= self.LANE_IMBALANCE_RATIO * cb:
                    heavy, light, ch, cl = ln_a, ln_b, ca, cb
                elif cb >= self.LANE_IMBALANCE_RATIO * ca:
                    heavy, light, ch, cl = ln_b, ln_a, cb, ca

            if heavy is not None:
                pair_key = (heavy, light)
                active_pairs.add(pair_key)
                # Record when this imbalance first appeared
                if pair_key not in self._imbalance_first_seen:
                    self._imbalance_first_seen[pair_key] = now
                sustained = now - self._imbalance_first_seen[pair_key]
                # Only fire after 5s sustained imbalance
                if sustained >= self.LANE_IMBALANCE_SUSTAIN_S:
                    if self._can_fire(BehaviourType.LANE_IMBALANCE, heavy, now):
                        events.append(BehaviourEvent(
                            behaviour=BehaviourType.LANE_IMBALANCE,
                            lane=light,   # underserved lane
                            risk=RISK_MEDIUM,
                            detail=f"{heavy} has {ch} vs {light} has {cl} vehicles (sustained {sustained:.0f}s)",
                        ))

        # Clear first-seen timestamps for pairs no longer imbalanced
        stale = [k for k in self._imbalance_first_seen if k not in active_pairs]
        for k in stale:
            del self._imbalance_first_seen[k]

        return events

    def _detect_bike_gap_filling(self, now, lane_map, detections) -> list:
        """
        Motorcycle moves laterally 15+ px between stopped vehicles → LOW risk.
        Checks motorcycles surrounded by stopped vehicles in the same lane.
        """
        events = []
        # Build a set of stopped vehicle positions per lane
        stopped_positions = defaultdict(list)
        for det in detections:
            if not getattr(det, 'is_moving', True):
                ln = getattr(det, 'lane', None)
                if ln:
                    stopped_positions[ln].append((det.cx, det.cy))

        for det in detections:
            if det.label not in ("motorcycle", "bicycle"):
                continue
            if det.track_id < 0:
                continue
            lane = getattr(det, 'lane', None)
            if not lane:
                continue

            # Check lateral movement of this motorcycle
            pos = list(self._positions.get(det.track_id, []))
            if len(pos) < 3:
                continue
            lateral_moves = [abs(pos[i+1][0] - pos[i][0]) for i in range(len(pos)-1)]
            max_lateral = max(lateral_moves[-3:]) if len(lateral_moves) >= 3 else 0

            if max_lateral >= self.BIKE_GAP_LATERAL_PX:
                # Confirm there are stopped vehicles nearby in same lane
                nearby_stopped = stopped_positions.get(lane, [])
                if len(nearby_stopped) >= 2:
                    if self._can_fire(BehaviourType.BIKE_GAP_FILLING, lane, now):
                        events.append(BehaviourEvent(
                            behaviour=BehaviourType.BIKE_GAP_FILLING,
                            lane=lane,
                            risk=RISK_LOW,
                            detail=f"Bike #{det.track_id} gap-filling ({max_lateral:.0f}px lateral)",
                        ))
        return events

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _can_fire(self, behaviour: BehaviourType, lane: str, now: float) -> bool:
        key = (behaviour, lane)
        last = self._last_fired.get(key, 0.0)
        if now - last >= self._COOLDOWN:
            self._last_fired[key] = now
            return True
        return False

    def get_recent_events(self, window_s: float = 30.0) -> list:
        now = time.time()
        return [e for e in self._events if now - e.timestamp <= window_s]

    def get_lane_behaviour_summary(self, window_s: float = 30.0) -> dict:
        """Returns per-lane count of each behaviour type in the last window."""
        summary = {ln: {} for ln in self.lane_names}
        for ev in self.get_recent_events(window_s):
            if ev.lane in summary:
                key = ev.behaviour.value
                summary[ev.lane][key] = summary[ev.lane].get(key, 0) + 1
        return summary

    def get_policy_breakdown(self, window_s: float = 60.0) -> list:
        """Returns sorted list of behaviour causes with percentages — for policy dashboard."""
        events = self.get_recent_events(window_s)
        counts = defaultdict(int)
        for ev in events:
            counts[ev.behaviour.value] += 1
        total = sum(counts.values()) or 1
        return sorted(
            [{"cause": k, "count": v, "pct": round(v / total * 100, 1)}
             for k, v in counts.items()],
            key=lambda x: x["count"], reverse=True
        )