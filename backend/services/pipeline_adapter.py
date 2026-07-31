"""
pipeline_adapter.py
────────────────────────────────────────────────────────────────────────────
Purpose:
    Pure-function adapter that converts Gamana's live frame state into the
    structured JSON format that FeatherlessTrafficService.generate_strategy()
    expects.

Why it exists:
    This module is the ONLY code that knows about both sides:
      - Left side:  Gamana's internal LaneStats / SignalStatus objects
      - Right side: Featherless AI input schema

    Keeping this logic here means neither the existing traffic modules nor
    the Featherless service ever need to know about each other.

    Zero dependencies on any Gamana module — it only reads public attributes
    via getattr(), so it will never crash if a field is missing.

Phase 2 role:
    Called by FeatherlessRunner each time a frame snapshot is submitted.

Phase 3 readiness:
    build_intersection_state() can be extended to include prediction data,
    risk scores, or trend direction without changing any existing module.
────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
def build_intersection_state(
    lane_stats: Dict[str, Any],
    signal_status: Any,
    behaviour_events: Optional[List[Any]] = None,
    predicted_pressures: Optional[Dict[str, float]] = None,
    frame_count: int = 0,
) -> Dict[str, Any]:
    """
    Convert Gamana's frame-level objects into the Featherless AI input schema.

    Parameters
    ----------
    lane_stats : dict
        Mapping of lane_name → LaneStats (object or dict).
    signal_status : SignalStatus
        The output of SignalController.update() for this frame.
    behaviour_events : list, optional
        BehaviourEvent objects from BehaviourDetector.update().
    predicted_pressures : dict, optional
        Lane → predicted pressure float from CongestionPredictor.
    frame_count : int
        Current frame number (for logging / tracing).

    Returns
    -------
    dict
        A dict matching the Featherless AI input schema:
        {
            "intersection": { lane_name: { ...metrics... }, ... },
            "current_signal": "LANE_N",
            "elapsed_green_time": float,
            "time_remaining": float,
            "green_duration": int,
            "signal_state": str,
            "frame_count": int,
            "timestamp": str
        }
    """
    # ── Collect per-lane behaviour strings ───────────────────────────────────
    lane_behaviours: Dict[str, List[str]] = {ln: [] for ln in lane_stats}
    if behaviour_events:
        for ev in behaviour_events:
            lane = _safe_str(ev, "lane", "")
            btype = _safe_event_type(ev)
            if lane in lane_behaviours and btype:
                lane_behaviours[lane].append(btype)

    # ── Build per-lane metrics ────────────────────────────────────────────────
    intersection: Dict[str, Any] = {}
    for ln, stats in lane_stats.items():
        pred_pressure = (predicted_pressures or {}).get(ln, 0.0)
        intersection[ln] = {
            "vehicle_count":   _safe_int(stats,  "total",           0),
            "moving":          _safe_int(stats,  "moving",          0),
            "stopped":         _safe_int(stats,  "stopped",         0),
            "pressure_score":  round(_safe_float(stats, "pressure", 0.0), 2),
            "predicted_pressure": round(float(pred_pressure), 2),
            "congestion":      _safe_str(stats,  "congestion_level", "LOW"),
            "wait_time_s":     round(_safe_float(stats, "wait_time", 0.0), 1),
            "flow_rate":       round(_safe_float(stats, "flow_rate", 0.0), 3),
            "emergency":       bool(_safe_get(stats, "emergency", False)),
            "behaviours":      lane_behaviours.get(ln, []),
        }

    # ── Build top-level context ───────────────────────────────────────────────
    active_lane    = _safe_str(signal_status, "active_lane",    "")
    time_remaining = round(_safe_float(signal_status, "time_remaining", 0.0), 1)
    green_duration = _safe_int(signal_status, "green_duration",  30)
    signal_state   = _safe_str(signal_status, "state",          "NORMAL")
    elapsed        = max(0.0, green_duration - time_remaining)

    return {
        "intersection":      intersection,
        "current_signal":    active_lane,
        "elapsed_green_time": round(elapsed, 1),
        "time_remaining":    time_remaining,
        "green_duration":    green_duration,
        "signal_state":      signal_state,
        "frame_count":       frame_count,
        "timestamp":         datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Safe attribute helpers — never raise, always return a typed default
# ─────────────────────────────────────────────────────────────────────────────

def _safe_get(obj: Any, key: str, default: Any) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _safe_int(obj: Any, key: str, default: int) -> int:
    try:
        return int(_safe_get(obj, key, default))
    except (TypeError, ValueError):
        return default


def _safe_float(obj: Any, key: str, default: float) -> float:
    try:
        return float(_safe_get(obj, key, default))
    except (TypeError, ValueError):
        return default


def _safe_str(obj: Any, key: str, default: str) -> str:
    try:
        return str(_safe_get(obj, key, default))
    except Exception:
        return default


def _safe_event_type(ev: Any) -> str:
    """Extract the behaviour type string from a BehaviourEvent or dict."""
    if hasattr(ev, "behaviour"):
        return getattr(ev.behaviour, "value", str(ev.behaviour))
    if isinstance(ev, dict):
        return str(ev.get("type", ""))
    return ""
