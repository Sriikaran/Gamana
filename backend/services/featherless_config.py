# featherless_config.py
# ─────────────────────────────────────────────────────────────────────────────
# Purpose:
#   Centralised configuration for the Featherless AI integration layer.
#   All tuneable parameters live here — no magic numbers scattered across files.
#
# Why it exists:
#   Separating configuration from logic allows Phase 2 to change model, timeout,
#   or endpoint without touching service code.
#
# Phase 2 connection:
#   featherless_service.py imports every constant from this file.
#   main.py / server.py will import FEATHERLESS_ENABLED to gate the feature.
# ─────────────────────────────────────────────────────────────────────────────

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=_env_path)
except ImportError:
    pass

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent          # backend/services/
_BACKEND = _HERE.parent                # backend/
_PROMPTS = _BACKEND / "prompts"

PROMPT_FILE: Path = _PROMPTS / "traffic_strategist_prompt.txt"
LOG_FILE: Path = _BACKEND / "logs" / "featherless.log"

# ── API credentials (loaded from .env or environment) ─────────────────────────
FEATHERLESS_API_KEY: str = os.getenv("FEATHERLESS_API_KEY", "")
FEATHERLESS_BASE_URL: str = os.getenv(
    "FEATHERLESS_BASE_URL",
    "https://api.featherless.ai/v1"
)

# ── Model selection ────────────────────────────────────────────────────────────
FEATHERLESS_MODEL: str = os.getenv("FEATHERLESS_MODEL", "moonshotai/Kimi-K2-Instruct")

# ── Request parameters ─────────────────────────────────────────────────────────
REQUEST_TIMEOUT_S: int = int(os.getenv("FEATHERLESS_TIMEOUT", "20"))
MAX_TOKENS: int = int(os.getenv("FEATHERLESS_MAX_TOKENS", "512"))
TEMPERATURE: float = float(os.getenv("FEATHERLESS_TEMPERATURE", "0.2"))

# ── Retry policy ───────────────────────────────────────────────────────────────
MAX_RETRIES: int = 1          # retry once on failure, then fallback

# ── Feature flag ──────────────────────────────────────────────────────────────
# Phase 2 will read this flag in main.py to decide whether to activate the AI
# advisory layer without breaking the existing signal controller.
FEATHERLESS_ENABLED: bool = os.getenv("FEATHERLESS_ENABLED", "true").lower() == "true"

# ── Response schema ───────────────────────────────────────────────────────────
# Canonical keys the service validates against.
REQUIRED_RESPONSE_KEYS = {
    "recommended_lane",
    "green_duration",
    "confidence",
    "reasoning",
    "future_prediction",
    "priority_factors",
}
