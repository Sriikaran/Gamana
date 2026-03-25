"""
backend/server.py
──────────────────
Flask API + MJPEG stream server for Pragati AI.

Routes:
  GET  /                  → dashboard (templates/index.html)
  GET  /video_feed        → MJPEG stream
  GET  /api/status        → system status JSON
  GET  /api/lanes         → lane stats + predictions JSON
  GET  /api/signals       → signal state JSON
  GET  /api/history       → pressure history JSON
  GET  /api/behaviours    → behaviour events + risk scores JSON
  POST /upload            → upload a video file to analyze
  POST /api/set_lanes     → change lane count at runtime
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict

from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS

_HERE         = os.path.dirname(os.path.abspath(__file__))
_TEMPLATE_DIR = os.path.normpath(os.path.join(_HERE, "..", "templates"))
_STATIC_DIR   = os.path.normpath(os.path.join(_HERE, "..", "static"))

app = Flask(
    __name__,
    template_folder=_TEMPLATE_DIR,
    static_folder=_STATIC_DIR,
)
CORS(app)

# ── Shared state ──────────────────────────────────────────────────────────────
_lock = threading.Lock()
_state: Dict[str, Any] = {
    "frame_jpg":       None,
    "lane_stats":      {},
    "signals":         {},
    "active_lane":     "",
    "signal_state":    "NORMAL",
    "time_remaining":  0.0,
    "green_duration":  20,
    "history":         {},
    "predicted":       {},
    "trends":          {},
    "fps":             0.0,
    "frame_count":     0,
    "uptime":          time.time(),
    "behaviours":      [],
    "risks":           {},
    "policy_breakdown":[],
    "prediction_data": {},
    "video_source":    "",
    "lane_count":      4,
    "lane_names":      [],
}

# ── Update function (called every frame from main loop) ───────────────────────

def update_state(
    frame_jpg,
    lane_stats,
    signal_status,
    history,
    predicted,
    trends,
    fps,
    frame_count,
    behaviours=None,
    risks=None,
    policy_breakdown=None,
    prediction_data=None,
) -> None:
    """Thread-safe state update. Called every frame from the main processing loop."""

    # Serialize lane stats — handle both dict-style and object-style
    lanes_serial = {}
    for ln, stats in lane_stats.items():
        if isinstance(stats, dict):
            lanes_serial[ln] = stats
        else:
            lanes_serial[ln] = {
                "total":            getattr(stats, "total",            0),
                "moving":           getattr(stats, "moving",           0),
                "stopped":          getattr(stats, "stopped",          0),
                "pressure":         round(getattr(stats, "pressure",   0.0), 2),
                "congestion_level": getattr(stats, "congestion_level", "LOW"),
                "emergency":        getattr(stats, "emergency",        False),
                "vehicle_counts":   getattr(stats, "vehicle_counts",   {}),
                "flow_rate":        round(getattr(stats, "flow_rate",  0.0), 3),
                "wait_time":        round(getattr(stats, "wait_time",  0.0), 1),
                "trend":            getattr(stats, "trend",            "stable"),
            }

    with _lock:
        _state["frame_jpg"]      = frame_jpg
        _state["lane_stats"]     = lanes_serial
        _state["signals"]        = getattr(signal_status, "signals", {})
        _state["active_lane"]    = getattr(signal_status, "active_lane", "")
        _state["signal_state"]   = getattr(signal_status, "state", "NORMAL")
        _state["time_remaining"] = round(getattr(signal_status, "time_remaining", 0.0), 1)
        _state["green_duration"] = getattr(signal_status, "green_duration", 20)
        _state["history"]        = history or {}
        _state["predicted"]      = {k: round(v, 2) for k, v in (predicted or {}).items()}
        _state["trends"]         = trends or {}
        _state["fps"]            = round(fps, 1)
        _state["frame_count"]    = frame_count

        if behaviours is not None:
            _state["behaviours"] = behaviours
        if risks is not None:
            _state["risks"] = risks
        if policy_breakdown is not None:
            _state["policy_breakdown"] = policy_breakdown
        if prediction_data is not None:
            _state["prediction_data"] = prediction_data

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video_feed")
def video_feed():
    def generate():
        while True:
            with _lock:
                jpg = _state["frame_jpg"]
            if jpg is None:
                time.sleep(0.05)
                continue
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
            )
            time.sleep(0.033)
    return Response(
        generate(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/api/status")
def api_status():
    with _lock:
        return jsonify({
            "status":        "running",
            "active_lane":   _state["active_lane"],
            "signal_state":  _state["signal_state"],
            "fps":           _state["fps"],
            "frame_count":   _state["frame_count"],
            "uptime_s":      round(time.time() - _state["uptime"], 1),
            "video_source":  _state["video_source"],
            "lane_count":    _state["lane_count"],
            "lane_names":    _state["lane_names"],
        })


@app.route("/api/lanes")
def api_lanes():
    with _lock:
        lanes_with_pred = {}
        for ln, stats in _state["lane_stats"].items():
            lane_data = dict(stats) if isinstance(stats, dict) else stats
            # Merge prediction data
            pd = _state.get("prediction_data", {}).get(ln, {})
            if isinstance(lane_data, dict):
                lane_data["predicted_pressure"] = pd.get("predicted_pressure", 0.0)
                lane_data["time_to_jam_seconds"] = pd.get("time_to_jam_seconds", 999.0)
                lane_data["jam_warning"] = pd.get("jam_warning", False)
            lanes_with_pred[ln] = lane_data
        return jsonify({
            "lanes":     lanes_with_pred,
            "predicted": _state["predicted"],
            "trends":    _state["trends"],
        })


@app.route("/api/signals")
def api_signals():
    with _lock:
        return jsonify({
            "signals":        _state["signals"],
            "active_lane":    _state["active_lane"],
            "state":          _state["signal_state"],
            "time_remaining": _state["time_remaining"],
            "green_duration": _state["green_duration"],
        })


@app.route("/api/history")
def api_history():
    with _lock:
        return jsonify(_state["history"])


@app.route("/api/behaviours")
def api_behaviours():
    with _lock:
        return jsonify({
            "behaviours":       _state.get("behaviours", []),
            "risks":            _state.get("risks", {}),
            "policy_breakdown": _state.get("policy_breakdown", []),
        })


@app.route("/upload", methods=["POST"])
def upload_video():
    """
    Accept a video file upload, save it, and switch the processing pipeline
    to use the new file. Returns JSON with the new source path.
    """
    import config

    f = request.files.get("video")
    if not f or f.filename == "":
        return jsonify({"error": "No file provided"}), 400

    filename  = f.filename
    ext       = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in config.ALLOWED_EXTENSIONS:
        return jsonify({"error": f"File type .{ext} not allowed"}), 400

    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    save_path = os.path.join(config.UPLOAD_FOLDER, filename)
    f.save(save_path)

    # Switch video source — main loop will pick this up on next iteration
    config.VIDEO_SOURCE = save_path

    with _lock:
        _state["video_source"] = save_path

    print(f"[Server] Video uploaded: {save_path}")
    return jsonify({"ok": True, "source": save_path, "filename": filename})


@app.route("/api/set_lanes", methods=["POST"])
def api_set_lanes():
    """
    Change lane count at runtime.
    POST JSON: {"count": 2}  or  {"count": 4}
    """
    import config

    data  = request.json or {}
    count = data.get("count", 4)

    try:
        count = int(count)
        if count < 1 or count > 6:
            raise ValueError
    except ValueError:
        return jsonify({"error": "count must be 1-6"}), 400

    config.LANE_COUNT = count
    config.LANE_NAMES = [f"LANE_{i+1}" for i in range(count)]

    with _lock:
        _state["lane_count"] = count
        _state["lane_names"] = config.LANE_NAMES

    print(f"[Server] Lane count changed to {count}: {config.LANE_NAMES}")
    return jsonify({"ok": True, "count": count, "lane_names": config.LANE_NAMES})


@app.route("/api/sample_videos")
def api_sample_videos():
    """List available sample videos in the project root."""
    samples = []
    for ext in ["mp4", "avi", "mov"]:
        import glob
        samples += glob.glob(f"*.{ext}")
    return jsonify({"samples": samples})


# ── Start server ──────────────────────────────────────────────────────────────

def run_server(host: str = "0.0.0.0", port: int = 5000) -> None:
    """Start Flask in a background daemon thread."""
    import config
    _state["video_source"] = config.VIDEO_SOURCE
    _state["lane_count"]   = config.LANE_COUNT
    _state["lane_names"]   = config.LANE_NAMES

    t = threading.Thread(
        target=lambda: app.run(
            host=host, port=port,
            debug=False, use_reloader=False,
        ),
        daemon=True,
    )
    t.start()
    print(f"[Server] Dashboard → http://localhost:{port}")