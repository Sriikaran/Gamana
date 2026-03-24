"""
config.py — Central configuration for Pragati AI Smart Traffic System.
Edit this file to change behaviour without touching any other code.
"""

import numpy as np

# ─── VIDEO SOURCE ─────────────────────────────────────────────────────────────
VIDEO_SOURCE  = "indian_traffic.mp4"   # default video (overridden by upload)
FRAME_WIDTH   = 1280
FRAME_HEIGHT  = 720
TARGET_FPS    = 25
MJPEG_QUALITY = 75

# ─── REAL-TIME PERFORMANCE ───────────────────────────────────────────────────
# Keeps output near normal video speed on heavier models/videos.
REALTIME_MODE = True
INFER_SCALE = 0.75            # YOLO inference scale (0.5-1.0)
DETECT_EVERY_N_FRAMES = 2     # run detector every N frames, reuse tracks between
MAX_SKIPPED_FRAMES = 4        # adaptive skip when processing lags source FPS

# ─── LANE CONFIGURATION ───────────────────────────────────────────────────────
# Fixed 4-lane intersection (LEFT, LEFT_CENTER, RIGHT_CENTER, RIGHT)
LANE_COUNT = 4

# Lane names auto-generated based on LANE_COUNT:
#   2 lanes → ["LEFT", "RIGHT"]
#   3 lanes → ["LEFT", "CENTER", "RIGHT"]
#   4 lanes → ["LEFT", "LEFT_CENTER", "RIGHT_CENTER", "RIGHT"]
def get_lane_names(count: int) -> list:
    if count == 2:
        return ["LEFT", "RIGHT"]
    elif count == 3:
        return ["LEFT", "CENTER", "RIGHT"]
    elif count == 4:
        return ["LEFT", "LEFT_CENTER", "RIGHT_CENTER", "RIGHT"]
    else:
        return [f"LANE_{i+1}" for i in range(count)]

LANE_NAMES = get_lane_names(LANE_COUNT)

LANE_COLORS_MAP = {
    "LEFT":         (255, 200,  50),
    "LEFT_CENTER":  ( 50, 200, 255),
    "CENTER":       (100, 255, 100),
    "RIGHT_CENTER": (200, 255,  50),
    "RIGHT":        (255,  50, 200),
    "LANE_1":       (255, 200,  50),
    "LANE_2":       ( 50, 200, 255),
    "LANE_3":       (200, 255,  50),
    "LANE_4":       (255,  50, 200),
    "LANE_5":       (255, 150, 100),
}

# ─── MODEL ────────────────────────────────────────────────────────────────────
MODEL_PATH  = "yolov8n.pt"
CONF_THRESH = 0.30
IOU_THRESH  = 0.45
DEVICE      = "cuda"          # "cuda" | "cpu"
TRACKER_CFG = "botsort.yaml"

# COCO class IDs we care about
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
    1: "bicycle",
    0: "person",
}

# ─── VEHICLE WEIGHTS (congestion scoring) ────────────────────────────────────
VEHICLE_WEIGHTS = {
    "car":        1.0,
    "motorcycle": 0.5,
    "auto":       1.2,
    "bus":        3.0,
    "truck":      3.5,
    "bicycle":    0.3,
    "person":     0.2,
    "ambulance":  0.0,
}

# ─── AUTO-RICKSHAW HEURISTIC ──────────────────────────────────────────────────
AUTO_ASPECT_RATIO_MAX = 0.85
AUTO_AREA_MAX         = 12000

# ─── AMBULANCE DETECTION ──────────────────────────────────────────────────────
AMBULANCE_RED_RATIO_MIN = 0.30

# ─── TRACKING / MOTION ───────────────────────────────────────────────────────
MOVEMENT_THRESHOLD_PX = 8
STOPPED_FRAMES_WINDOW = 15
HISTORY_MAX_FRAMES    = 30

# ─── CONGESTION SCORING ──────────────────────────────────────────────────────
STOPPED_PENALTY_MULTIPLIER = 1.8
MAX_WAIT_BONUS             = 30
FLOW_RATE_DISCOUNT         = 0.15
LANE_AREA_NORMALIZE        = True

# ─── SIGNAL CONTROLLER ───────────────────────────────────────────────────────
MIN_GREEN_SECONDS   = 12
MAX_GREEN_SECONDS   = 60
COOLDOWN_SECONDS    = 4
SWITCH_DELTA_THRESH = 15
FAILSAFE_GREEN_SECONDS = 20  # fixed green per lane in FAILSAFE rotation

GREEN_TIME_LOW    = 12
GREEN_TIME_MEDIUM = 25
GREEN_TIME_HIGH   = 45
GREEN_TIME_PEAK   = 60

# ─── FLASK / SERVER ───────────────────────────────────────────────────────────
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000

# ─── UPLOAD ───────────────────────────────────────────────────────────────────
UPLOAD_FOLDER   = "uploads"
ALLOWED_EXTENSIONS = {"mp4", "avi", "mov", "mkv", "webm"}

# ─── BACKWARD-COMPATIBLE ALIASES ─────────────────────────────────────────────
# These map the old constant names (used by vehicle_detector, tracker,
# traffic_analyzer, signal_controller, predictor, video_renderer) to their
# new equivalents so those modules need not be changed.

# vehicle_detector.py
TRACKER            = TRACKER_CFG
CONF_THRESHOLD     = CONF_THRESH
IOU_THRESHOLD      = IOU_THRESH
INFERENCE_IMGSZ    = 1280
COCO_CLASS_MAP     = VEHICLE_CLASSES
TRACK_CLASSES      = set(VEHICLE_CLASSES.keys())
AUTO_ASPECT_RATIO_MIN  = 0.75
AUTO_ASPECT_RATIO_MAX  = AUTO_ASPECT_RATIO_MAX   # already defined above
AUTO_MAX_AREA_PX       = AUTO_AREA_MAX
AMBULANCE_MIN_AREA     = 5000
AMBULANCE_BRIGHTNESS_TH = 160

# tracker.py
MOTION_HISTORY_LEN = HISTORY_MAX_FRAMES
STOPPED_THRESHOLD  = MOVEMENT_THRESHOLD_PX
MOTION_FRAMES_MIN  = 3

# traffic_analyzer.py
STOPPED_PENALTY      = STOPPED_PENALTY_MULTIPLIER
MOVING_MULTIPLIER    = 1.0
WAITING_TIME_WEIGHT  = 0.05
CONGESTION_LOW_MAX   = 30.0
CONGESTION_HIGH_MIN  = 65.0

# signal_controller.py
MIN_GREEN_TIME   = MIN_GREEN_SECONDS
MAX_GREEN_TIME   = MAX_GREEN_SECONDS
COOLDOWN_TIME    = COOLDOWN_SECONDS
GREEN_LOW_TIME   = GREEN_TIME_LOW
GREEN_MED_TIME   = GREEN_TIME_MEDIUM
GREEN_HIGH_TIME  = GREEN_TIME_HIGH
SWITCH_THRESHOLD = SWITCH_DELTA_THRESH
FAILSAFE_GREEN_TIME = FAILSAFE_GREEN_SECONDS

# predictor.py
HISTORY_LEN          = 60
PREDICTION_LOOKAHEAD = 10
SPIKE_THRESHOLD      = 15.0

# video_renderer.py
LANE_COLORS   = LANE_COLORS_MAP
FONT          = 0   # cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE_SM = 0.45
FONT_SCALE_MD = 0.60
FONT_SCALE_LG = 0.75
FONT_THICKNESS = 1
BOX_THICKNESS  = 2
VEHICLE_COLORS = {
    "car":        (100, 220, 255),
    "motorcycle": (255, 200,  50),
    "auto":       (255, 100, 200),
    "bus":        ( 50, 100, 255),
    "truck":      (255,  50,  50),
    "bicycle":    (100, 255, 150),
    "person":     (200, 200, 200),
    "unknown":    (180, 180, 180),
}