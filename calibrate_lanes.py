"""
calibrate_lanes.py — 2-point smart lane calibration

Flow:
  1) User clicks LEFT road edge and RIGHT road edge on first frame.
  2) Tool previews LANE_COUNT equal vertical lane strips.
  3) Press Y to save, R to redo.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import cv2
import numpy as np

import config


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Calibrate lane polygons from the first frame")
    p.add_argument("--source", required=True, help="Video file path (e.g. intersection.mp4)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    src = args.source
    src_name = os.path.basename(src)
    stem = os.path.splitext(src_name)[0]

    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open source: {src}")
        sys.exit(1)

    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        print("[ERROR] Cannot read first frame")
        sys.exit(1)

    H, W = frame.shape[:2]
    y_top = (H * 30) // 100
    y_bottom = H

    lane_count = max(1, int(config.LANE_COUNT))
    left_pt = None  # (x,y)
    right_pt = None  # (x,y)

    window = "Road Boundary Selection"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    lane_colors = [
        (0, 255, 255),
        (0, 200, 100),
        (255, 128, 0),
        (200, 100, 255),
        (0, 165, 255),
        (255, 80, 80),
        (120, 255, 120),
        (180, 180, 255),
    ]

    def lane_names(n: int) -> list[str]:
        return config.get_lane_names(n)

    def preview_polygons(n: int) -> list[list[list[int]]]:
        if left_pt is None or right_pt is None:
            return []
        x1 = int(left_pt[0])
        x2 = int(right_pt[0])
        if x2 < x1:
            x1, x2 = x2, x1

        span = max(1, x2 - x1)
        bounds = [int(round(x1 + i * span / n)) for i in range(n + 1)]
        bounds[0] = x1
        bounds[-1] = x2

        polys = []
        for i in range(n):
            lx = bounds[i]
            rx = bounds[i + 1]
            polys.append([[lx, y_top], [rx, y_top], [rx, y_bottom], [lx, y_bottom]])
        return polys

    def redraw() -> np.ndarray:
        vis = frame.copy()

        instruction = "Click LEFT edge, then RIGHT edge. Y=confirm/save, R=redo."
        cv2.putText(vis, instruction, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(vis, instruction, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        if left_pt is not None:
            cv2.circle(vis, (int(left_pt[0]), int(left_pt[1])), 6, (0, 255, 0), -1, cv2.LINE_AA)
            cv2.putText(vis, "LEFT", (int(left_pt[0]) + 8, int(left_pt[1]) + 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
        if right_pt is not None:
            cv2.circle(vis, (int(right_pt[0]), int(right_pt[1])), 6, (0, 0, 255), -1, cv2.LINE_AA)
            cv2.putText(vis, "RIGHT", (int(right_pt[0]) + 8, int(right_pt[1]) + 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)

        polys = preview_polygons(lane_count)
        if polys:
            names = lane_names(lane_count)
            for i, poly in enumerate(polys):
                pts = np.array(poly, dtype=np.int32)
                col = lane_colors[i % len(lane_colors)]
                cv2.polylines(vis, [pts], True, col, 2, cv2.LINE_AA)
                cx = int((poly[0][0] + poly[2][0]) / 2)
                cy = int((poly[0][1] + poly[2][1]) / 2)
                label = names[i] if i < len(names) else f"LANE_{i+1}"
                cv2.putText(vis, label, (cx - 35, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2, cv2.LINE_AA)

        hint2 = f"Lanes: {lane_count} | Y save | R redo | ESC exit"
        cv2.putText(vis, hint2, (10, H - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        return vis

    def on_mouse(event, x, y, flags, param) -> None:
        nonlocal left_pt, right_pt
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        if left_pt is None:
            left_pt = (x, y)
            return
        if right_pt is None:
            right_pt = (x, y)
            return

        # If both are set, overwrite (keeps UX simple)
        left_pt = (x, y)
        right_pt = None

    cv2.setMouseCallback(window, on_mouse)

    while True:
        cv2.imshow(window, redraw())
        k = cv2.waitKey(30) & 0xFF

        if k == 27:  # ESC
            break

        # redo
        if k in (ord("r"), ord("R")):
            left_pt = None
            right_pt = None
            continue

        # save
        if k in (ord("y"), ord("Y")):
            if left_pt is None or right_pt is None:
                continue

            polys = preview_polygons(lane_count)
            names = lane_names(lane_count)

            lanes = []
            for i, poly in enumerate(polys):
                nm = names[i] if i < len(names) else f"LANE_{i+1}"
                lanes.append({"name": nm, "polygon": poly})

            out = {
                "source": src_name,
                "width": int(W),
                "height": int(H),
                "lanes": lanes,
            }

            out_name = f"lane_config_{stem}.json"
            out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), out_name)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2)

            print(f"Saved to {out_name}")
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

