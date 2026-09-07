"""Runtime configuration via environment variables."""

from __future__ import annotations

import os


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Deterministic keyword path is always on. Semantic similarity is opt-in.
USE_SEMANTIC: bool = _env_bool("TRUTHGRAPH_SEMANTIC", False)

# Optional SQLite verification history (default off).
HISTORY_ENABLED: bool = _env_bool("TRUTHGRAPH_HISTORY", False)
HISTORY_DB_PATH: str = os.getenv("TRUTHGRAPH_HISTORY_DB", "data/verification_history.sqlite3")

# Hybrid blend when semantic is enabled: keyword_weight + semantic_weight = 1.0
KEYWORD_WEIGHT: float = float(os.getenv("TRUTHGRAPH_KEYWORD_WEIGHT", "0.7"))
SEMANTIC_WEIGHT: float = float(os.getenv("TRUTHGRAPH_SEMANTIC_WEIGHT", "0.3"))

# Claim decomposition into atomic sub-claims (default on for richer dossiers).
DECOMPOSE_CLAIMS: bool = _env_bool("TRUTHGRAPH_DECOMPOSE", True)

APP_VERSION = "2.0.0"
