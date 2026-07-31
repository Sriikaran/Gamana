"""
featherless_service.py
────────────────────────────────────────────────────────────────────────────
Purpose:
    Sole point of contact between Gamana and the Featherless AI (Kimi K2)
    API.  All HTTP calls, retries, logging, validation, and fallback logic
    live here.  No other module should ever call the API directly.

Why it exists:
    Isolating the AI layer means the existing traffic pipeline is completely
    unaffected.  Phase 2 will import FeatherlessTrafficService and call
    generate_strategy() — nothing else changes.

Phase 2 connection:
    main.py will instantiate one FeatherlessTrafficService at startup
    (gated by FEATHERLESS_ENABLED).  Each frame cycle, after the signal
    controller produces its own decision, generate_strategy() will be
    called asynchronously (or every N frames) to produce an advisory
    recommendation that can enrich the dashboard or fine-tune timing.
────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

import requests

# ── Load .env if python-dotenv is available (graceful if not installed) ───────
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=_env_path)
except ImportError:
    pass

# ── Resolve import path so service can be run standalone ─────────────────────
_BACKEND_DIR = Path(__file__).parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from services.featherless_config import (
    FEATHERLESS_API_KEY,
    FEATHERLESS_BASE_URL,
    FEATHERLESS_MODEL,
    REQUEST_TIMEOUT_S,
    MAX_TOKENS,
    TEMPERATURE,
    MAX_RETRIES,
    PROMPT_FILE,
    LOG_FILE,
    REQUIRED_RESPONSE_KEYS,
)
from models.featherless_response import FeatherlessResponse


# ─────────────────────────────────────────────────────────────────────────────
# Logging setup
# ─────────────────────────────────────────────────────────────────────────────
def _build_logger(name: str = "featherless") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler (creates logs/ dir if needed)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError as e:
        logger.warning(f"Could not create log file: {e}")

    return logger


_log = _build_logger()


# ─────────────────────────────────────────────────────────────────────────────
# FeatherlessTrafficService
# ─────────────────────────────────────────────────────────────────────────────
class FeatherlessTrafficService:
    """
    Reusable service for communicating with Featherless AI (Kimi K2).

    Usage
    -----
        service = FeatherlessTrafficService()
        if service.initialize():
            result = service.generate_strategy(intersection_state_dict)
            print(result.to_dict())
    """

    def __init__(self) -> None:
        self._api_key:      str           = FEATHERLESS_API_KEY
        self._base_url:     str           = FEATHERLESS_BASE_URL.rstrip("/")
        self._model:        str           = FEATHERLESS_MODEL
        self._system_prompt: str          = ""
        self._ready:        bool          = False
        self._session:      Optional[requests.Session] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def initialize(self) -> bool:
        """
        Prepare the service:
          1. Load the system prompt from disk.
          2. Build a persistent HTTP session with auth headers.
          3. Mark the service as ready.

        Returns True on success, False on any error.
        Never raises.
        """
        try:
            if not self._api_key:
                _log.error(
                    "FEATHERLESS_API_KEY is empty.  "
                    "Set it in backend/.env or as an environment variable."
                )
                return False

            self._system_prompt = self._load_prompt()
            self._session = self._build_session()
            self._ready = True
            _log.info(
                f"[Featherless] Service initialised — model={self._model}, "
                f"url={self._base_url}"
            )
            return True

        except Exception as exc:
            _log.exception(f"[Featherless] initialize() failed: {exc}")
            return False

    def health_check(self) -> Dict[str, Any]:
        """
        Send a minimal request to verify API connectivity.
        Returns a dict with keys: {'status', 'model', 'latency_ms'}.
        Never raises.
        """
        if not self._ready:
            return {"status": "not_initialized", "model": self._model, "latency_ms": 0}

        dummy_state = {
            "intersection": {
                "north": {"vehicles": 2, "wait_s": 10, "pressure": 20},
                "south": {"vehicles": 0, "wait_s": 0,  "pressure": 0},
                "east":  {"vehicles": 1, "wait_s": 5,  "pressure": 10},
                "west":  {"vehicles": 0, "wait_s": 0,  "pressure": 0},
            }
        }
        t0 = time.time()
        resp = self.generate_strategy(dummy_state)
        latency_ms = int((time.time() - t0) * 1000)

        if resp.status == "fallback":
            return {"status": "unhealthy", "model": self._model, "latency_ms": latency_ms}
        return {"status": "healthy", "model": self._model, "latency_ms": latency_ms}

    def generate_strategy(
        self, intersection_state: Dict[str, Any]
    ) -> FeatherlessResponse:
        """
        Core method: send the intersection state to Featherless AI and return
        a validated, typed FeatherlessResponse.

        Parameters
        ----------
        intersection_state : dict
            Must include at least one lane under 'intersection'.
            Example:
            {
                "intersection": {
                    "LANE_1": {"vehicles": 12, "wait_s": 45, "pressure": 78},
                    "LANE_2": {"vehicles": 4,  "wait_s": 10, "pressure": 22},
                }
            }

        Returns
        -------
        FeatherlessResponse
            Always returns a FeatherlessResponse — never raises.
            status == "fallback" signals a degraded response.
        """
        if not self._ready:
            _log.warning("[Featherless] Service not initialised — returning fallback.")
            return FeatherlessResponse.fallback()

        return self._call_with_retry(intersection_state)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _call_with_retry(
        self, intersection_state: Dict[str, Any]
    ) -> FeatherlessResponse:
        """Attempt the API call up to (1 + MAX_RETRIES) times."""
        payload = json.dumps(intersection_state, indent=2, ensure_ascii=False)

        for attempt in range(1 + MAX_RETRIES):
            _log.info(
                f"[Featherless] generate_strategy attempt={attempt + 1} "
                f"payload_bytes={len(payload)}"
            )
            t0 = time.time()
            try:
                raw = self._http_call(payload)
                elapsed = round((time.time() - t0) * 1000)
                _log.debug(f"[Featherless] response_ms={elapsed} raw={raw[:300]!r}")

                validated = self._validate(raw)
                if validated is not None:
                    _log.info(
                        f"[Featherless] Valid response received "
                        f"lane={validated.recommended_lane} "
                        f"confidence={validated.confidence}"
                    )
                    return validated

                _log.warning(
                    f"[Featherless] Validation failed attempt={attempt + 1}."
                )

            except requests.Timeout:
                _log.warning(f"[Featherless] Timeout on attempt {attempt + 1}.")
            except requests.RequestException as exc:
                _log.warning(f"[Featherless] Network error attempt {attempt + 1}: {exc}")
            except Exception as exc:
                _log.exception(f"[Featherless] Unexpected error attempt {attempt + 1}: {exc}")

        _log.error("[Featherless] All attempts exhausted — returning fallback.")
        return FeatherlessResponse.fallback()

    def _http_call(self, payload_json: str) -> str:
        """Execute a single HTTP POST and return the raw content string."""
        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user",   "content": payload_json},
        ]
        body = {
            "model":       self._model,
            "messages":    messages,
            "max_tokens":  MAX_TOKENS,
            "temperature": TEMPERATURE,
        }
        resp = self._session.post(
            f"{self._base_url}/chat/completions",
            json=body,
            timeout=REQUEST_TIMEOUT_S,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    def _validate(self, raw: str) -> Optional[FeatherlessResponse]:
        """
        Parse and validate the raw LLM text.
        Returns a FeatherlessResponse on success, None on failure.
        """
        # Strip markdown fences if the model ignored the prompt rule
        clean = raw.strip()
        if clean.startswith("```"):
            clean = "\n".join(
                line for line in clean.splitlines()
                if not line.strip().startswith("```")
            ).strip()

        try:
            data = json.loads(clean)
        except json.JSONDecodeError as exc:
            _log.debug(f"[Featherless] JSON parse error: {exc} | raw={clean[:200]!r}")
            return None

        missing = REQUIRED_RESPONSE_KEYS - set(data.keys())
        if missing:
            _log.debug(f"[Featherless] Missing keys in response: {missing}")
            return None

        # Type-guard key fields
        if not isinstance(data.get("reasoning"),       list): return None
        if not isinstance(data.get("priority_factors"), list): return None
        try:
            float(data["confidence"])
            int(data["green_duration"])
        except (TypeError, ValueError):
            return None

        return FeatherlessResponse.from_dict(data)

    def _load_prompt(self) -> str:
        if not PROMPT_FILE.is_file():
            raise FileNotFoundError(f"System prompt not found: {PROMPT_FILE}")
        return PROMPT_FILE.read_text(encoding="utf-8").strip()

    @staticmethod
    def _build_session() -> requests.Session:
        s = requests.Session()
        s.headers.update({
            "Authorization": f"Bearer {FEATHERLESS_API_KEY}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        })
        return s
