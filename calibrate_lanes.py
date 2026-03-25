import argparse
import json
import os
import sys

import cv2
import numpy as np

import config

def get_args():
    parser = argparse.ArgumentParser(description="Calibrate lane polygons for Pragati AI.")
    parser.add_argument("--source", type=str, required=True, help="Path to the video file to calibrate.")
    return parser.parse_args()

def main():
    args = get_args()
    source_path = args.source
    
    if not os.path.isfile(source_path):
        print(f"Error: Video file '{source_path}' not found.")
        sys.exit(1)
        
    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        print(f"Error: Could not open video '{source_path}'.")
        sys.exit(1)
        
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        print("Error: Could not read the first frame.")
        sys.exit(1)
        
    frame_h, frame_w = frame.shape[:2]
    
    lane_count = config.LANE_COUNT
    lane_names = config.LANE_NAMES
    
    print(f"Calibrating {lane_count} lanes for {source_path}")
    print("Controls:")
    print("  - Click: Add polygon point")
    print("  - 'n': Next lane (or finish)")
    print("  - 'u': Undo last point")
    print("  - 's': Save and exit")
    print("  - 'q': Quit without saving")
    
    current_lane_idx = 0
    polygons = [[] for _ in range(lane_count)]
    
    window_name = "Lane Calibration"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    
    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            if current_lane_idx < lane_count:
                polygons[current_lane_idx].append([x, y])
                
    cv2.setMouseCallback(window_name, mouse_callback)
    
    while True:
        display = frame.copy()
        
        # Draw completed polygons
        for i, poly in enumerate(polygons):
            if not poly:
                continue
            
            color = config.LANE_COLORS_MAP.get(lane_names[i], (0, 255, 0))
            pts = np.array(poly, np.int32)
            
            if i < current_lane_idx:
                # Completed lane
                cv2.polylines(display, [pts], True, color, 2)
            else:
                # Current lane being drawn
                cv2.polylines(display, [pts], False, color, 2)
                for pt in poly:
                    cv2.circle(display, tuple(pt), 4, color, -1)
                    
        # Add text overlay
        if current_lane_idx < lane_count:
            status_text = f"Drawing {lane_names[current_lane_idx]} ({len(polygons[current_lane_idx])} points)"
        else:
            status_text = "All lanes defined. Press 's' to save or 'u' to undo."
            
        cv2.putText(display, status_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        cv2.imshow(window_name, display)
        key = cv2.waitKey(20) & 0xFF
        
        if key == ord('q'):
            print("Quit without saving.")
            break
        elif key == ord('n'):
            if current_lane_idx < lane_count:
                if len(polygons[current_lane_idx]) < 3:
                    print(f"Warning: {lane_names[current_lane_idx]} needs at least 3 points.")
                else:
                    current_lane_idx += 1
        elif key == ord('u'):
            if current_lane_idx < lane_count and len(polygons[current_lane_idx]) > 0:
                polygons[current_lane_idx].pop()
            elif current_lane_idx > 0 and (current_lane_idx >= lane_count or len(polygons[current_lane_idx]) == 0):
                current_lane_idx -= 1
                if len(polygons[current_lane_idx]) > 0:
                    polygons[current_lane_idx].pop()
        elif key == ord('s'):
            # Validate and keep only lanes with >= 3 points
            valid_polygons = []
            valid_names = []
            for i, poly in enumerate(polygons):
                if len(poly) >= 3:
                    valid_polygons.append(poly)
                    valid_names.append(lane_names[i])
                elif len(poly) > 0:
                    print(f"Warning: {lane_names[i]} has {len(poly)} points (needs 3+), skipping.")
            
            if not valid_polygons:
                print("Error: No valid lanes to save.")
                continue
                
            # Basic overlap check using masks
            overlap = False
            masks = []
            for poly in valid_polygons:
                mask = np.zeros((frame_h, frame_w), dtype=np.uint8)
                pts = np.array(poly, np.int32)
                cv2.fillPoly(mask, [pts], 255)
                masks.append(mask)
                
            for i in range(len(masks)):
                for j in range(i + 1, len(masks)):
                    intersection = cv2.bitwise_and(masks[i], masks[j])
                    if cv2.countNonZero(intersection) > 0:
                        overlap = True
                        print(f"Warning: {valid_names[i]} and {valid_names[j]} overlap!")
                        
            if overlap:
                print("Please fix the overlapping lanes before saving. (Press 'u' to undo)")
                continue
                
            # Save JSON
            stem = os.path.splitext(os.path.basename(source_path))[0]
            out_filename = f"lane_config_{stem}.json"
            out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), out_filename)
            
            lanes_data = []
            for i, poly in enumerate(valid_polygons):
                lanes_data.append({
                    "name": valid_names[i],
                    "polygon": poly
                })
                
            output_data = {
                "source": os.path.basename(source_path),
                "width": frame_w,
                "height": frame_h,
                "lanes": lanes_data
            }
            
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2)
                
            print(f"Successfully saved {len(valid_polygons)} lanes to {out_path}")
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()