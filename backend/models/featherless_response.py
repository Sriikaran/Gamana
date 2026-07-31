"""
featherless_response.py
────────────────────────────────────────────────────────────────────────────
Purpose:
    Typed data-model for every response that comes out of FeatherlessTrafficService.
    Using dataclasses (stdlib, no extra dependencies) keeps the model lightweight.

Why it exists:
    Prevents raw dict/JSON from leaking into the rest of the codebase.
    Phase 2 will import FeatherlessResponse directly so that the signal
    controller can access strongly-typed fields instead of dict key lookups.

Phase 2 connection:
    main.py will receive a FeatherlessResponse (or FallbackResponse) from the
    service and optionally feed recommended_lane / green_duration into the
    signal controller as advisory hints.
────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class FeatherlessResponse:
    """
    Structured, validated response from Kimi K3 / Featherless AI.

    Attributes
    ----------
    recommended_lane : str
        The lane the AI recommends granting a green signal.
    green_duration : int
        Suggested green duration in seconds (clamped 12–60 by service).
    confidence : float
        AI self-reported confidence [0.0, 1.0].
    reasoning : List[str]
        Ordered list of reasoning sentences from the model.
    future_prediction : str
        One-sentence forecast of near-future traffic conditions.
    priority_factors : List[str]
        Key factors that drove the recommendation.
    status : str
        "ok" for valid responses, "fallback" for degraded/error states.
    """

    recommended_lane:  str         = ""
    green_duration:    int         = 30
    confidence:        float       = 0.0
    reasoning:         List[str]   = field(default_factory=list)
    future_prediction: str         = ""
    priority_factors:  List[str]   = field(default_factory=list)
    status:            str         = "ok"

    # Metadata fields requested by user
    backend_status:      str         = "ok"
    api_status:          str         = "ok"
    model:               str         = "Kimi K3"
    queue_status:        str         = "healthy"
    processing:          bool        = False
    response_latency_ms: int         = 0
    inference_time_ms:   int         = 0
    recommendation_age_s:float       = 0.0
    last_updated:        float       = 0.0
    snapshot_timestamp:  float       = 0.0
    request_timestamp:   float       = 0.0
    response_timestamp:  float       = 0.0

    # ── Convenience constructors ─────────────────────────────────────────────

    @classmethod
    def fallback(cls) -> "FeatherlessResponse":
        """Return a safe fallback object when AI is unavailable or invalid."""
        return cls(
            status="fallback",
            backend_status="error",
            api_status="offline",
            queue_status="offline"
        )

    @classmethod
    def from_dict(cls, data: dict) -> "FeatherlessResponse":
        """
        Build a FeatherlessResponse from a validated dict.
        Clamps green_duration and confidence to safe ranges.
        """
        return cls(
            recommended_lane  = str(data.get("recommended_lane", "")),
            green_duration    = max(12, min(60, int(data.get("green_duration", 30)))),
            confidence        = max(0.0, min(1.0, float(data.get("confidence", 0.0)))),
            reasoning         = list(data.get("reasoning", [])),
            future_prediction = str(data.get("future_prediction", "")),
            priority_factors  = list(data.get("priority_factors", [])),
            status            = str(data.get("status", "ok")),
            backend_status    = str(data.get("backend_status", "ok")),
            api_status        = str(data.get("api_status", "ok")),
            model             = str(data.get("model", "Kimi K3")),
            queue_status      = str(data.get("queue_status", "healthy")),
            processing        = bool(data.get("processing", False)),
            response_latency_ms= int(data.get("response_latency_ms", 0)),
            inference_time_ms = int(data.get("inference_time_ms", 0)),
            recommendation_age_s= float(data.get("recommendation_age_s", 0.0)),
            last_updated      = float(data.get("last_updated", 0.0)),
            snapshot_timestamp= float(data.get("snapshot_timestamp", 0.0)),
            request_timestamp = float(data.get("request_timestamp", 0.0)),
            response_timestamp= float(data.get("response_timestamp", 0.0)),
        )

    def to_dict(self) -> dict:
        """Serialise to plain dict (for JSON responses from Flask endpoints)."""
        return {
            "recommended_lane":  self.recommended_lane,
            "green_duration":    self.green_duration,
            "confidence":        self.confidence,
            "reasoning":         self.reasoning,
            "future_prediction": self.future_prediction,
            "priority_factors":  self.priority_factors,
            "status":            self.status,
            "backend_status":    self.backend_status,
            "api_status":        self.api_status,
            "model":             self.model,
            "queue_status":      self.queue_status,
            "processing":        self.processing,
            "response_latency_ms": self.response_latency_ms,
            "inference_time_ms": self.inference_time_ms,
            "recommendation_age_s": self.recommendation_age_s,
            "last_updated":      self.last_updated,
            "snapshot_timestamp": self.snapshot_timestamp,
            "request_timestamp": self.request_timestamp,
            "response_timestamp": self.response_timestamp,
        }
