"""
main.py — Pragati AI Smart Traffic Management System
─────────────────────────────────────────────────────
Usage:
  python main.py --source indian_traffic.mp4
  python main.py --source indian_traffic.mp4 --lanes 2
  python main.py --source 0                         (webcam)
  python main.py --source traffic.mp4 --no-display  (headless)
  python main.py --source traffic.mp4 --model yolov8x.pt
"""

from __future__ import annotations

import argparse
import sys
import time
import os

import cv2

import config
from config import FLASK_HOST, FLASK_PORT, MJPEG_QUALITY
from modules.vehicle_detector import VehicleDetector
from modules.tracker import MotionTracker
from modules.lane_manager import LaneManager
from modules.traffic_analyzer import TrafficAnalyzer
from modules.signal_controller import SignalController
from modules.predictor import CongestionPredictor
from modules.video_renderer import VideoRenderer
from modules.behaviour_detector import BehaviourDetector
from modules.risk_predictor import RiskPredictor
from backend.server import run_server, update_state


def _make_pipeline():
    """Build objects that depend on config.LANE_NAMES (after lane detection)."""
    return (
        TrafficAnalyzer(),
        CongestionPredictor(),
        SignalController(),
        BehaviourDetector(config.LANE_NAMES),
        RiskPredictor(config.LANE_NAMES),
    )


# ─────────────────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pragati AI — Smart Traffic System")
    p.add_argument("--source", default=config.VIDEO_SOURCE,
                   help="Video file path, webcam index, or RTSP URL")
    p.add_argument("--model", default=None,
                   help="Override YOLO model (e.g. yolov8x.pt)")
    p.add_argument("--lanes", type=int, default=config.LANE_COUNT,
                   help="Fallback lane strips if Hough fails (1–8)")
    p.add_argument("--port", type=int, default=FLASK_PORT,
                   help=f"Flask dashboard port (default: {FLASK_PORT})")
    p.add_argument("--no-display", action="store_true",
                   help="Disable cv2.imshow popup window")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    return p.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    args = parse_args()

    if args.model:
        config.MODEL_PATH = args.model

    if args.lanes and args.lanes != config.LANE_COUNT:
        config.LANE_COUNT = args.lanes
        config.LANE_NAMES = config.get_lane_names(args.lanes)
        print(f"[Main] Fallback lane count set to {args.lanes}: {config.LANE_NAMES}")

    config.VIDEO_SOURCE = args.source

    # Warn if calibration file is missing; system still runs with equal strips.
    try:
        src_str = str(args.source)
        if not src_str.isdigit():
            src_base = os.path.basename(src_str)
            stem = os.path.splitext(src_base)[0]
            calib_name = f"lane_config_{stem}.json"
            calib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), calib_name)
            if not os.path.isfile(calib_path):
                print(f"[Main] No calibration found. Run: python calibrate_lanes.py --source {src_base}")
    except Exception:
        pass

    src: int | str = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open source: {args.source}")
        sys.exit(1)

    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    source_fps = float(cap.get(cv2.CAP_PROP_FPS))
    if source_fps <= 1.0 or source_fps != source_fps:
        source_fps = float(config.TARGET_FPS)
    frame_interval_s = 1.0 / max(1.0, source_fps)
    if args.width and args.height:
        W, H = args.width, args.height

    ret0, first = cap.read()
    if not ret0:
        print("[ERROR] Cannot read first frame")
        sys.exit(1)
    if args.width and args.height:
        first = cv2.resize(first, (W, H))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    lane_mgr = LaneManager()
    lane_mgr.set_frame_size(W, H)
    lane_mgr.initialize_from_frame(first)
    lane_polys = lane_mgr.get_polygons()

    detector = VehicleDetector()
    mot_tracker = MotionTracker()
    analyzer, predictor, controller, behaviour_det, risk_pred = _make_pipeline()
    renderer = VideoRenderer()
    prev_green = ""
    prev_behaviour_events: list = []
    last_detections: list = []

    print(f"[Main] Source: {args.source}  Resolution: {W}×{H}")
    print(f"[Main] Lanes: {config.LANE_COUNT} -> {config.LANE_NAMES}")
    print(f"[Main] Source FPS: {source_fps:.1f} | Realtime mode: {getattr(config, 'REALTIME_MODE', False)}")

    run_server(host=FLASK_HOST, port=args.port)

    fps = 0.0
    frame_count = 0
    fps_start = time.time()
    current_source = config.VIDEO_SOURCE

    print("[Main] Starting processing loop. Press Q to quit.")

    while cap.isOpened():
        loop_t0 = time.perf_counter()

        if config.VIDEO_SOURCE != current_source:
            print(f"[Main] Source changed to: {config.VIDEO_SOURCE}")
            cap.release()
            new_src = config.VIDEO_SOURCE
            src = int(new_src) if str(new_src).isdigit() else new_src
            cap = cv2.VideoCapture(src)
            if not cap.isOpened():
                print(f"[Main] Cannot open new source: {new_src}, reverting")
                cap = cv2.VideoCapture(current_source)
            else:
                current_source = config.VIDEO_SOURCE
                W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if args.width and args.height:
                    W, H = args.width, args.height
                lane_mgr.set_frame_size(W, H)
                r2, fr0 = cap.read()
                if r2:
                    if args.width and args.height:
                        fr0 = cv2.resize(fr0, (W, H))
                    lane_mgr.initialize_from_frame(fr0)
                lane_polys = lane_mgr.get_polygons()
                analyzer, predictor, controller, behaviour_det, risk_pred = _make_pipeline()
                prev_green = ""
                prev_behaviour_events = []
                frame_count = 0
            continue

        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        frame_count += 1

        if args.width and args.height:
            frame = cv2.resize(frame, (W, H))

        detect_every = max(1, int(getattr(config, "DETECT_EVERY_N_FRAMES", 1)))
        run_detection = (frame_count % detect_every == 0) or (not last_detections)

        if run_detection:
            infer_scale = float(getattr(config, "INFER_SCALE", 1.0))
            if 0.1 < infer_scale < 0.99:
                sw = max(1, int(W * infer_scale))
                sh = max(1, int(H * infer_scale))
                infer_frame = cv2.resize(frame, (sw, sh))
            else:
                infer_frame = frame
                sw, sh = W, H

            detections = detector.detect(infer_frame)

            # Map detections back to display resolution if inference was scaled.
            if infer_frame is not frame and detections:
                sx = W / max(1.0, float(sw))
                sy = H / max(1.0, float(sh))
                for d in detections:
                    d.x1 = int(d.x1 * sx)
                    d.x2 = int(d.x2 * sx)
                    d.y1 = int(d.y1 * sy)
                    d.y2 = int(d.y2 * sy)
                    d.cx = int(d.cx * sx)
                    d.cy = int(d.cy * sy)
                    d.area = max(0, (d.x2 - d.x1) * (d.y2 - d.y1))

            detections = mot_tracker.update(detections)
            last_detections = detections
        else:
            detections = last_detections

        detection_ok = len(detections) > 0

        per_lane = lane_mgr.assign_lanes(detections)

        signal_for_analyzer = controller._active
        lane_stats = analyzer.update(per_lane, signal_for_analyzer)

        predicted_pressures = predictor.update(lane_stats)
        trends = {ln: predictor.trend_direction(ln) for ln in config.LANE_NAMES}
        history = {ln: predictor.get_history(ln) for ln in config.LANE_NAMES}
        prediction_data = {ln: predictor.get_prediction_data(ln) for ln in config.LANE_NAMES}

        signal_status = controller.update(
            lane_stats,
            detection_ok,
            predicted_pressures,
            behaviour_events=prev_behaviour_events,
            frame=frame,
        )

        green_changed = signal_status.active_lane != prev_green
        prev_green = signal_status.active_lane

        behaviour_events = behaviour_det.update(
            detections,
            per_lane,
            lane_stats,
            signal_status.active_lane,
            green_changed,
        )
        prev_behaviour_events = behaviour_events

        for ln, stats in lane_stats.items():
            pressure = getattr(stats, "pressure", 0.0)
            risk_pred.update_pressure(ln, pressure)

        risk_pred.add_events(behaviour_events)
        risks = risk_pred.compute_risks()

        annotated = renderer.render(
            frame, detections, lane_polys,
            lane_stats, signal_status,
            predicted_pressures, trends,
            behaviour_events=behaviour_events,
            risks=risks,
            prediction_data=prediction_data,
        )

        ok, jpg_buf = cv2.imencode(
            ".jpg", annotated,
            [cv2.IMWRITE_JPEG_QUALITY, MJPEG_QUALITY],
        )
        if ok:
            behaviour_dicts = [e.to_dict() for e in behaviour_det.get_recent_events(30)]
            risk_dicts = {ln: r.to_dict() for ln, r in risks.items()}
            policy_breakdown = behaviour_det.get_policy_breakdown(60)

            update_state(
                frame_jpg=jpg_buf.tobytes(),
                lane_stats=lane_stats,
                signal_status=signal_status,
                history=history,
                predicted=predicted_pressures,
                trends=trends,
                fps=fps,
                frame_count=frame_count,
                behaviours=behaviour_dicts,
                risks=risk_dicts,
                policy_breakdown=policy_breakdown,
                prediction_data=prediction_data,
            )

        if not args.no_display:
            cv2.imshow("Pragati AI — Smart Traffic", annotated)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                break

        if frame_count % 30 == 0:
            elapsed = time.time() - fps_start
            fps = 30.0 / max(elapsed, 0.01)
            fps_start = time.time()

        # Adaptive frame skipping keeps playback near normal source speed.
        if getattr(config, "REALTIME_MODE", False) and not str(args.source).isdigit():
            proc_s = time.perf_counter() - loop_t0
            if proc_s > frame_interval_s:
                lag_frames = int(proc_s / frame_interval_s) - 1
                max_skip = max(0, int(getattr(config, "MAX_SKIPPED_FRAMES", 0)))
                to_skip = max(0, min(max_skip, lag_frames))
                for _ in range(to_skip):
                    if not cap.grab():
                        break

    cap.release()
    cv2.destroyAllWindows()
    print("[Main] Stopped.")


if __name__ == "__main__":
    main()
