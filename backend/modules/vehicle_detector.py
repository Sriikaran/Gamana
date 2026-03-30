"""
vehicle_detector.py
────────────────────
YOLOv8-based vehicle detection with Indian road adaptations.
Handles COCO-class remapping and auto-rickshaw heuristic detection.
"""

from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional

from config import (
    MODEL_PATH, TRACKER, CONF_THRESHOLD, IOU_THRESHOLD, INFERENCE_IMGSZ,
    COCO_CLASS_MAP, TRACK_CLASSES,
    AUTO_ASPECT_RATIO_MIN, AUTO_ASPECT_RATIO_MAX, AUTO_MAX_AREA_PX,
    AMBULANCE_MIN_AREA, AMBULANCE_BRIGHTNESS_TH, DEVICE,
)


# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Detection:
    track_id:   int
    raw_class:  int         # COCO class id
    label:      str         # internal label (car / motorcycle / auto / …)
    confidence: float
    x1:         int
    y1:         int
    x2:         int
    y2:         int
    cx:         int         # centre-x
    cy:         int         # centre-y
    area:       int
    is_ambulance: bool = False
    is_moving:  bool = False   # filled by tracker


# ─────────────────────────────────────────────────────────────────────────────
class VehicleDetector:
    """
    Wraps Ultralytics YOLO with BOT-SORT / ByteTrack tracking.
    Returns a list of Detection objects per frame.
    """

    def __init__(self):
        from ultralytics import YOLO          # lazy import — avoids slow startup
        import torch
        self.model = YOLO(MODEL_PATH)
        requested = str(DEVICE).lower()
        if requested.startswith("cuda") and not torch.cuda.is_available():
            print("[Detector] CUDA requested but unavailable in current torch build. Falling back to CPU.")
            self._device = "cpu"
        else:
            self._device = requested
        print(f"[Detector] Loaded model: {MODEL_PATH} on {self._device}")

    # ── Public API ────────────────────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Run inference + tracking on one frame. Returns list of Detection."""
        results = self.model.track(
            frame,
            persist=True,
            tracker=TRACKER,
            conf=CONF_THRESHOLD,
            iou=IOU_THRESHOLD,
            imgsz=INFERENCE_IMGSZ,
            device=self._device,
            half=self._device.startswith("cuda"),
            verbose=False,
            classes=list(TRACK_CLASSES),   # filter coco classes at model level
        )

        detections: List[Detection] = []
        boxes = results[0].boxes

        if boxes is None or boxes.id is None:
            return detections

        ids      = boxes.id.int().tolist()
        classes  = boxes.cls.int().tolist()
        confs    = boxes.conf.float().tolist()
        xyxy     = boxes.xyxy.cpu().numpy().astype(int)

        for i, track_id in enumerate(ids):
            raw_cls = classes[i]
            if raw_cls not in COCO_CLASS_MAP:
                continue

            x1, y1, x2, y2 = xyxy[i]
            cx   = (x1 + x2) // 2
            cy   = (y1 + y2) // 2
            area = (x2 - x1) * (y2 - y1)
            conf = round(confs[i], 3)

            label = self._classify(raw_cls, x1, y1, x2, y2, area)
            if label is None:
                continue

            red_ratio = self._ambulance_red_ratio(frame, x1, y1, x2, y2)
            amb = self._check_ambulance(frame, x1, y1, x2, y2, area) or (red_ratio >= 0.12)
            if amb:
                label = "ambulance"

            detections.append(Detection(
                track_id   = track_id,
                raw_class  = raw_cls,
                label      = label,
                confidence = conf,
                x1=x1, y1=y1, x2=x2, y2=y2,
                cx=cx, cy=cy,
                area=area,
                is_ambulance=amb,
            ))

        return detections

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _classify(self, cls: int, x1: int, y1: int, x2: int, y2: int,
                  area: int) -> Optional[str]:
        """
        Map COCO class → internal label.
        Includes auto-rickshaw heuristic for class 2 (car) detections.
        """
        w   = x2 - x1
        h   = y2 - y1 + 1e-6
        ratio = w / h

        if cls == 1:
            return "bicycle"

        if cls == 3:
            return "motorcycle"

        if cls == 5:
            return "bus"

        if cls == 7:
            return "truck"

        if cls == 2:
            # ── Auto-rickshaw heuristic ──
            # Auto-rickshaws are roughly square/slightly wide, and smaller
            # than a typical car in an overhead/angled camera view.
            if (AUTO_ASPECT_RATIO_MIN <= ratio <= AUTO_ASPECT_RATIO_MAX
                    and area <= AUTO_MAX_AREA_PX):
                return "auto"
            return "car"

        if cls == 0:
            return "person"

        return None

    def _check_ambulance(self, frame: np.ndarray,
                         x1: int, y1: int, x2: int, y2: int,
                         area: int) -> bool:
        """
        Lightweight ambulance heuristic:
        - Bounding box area > minimum
        - ROI mean brightness > threshold (ambulances are white/brightly lit)
        """
        if area < AMBULANCE_MIN_AREA:
            return False

        # Clamp ROI to frame bounds
        fh, fw = frame.shape[:2]
        ry1, ry2 = max(0, y1), min(fh, y2)
        rx1, rx2 = max(0, x1), min(fw, x2)

        roi = frame[ry1:ry2, rx1:rx2]
        if roi.size == 0:
            return False

        brightness = float(np.mean(roi))
        return brightness > AMBULANCE_BRIGHTNESS_TH

    @staticmethod
    def _ambulance_red_ratio(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> float:
        """Backup ambulance cue: fraction of red pixels in bbox (HSV)."""
        fh, fw = frame.shape[:2]
        ry1, ry2 = max(0, y1), min(fh, y2)
        rx1, rx2 = max(0, x1), min(fw, x2)
        roi = frame[ry1:ry2, rx1:rx2]
        if roi.size == 0:
            return 0.0
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        lower_red1 = np.array([0, 100, 80], dtype=np.uint8)
        upper_red1 = np.array([10, 255, 255], dtype=np.uint8)
        lower_red2 = np.array([160, 100, 80], dtype=np.uint8)
        upper_red2 = np.array([179, 255, 255], dtype=np.uint8)
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = cv2.bitwise_or(mask1, mask2)
        return float(np.count_nonzero(mask)) / float(mask.size)
