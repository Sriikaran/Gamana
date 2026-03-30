"""
modules/video_renderer.py
──────────────────────────
Pragati AI — Clean video annotation.

What this draws:
  1. Thin lane boundary lines (NOT heavy filled overlays)
  2. Clean vehicle boxes — minimal, color-coded by type
  3. Vehicle label chips — type + ID only (no clutter)
  4. Per-lane HUD panel — pressure bar, signal dot, vehicle count
  5. Active signal banner — top center
  6. Behaviour alert ticker — bottom of screen
  7. Ambulance override — red flashing border + banner
  8. Risk level indicator per lane
  9. System state badge
"""

from __future__ import annotations

import cv2
import numpy as np
import time
from typing import Optional

try:
    import config
except ImportError:
    pass


# ── Color palette ─────────────────────────────────────────────────────────────
VEHICLE_COLORS = {
    "car":        (255, 255, 255),   # white
    "motorcycle": (255, 255,   0),   # cyan
    "auto":       (  0, 255, 255),   # yellow
    "bus":        (  0,   0, 255),   # red
    "truck":      (  0, 128, 255),   # orange
    "bicycle":    (180, 255, 100),   # lime
    "person":     (200, 200, 200),   # gray
    "ambulance":  (  0,   0, 255),   # bright red
}

SIGNAL_COLORS = {
    "green":  (50, 220, 80),
    "red":    (60,  60, 200),
    "yellow": (50, 200, 220),
}

RISK_COLORS = {
    "LOW":      (80,  200,  80),
    "MEDIUM":   (50,  180, 220),
    "HIGH":     (50,   80, 220),
    "CRITICAL": (30,   30, 200),
}

LANE_BORDER_COLORS = {
    "LEFT":         (255, 200,  50),
    "LEFT_CENTER":  ( 50, 200, 255),
    "CENTER":       (100, 255, 100),
    "RIGHT_CENTER": (200, 255,  50),
    "RIGHT":        (255,  50, 200),
    "LANE_1":       (255, 200,  50),
    "LANE_2":       ( 50, 200, 255),
    "LANE_3":       (200, 255,  50),
    "LANE_4":       (255,  50, 200),
}


class VideoRenderer:

    def __init__(self):
        self._amb_flash_time = 0.0
        self._behaviour_ticker = []   # list of (text, color, expire_time)
        self._font     = cv2.FONT_HERSHEY_SIMPLEX
        self._font_b   = cv2.FONT_HERSHEY_DUPLEX

    # ── Main render ───────────────────────────────────────────────────────────

    def render(
        self,
        frame:      np.ndarray,
        detections: list,
        lane_polys: dict,
        lane_stats: dict,
        signal_status,
        predicted:  dict,
        trends:     dict,
        behaviour_events: list = None,
        risks:      dict = None,
        prediction_data: dict = None,
    ) -> np.ndarray:

        out = frame.copy()
        H, W = out.shape[:2]

        active_lane = getattr(signal_status, 'active_lane', '')
        state       = getattr(signal_status, 'state',       'NORMAL')

        signals = {
            ln: ("green" if ln == active_lane else "red")
            for ln in lane_polys
        }

        # 1. Thin lane boundaries (no heavy fill)
        self._draw_lane_borders(out, lane_polys, signals)

        # 2. Per-lane HUD panels (right side)
        self._draw_lane_hud(out, lane_stats, signals, risks or {}, trends,
                            prediction_data or {})

        # 3. Vehicle bounding boxes — drawn AFTER lane overlays to stay visible
        self._draw_vehicles(out, detections)

        # 4. Active signal banner (top center)
        self._draw_signal_banner(out, signal_status, W)

        # 4b. Switch reason banner (3s display after signal switches)
        switch_reason = getattr(signal_status, 'switch_reason', '')
        if switch_reason:
            self._draw_switch_banner(out, switch_reason, W, H)

        # 5. Behaviour event ticker (bottom)
        if behaviour_events:
            self._update_ticker(behaviour_events)
        self._draw_ticker(out, W, H)

        # 6. Ambulance override
        if str(state) in ("AMBULANCE_OVERRIDE", "SignalState.AMBULANCE_OVERRIDE"):
            self._draw_ambulance_overlay(out, W, H)

        # 7. System state badge (top left)
        self._draw_state_badge(out, state)

        # 8. Stats footer bar
        self._draw_footer(out, lane_stats, W, H)

        return out

    # ── Lane borders — thin lines only, tiny fill ─────────────────────────────

    def _draw_lane_borders(self, frame, lane_polys, signals):
        for name, poly in lane_polys.items():
            is_green = signals.get(name) == "green"
            color    = LANE_BORDER_COLORS.get(name, (180, 180, 180))

            # Thin boundary lines only — no road-covering fills
            border_color = (0, 230, 80) if is_green else color
            thickness    = 2
            cv2.polylines(frame, [poly], isClosed=True,
                          color=border_color, thickness=thickness,
                          lineType=cv2.LINE_AA)

            # Lane name — small, at top of lane polygon
            pts = poly.reshape(-1, 2)
            top_pts = sorted(pts, key=lambda p: p[1])[:2]
            lx = int((top_pts[0][0] + top_pts[1][0]) / 2)
            ly = int((top_pts[0][1] + top_pts[1][1]) / 2) + 18
            self._text_chip(frame, name, lx, ly, color, scale=0.38, center=True)

    # ── Vehicle boxes ─────────────────────────────────────────────────────────

    def _draw_vehicles(self, frame, detections):
        for det in detections:
            x1, y1, x2, y2 = self._get_bbox(det)
            label    = getattr(det, 'label', 'car')
            is_amb   = getattr(det, 'is_ambulance', False)

            color = (0, 0, 255) if is_amb else VEHICLE_COLORS.get(label, (200, 200, 200))

            thickness = 3 if is_amb else 1
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)

            # Show only vehicle type — no ID, confidence, or movement state
            chip_text = self._vehicle_label_short(label)

            self._text_chip(frame, chip_text, x1, y1 - 2, color,
                            scale=0.34, anchor="bottom-left")

    # ── Per-lane HUD panel (right side) ───────────────────────────────────────

    def _draw_lane_hud(self, frame, lane_stats, signals, risks, trends, prediction_data=None):
        H, W = frame.shape[:2]
        panel_w  = 200
        panel_x  = W - panel_w - 8
        row_h    = 72
        start_y  = 8
        pred_data = prediction_data if prediction_data else {}

        for i, (lane_name, stats) in enumerate(lane_stats.items()):
            bx = panel_x
            by = start_y + i * (row_h + 5)

            is_green = signals.get(lane_name) == "green"
            pressure = self._get_pressure(stats)
            total    = self._get_stat(stats, 'total',   0)
            moving   = self._get_stat(stats, 'moving',  0)
            stopped  = self._get_stat(stats, 'stopped', 0)

            risk_obj  = risks.get(lane_name, {})
            risk_lvl  = risk_obj.get('level', 'LOW') if isinstance(risk_obj, dict) else 'LOW'
            trend     = trends.get(lane_name, 'stable')

            lane_name_clean = str(lane_name).replace("??", "")
            risk_lvl = str(risk_lvl).replace("??", "")

            # Prediction data
            pd = pred_data.get(lane_name, {})
            jam_warning = pd.get('jam_warning', False)
            ttj = pd.get('time_to_jam_seconds', 999.0)
            # Arrows: rising=red ↑, stable=gray →, falling=green ↓
            pred_arrow  = "^" if trend == "rising" else ("v" if trend == "falling" else "-")
            arrow_color = (40, 50, 220) if trend == "rising" else (60, 200, 70) if trend == "falling" else (160, 160, 160)

            # Background panel
            bg_color = (0, 28, 8) if is_green else (10, 14, 24)
            overlay  = frame.copy()
            cv2.rectangle(overlay, (bx, by), (bx + panel_w, by + row_h), bg_color, -1)
            cv2.addWeighted(overlay, 0.78, frame, 0.22, 0, frame)

            # Border
            border_col = (0, 200, 60) if is_green else (40, 55, 80)
            cv2.rectangle(frame, (bx, by), (bx + panel_w, by + row_h),
                          border_col, 1, cv2.LINE_AA)

            # Signal dot
            dot_col = (0, 220, 70) if is_green else (60, 60, 100)
            cv2.circle(frame, (bx + 12, by + 12), 5, dot_col, -1, cv2.LINE_AA)

            # Lane name
            cv2.putText(frame, lane_name_clean.replace('_', '-'),
                        (bx + 22, by + 16),
                        self._font, 0.42, (220, 225, 235), 1, cv2.LINE_AA)

            # Risk badge
            risk_col = RISK_COLORS.get(risk_lvl, (80, 80, 80))
            self._text_chip(frame, risk_lvl, bx + panel_w - 22, by + 8,
                            risk_col, scale=0.30, anchor="top-right")

            # Prediction arrow (right edge)
            cv2.putText(frame, pred_arrow,
                        (bx + panel_w - 14, by + 22),
                        self._font, 0.55, arrow_color, 1, cv2.LINE_AA)

            # Pressure bar
            bar_x = bx + 8
            bar_y = by + 26
            bar_w = panel_w - 16
            bar_h = 7

            cv2.rectangle(frame, (bar_x, bar_y),
                          (bar_x + bar_w, bar_y + bar_h), (30, 36, 52), -1)

            fill_w = int(bar_w * min(pressure, 100) / 100.0)
            if fill_w > 0:
                bar_color = self._pressure_color(pressure)
                cv2.rectangle(frame, (bar_x, bar_y),
                              (bar_x + fill_w, bar_y + bar_h), bar_color, -1)

            # Pressure value
            cv2.putText(frame, f"{pressure:.0f}%",
                        (bar_x + bar_w + 4, bar_y + bar_h),
                        self._font, 0.36, self._pressure_color(pressure), 1, cv2.LINE_AA)

            # Stats row: T/M/S
            stats_text = f"T:{total}  M:{moving}  S:{stopped}"
            cv2.putText(frame, stats_text, (bx + 8, by + 48),
                        self._font, 0.36, (160, 170, 190), 1, cv2.LINE_AA)

            # Jam warning / time-to-jam or vehicle type breakdown
            if jam_warning and ttj < 999.0:
                jam_text = f"~{ttj:.0f}s to jam"
                # Amber color in BGR: (0, 165, 255)
                cv2.putText(frame, jam_text, (bx + 8, by + 62),
                            self._font, 0.30, (0, 165, 255), 1, cv2.LINE_AA)
            else:
                vc = self._get_stat(stats, 'vehicle_counts', {})
                if isinstance(vc, dict) and vc:
                    vtext = "  ".join(
                        f"{k[:3]}:{v}" for k, v in list(vc.items())[:3]
                    )
                    cv2.putText(frame, vtext, (bx + 8, by + 62),
                                self._font, 0.30, (100, 110, 130), 1, cv2.LINE_AA)

    # ── Switch reason banner ───────────────────────────────────────────────────

    def _draw_switch_banner(self, frame, switch_text: str, W: int, H: int):
        """Draw 3-second switch notification: 'SIGNAL: LEFT→RIGHT  Reason: ...'"""
        font_scale = 0.50
        (tw, th), _ = cv2.getTextSize(switch_text, self._font, font_scale, 1)
        tx = (W - tw) // 2
        ty = H // 2
        pad = 8
        cv2.rectangle(frame, (tx - pad, ty - th - pad),
                      (tx + tw + pad, ty + pad), (8, 10, 18), -1)
        cv2.rectangle(frame, (tx - pad, ty - th - pad),
                      (tx + tw + pad, ty + pad), (50, 200, 50), 1)
        cv2.putText(frame, switch_text, (tx, ty),
                    self._font, font_scale, (180, 255, 180), 1, cv2.LINE_AA)

    # ── Active signal banner (top center) ────────────────────────────────────

    def _draw_signal_banner(self, frame, signal_status, W):
        active_lane    = getattr(signal_status, 'active_lane',   '')
        time_remaining = getattr(signal_status, 'time_remaining', 0)
        green_duration = getattr(signal_status, 'green_duration', 20)
        state          = str(getattr(signal_status, 'state', 'NORMAL'))

        # Progress bar across top
        progress = max(0.0, min(1.0, time_remaining / max(green_duration, 1)))
        bar_color = (0, 200, 60) if 'NORMAL' in state or 'COOLDOWN' in state else (60, 60, 200)
        bar_h = 4
        fill_w = int(W * progress)
        cv2.rectangle(frame, (0, 0), (W, bar_h), (20, 25, 35), -1)
        if fill_w > 0:
            cv2.rectangle(frame, (0, 0), (fill_w, bar_h), bar_color, -1)

        # Central banner
        lane_display = active_lane.replace('_', '-') if active_lane else '---'
        timer_display = f"{int(time_remaining)}s"

        banner_text = f"GREEN: {lane_display}    {timer_display}"
        font_scale  = 0.60
        (tw, th), _ = cv2.getTextSize(banner_text, self._font, font_scale, 1)
        tx = (W - tw) // 2
        ty = 24

        # Background
        cv2.rectangle(frame, (tx - 12, ty - th - 5),
                      (tx + tw + 12, ty + 7), (8, 10, 16), -1)
        cv2.rectangle(frame, (tx - 12, ty - th - 5),
                      (tx + tw + 12, ty + 7), bar_color, 1)

        cv2.putText(frame, banner_text, (tx, ty),
                    self._font, font_scale, (230, 240, 255), 1, cv2.LINE_AA)

    # ── Behaviour ticker (bottom center) ─────────────────────────────────────

    def _update_ticker(self, events):
        now = time.time()
        for ev in events:
            t    = ev.timestamp if hasattr(ev, 'timestamp') else now
            btype = ev.behaviour.value if hasattr(ev, 'behaviour') else str(ev.get('type', ''))
            lane  = ev.lane if hasattr(ev, 'lane') else ev.get('lane', '')
            risk  = ev.risk if hasattr(ev, 'risk') else ev.get('risk', 'LOW')

            lane_u = str(lane).replace(" ", "_").upper()
            msg   = f"ALERT: {btype.replace('_',' ').upper()} in {lane_u}"
            bt = str(btype).lower() if btype else ""
            if bt == "startup_delay":
                color = (0, 165, 255)
            else:
                color = (30, 30, 220) if risk == 'HIGH' else (50, 165, 230) if risk == 'MEDIUM' else (80, 180, 80)
            expire = now + 5.0

            # Avoid duplicate
            existing = [t[0] for t in self._behaviour_ticker]
            if msg not in existing:
                self._behaviour_ticker.append((msg, color, expire))

        # Prune expired
        now = time.time()
        self._behaviour_ticker = [t for t in self._behaviour_ticker if t[2] > now]
        # Keep max 3
        self._behaviour_ticker = self._behaviour_ticker[-3:]

    def _draw_ticker(self, frame, W, H):
        if not self._behaviour_ticker:
            return
        now = time.time()
        pad = 6
        for i, (msg, color, expire) in enumerate(reversed(self._behaviour_ticker)):
            fade = min(1.0, expire - now)
            alpha = max(0.3, fade)
            y = H - 30 - i * 22
            (tw, th), _ = cv2.getTextSize(msg, self._font, 0.46, 1)
            tx = (W - tw) // 2
            overlay = frame.copy()
            cv2.rectangle(overlay, (tx - pad, y - th - pad),
                          (tx + tw + pad, y + pad), (6, 8, 14), -1)
            cv2.addWeighted(overlay, 0.75 * alpha, frame, 1 - 0.75 * alpha, 0, frame)
            cv2.rectangle(frame, (tx - pad, y - th - pad),
                          (tx + tw + pad, y + pad), color, 1)
            faded_color = tuple(int(c * alpha) for c in color)
            cv2.putText(frame, msg, (tx, y),
                        self._font, 0.46, faded_color, 1, cv2.LINE_AA)

    # ── Ambulance overlay ─────────────────────────────────────────────────────

    def _draw_ambulance_overlay(self, frame, W, H):
        # Flashing red border every 0.4s
        flash = int(time.time() * 2.5) % 2 == 0
        if flash:
            for t in range(4):
                cv2.rectangle(frame, (t, t), (W - t, H - t), (0, 0, 220), 1)

        # Top banner
        msg = "  AMBULANCE DETECTED  PRIORITY GREEN OVERRIDE  "
        (tw, th), _ = cv2.getTextSize(msg, self._font_b, 0.65, 1)
        tx = (W - tw) // 2
        cv2.rectangle(frame, (tx - 10, 35), (tx + tw + 10, 68), (0, 0, 180), -1)
        cv2.putText(frame, msg, (tx, 60),
                    self._font_b, 0.65, (255, 255, 255), 1, cv2.LINE_AA)

    # ── State badge (top left) ────────────────────────────────────────────────

    def _draw_state_badge(self, frame, state):
        raw = str(state).replace("SignalState.", "")
        if raw == "AMBULANCE_OVERRIDE":
            state_str = "AMBULANCE"
        else:
            state_str = raw.replace("_", " ")
        colors = {
            "NORMAL":    (50, 200,  80),
            "COOLDOWN":  (50, 180, 220),
            "AMBULANCE": (30,  30, 220),
            "FAILSAFE":  (50, 140, 220),
        }
        color = colors.get(state_str, (120, 120, 120))
        w_chip = 150 if state_str == "AMBULANCE" else 130
        cv2.rectangle(frame, (6, 8), (w_chip, 28), (8, 10, 16), -1)
        cv2.rectangle(frame, (6, 8), (w_chip, 28), color, 1)
        cv2.putText(frame, state_str, (10, 22),
                    self._font, 0.40, color, 1, cv2.LINE_AA)

    # ── Footer stats bar ──────────────────────────────────────────────────────

    def _draw_footer(self, frame, lane_stats, W, H):
        total_vehicles = sum(
            self._get_stat(s, 'total', 0) for s in lane_stats.values()
        )
        text = f"Pragati AI | Vehicles: {total_vehicles} | Lanes: {len(lane_stats)}"
        cv2.rectangle(frame, (0, H - 22), (W, H), (6, 8, 14), -1)
        cv2.putText(frame, text, (8, H - 8),
                    self._font, 0.38, (80, 90, 110), 1, cv2.LINE_AA)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _text_chip(self, frame, text, x, y, color,
                   scale=0.38, anchor="top-left", center=False):
        """Draw a small dark background chip with text."""
        text = str(text).replace("??", "")
        font   = self._font
        thick  = 1
        (tw, th), baseline = cv2.getTextSize(text, font, scale, thick)
        pad = 3

        if center:
            tx = x - tw // 2
            ty = y
        elif anchor == "bottom-left":
            tx = x
            ty = y - baseline
        elif anchor == "top-right":
            tx = x - tw - pad * 2
            ty = y + th + pad
        else:
            tx = x
            ty = y + th + pad

        cv2.rectangle(frame,
                      (tx - pad, ty - th - pad),
                      (tx + tw + pad, ty + baseline + pad),
                      (6, 8, 14), -1)
        cv2.putText(frame, text, (tx, ty),
                    font, scale, color, thick, cv2.LINE_AA)

    @staticmethod
    def _pressure_color(pressure: float):
        if pressure > 70: return (40,  50, 220)
        if pressure > 45: return (40, 165, 230)
        return (60, 200, 70)

    @staticmethod
    def _get_bbox(det):
        bbox = getattr(det, 'bbox', None)
        if bbox:
            return int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        return 0, 0, 50, 50

    @staticmethod
    def _vehicle_label_short(label: str) -> str:
        m = {
            "car": "CAR",
            "motorcycle": "MOTORCYCLE",
            "auto": "AUTO",
            "bus": "BUS",
            "truck": "TRUCK",
            "bicycle": "BICYCLE",
            "person": "PERSON",
            "ambulance": "AMBULANCE",
        }
        return m.get(str(label).lower(), str(label)[:4].upper())

    @staticmethod
    def _get_pressure(stats) -> float:
        if isinstance(stats, dict):
            return float(stats.get('pressure', 0.0))
        return float(getattr(stats, 'pressure', 0.0))

    @staticmethod
    def _get_stat(stats, key, default):
        if isinstance(stats, dict):
            return stats.get(key, default)
        return getattr(stats, key, default)