"""
modules/lane_manager.py
────────────────────────
Lane manager:
  - If a per-video calibration file exists (lane_config_{source}.json), load those polygons.
  - Otherwise fall back to equal vertical strips.
  - Always assigns each vehicle to a lane: if the bbox center isn't inside any polygon,
    assign to the nearest lane by x (cx) distance.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

import config

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


@dataclass
class LaneStats:
    """Returned by assign_lanes() — per-lane vehicle list."""

    name: str
    detections: list


class LaneManager:
    def __init__(self):
        self.lane_names: list[str] = list(config.LANE_NAMES)
        self.lane_count: int = config.LANE_COUNT
        self.colors = config.LANE_COLORS_MAP
        self.frame_w = config.FRAME_WIDTH
        self.frame_h = config.FRAME_HEIGHT

        self._polygons: dict[str, np.ndarray] = {}
        self._areas: dict[str, float] = {}
        self._lane_centroid_x: dict[str, float] = {}
        self._lane_centroid_y: dict[str, float] = {}

        self._build_polygons()

    def set_frame_size(self, w: int, h: int):
        self.frame_w = w
        self.frame_h = h
        self._build_polygons()

    def initialize_from_frame(self, frame: np.ndarray) -> None:
        """Call once on first frame (mainly to sync frame size)."""
        if frame is None or frame.size == 0:
            return
        h, w = frame.shape[:2]
        self.set_frame_size(w, h)

    def _calibration_path_for_current_source(self) -> Optional[str]:
        src = str(getattr(config, "VIDEO_SOURCE", "")).strip()
        if not src:
            return None
        if src.isdigit():
            return None  # webcam index: no calibration

        src_base = os.path.basename(src)
        stem = os.path.splitext(src_base)[0]
        filename = f"lane_config_{stem}.json"
        return os.path.join(_PROJECT_ROOT, filename)

    def _try_load_calibration(self) -> bool:
        path = self._calibration_path_for_current_source()
        if not path or not os.path.isfile(path):
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False

        src = str(getattr(config, "VIDEO_SOURCE", ""))
        src_base = os.path.basename(src)
        if os.path.basename(str(data.get("source", ""))) != src_base:
            return False

        width = int(data.get("width", -1))
        height = int(data.get("height", -1))
        scale_x = self.frame_w / width if width > 0 else 1.0
        scale_y = self.frame_h / height if height > 0 else 1.0

        lanes = data.get("lanes", [])
        if not isinstance(lanes, list) or len(lanes) < 1:
            return False

        # Update global lane config to match calibration file
        loaded_names: list[str] = [str(l.get("name", "")) for l in lanes]
        if any(not n for n in loaded_names):
            return False

        config.LANE_COUNT = len(loaded_names)
        config.LANE_NAMES = loaded_names
        self.lane_names = list(config.LANE_NAMES)
        self.lane_count = config.LANE_COUNT

        polys: dict[str, np.ndarray] = {}
        areas: dict[str, float] = {}
        centroid_x: dict[str, float] = {}
        centroid_y: dict[str, float] = {}

        for idx, lane_entry in enumerate(lanes):
            name = loaded_names[idx]
            pts = lane_entry.get("polygon", [])
            if not isinstance(pts, list) or len(pts) < 3:
                continue

            poly = np.array(pts, dtype=np.float32)
            poly[:, 0] *= scale_x
            poly[:, 1] *= scale_y
            poly = poly.astype(np.int32)
            
            polys[name] = poly
            areas[name] = float(cv2.contourArea(poly))

            M = cv2.moments(poly)
            if M.get("m00", 0) != 0:
                centroid_x[name] = float(M["m10"] / M["m00"])
                centroid_y[name] = float(M["m01"] / M["m00"])
            else:
                centroid_x[name] = float(np.mean(poly[:, 0]))
                centroid_y[name] = float(np.mean(poly[:, 1]))

        self._polygons = polys
        self._areas = areas
        self._lane_centroid_x = centroid_x
        self._lane_centroid_y = centroid_y

        print(f"[LaneManager] Loaded calibration for {src_base}: {len(polys)} lanes")
        print("Loaded lanes:", list(self._polygons.keys()))
        return True

    def _build_polygons(self) -> None:
        self._polygons = {}
        self._areas = {}
        self._lane_centroid_x = {}
        self._lane_centroid_y = {}

        if self._try_load_calibration():
            return

        # Fallback: equal vertical strips across full frame height
        W = int(self.frame_w)
        H = int(self.frame_h)
        N = max(1, int(self.lane_count))

        boundaries = [int(round(i * W / N)) for i in range(N + 1)]
        boundaries[0] = 0
        boundaries[-1] = W

        # Full-frame strips when calibration is absent
        y_top = 0
        y_bottom = H

        # Build rectangles per lane
        for i, name in enumerate(self.lane_names):
            if i + 1 >= len(boundaries):
                break
            x1 = boundaries[i]
            x2 = boundaries[i + 1]
            poly = np.array(
                [[x1, y_top], [x2, y_top], [x2, y_bottom], [x1, y_bottom]],
                dtype=np.int32,
            )
            self._polygons[name] = poly
            self._areas[name] = float(cv2.contourArea(poly))

            M = cv2.moments(poly)
            if M.get("m00", 0) != 0:
                self._lane_centroid_x[name] = float(M["m10"] / M["m00"])
                self._lane_centroid_y[name] = float(M["m01"] / M["m00"])
            else:
                self._lane_centroid_x[name] = float(x1 + (x2 - x1) / 2.0)
                self._lane_centroid_y[name] = float(y_top + (y_bottom - y_top) / 2.0)

    def get_polygons(self) -> dict:
        return self._polygons

    def get_lane_area(self, name: str) -> float:
        return self._areas.get(name, 1.0)

    def _find_lane(self, det) -> Optional[str]:
        # Compute centroid using bounding box if available
        x1 = getattr(det, "x1", None)
        y1 = getattr(det, "y1", None)
        x2 = getattr(det, "x2", None)
        y2 = getattr(det, "y2", None)
        
        if x1 is not None and x2 is not None and y1 is not None and y2 is not None:
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
        else:
            cx = int(getattr(det, "cx", 0))
            cy = int(getattr(det, "cy", 0))

        MAX_FALLBACK_DISTANCE = 99999  # pixels — tunable threshold

        assigned_lane = None

        # Check membership using pointPolygonTest
        for ln, poly in self._polygons.items():
            if cv2.pointPolygonTest(poly, (float(cx), float(cy)), False) >= 0:
                assigned_lane = ln
                break

        # Strong fallback using Euclidean distance to polygon centroids
        if assigned_lane is None and self._lane_centroid_y and self._polygons:
            import math
            distances = {
                ln: math.hypot(float(cx) - self._lane_centroid_x[ln],
                               float(cy) - self._lane_centroid_y[ln])
                for ln in self._polygons
            }
            if distances:
                nearest = min(distances, key=distances.get)
                min_dist = distances[nearest]
                if min_dist <= MAX_FALLBACK_DISTANCE:
                    assigned_lane = nearest

        return assigned_lane

    def _nearest_lane_by_cx(self, cx: float) -> Optional[str]:
        if not self._lane_centroid_x:
            return None
        return min(self._lane_centroid_x.keys(), key=lambda ln: abs(cx - self._lane_centroid_x[ln]))

    def assign_lanes(self, detections: list) -> dict:
        lane_map = {name: [] for name in self.lane_names}

        for det in detections:
            lane = self._find_lane(det)
            
            det.lane = lane
            if lane and lane in lane_map:
                lane_map[lane].append(det)

        return lane_map

    def draw_lanes(self, frame: np.ndarray, signal_states: dict) -> np.ndarray:
        """Thin lane outlines only (no heavy fills)."""
        for name, poly in self._polygons.items():
            state = signal_states.get(name, "red")
            base_color = self.colors.get(name, (180, 180, 180))
            border = (0, 255, 80) if state == "green" else base_color
            thick = 2 if state == "green" else 1
            cv2.polylines(frame, [poly], isClosed=True, color=border, thickness=thick, lineType=cv2.LINE_AA)
            M = cv2.moments(poly)
            if M.get("m00", 0) != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                self._draw_lane_label(frame, name, cx, cy - 20, base_color)
        return frame

    @staticmethod
    def _draw_lane_label(frame, text, cx, cy, color):
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.55
        thick = 1
        (tw, th), _ = cv2.getTextSize(text, font, scale, thick)
        cv2.rectangle(frame, (cx - tw // 2 - 4, cy - th - 4), (cx + tw // 2 + 4, cy + 4), (0, 0, 0), -1)
        cv2.putText(frame, text, (cx - tw // 2, cy), font, scale, color, thick, cv2.LINE_AA)

    def get_signal_states(self, active_lane: str) -> dict:
        return {name: "green" if name == active_lane else "red" for name in self.lane_names}

