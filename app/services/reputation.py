"""Source reputation registry with sensible defaults and caller override."""

from __future__ import annotations

from copy import deepcopy

# Case-insensitive lookup keys stored lowercase.
DEFAULT_SOURCE_REPUTATION: dict[str, float] = {
    "nasa": 0.98,
    "cdc": 0.95,
    "who": 0.95,
    "nih": 0.94,
    "nature": 0.93,
    "science": 0.93,
    "reuters": 0.90,
    "associated press": 0.90,
    "ap": 0.90,
    "bbc": 0.88,
    "nytimes": 0.85,
    "the new york times": 0.85,
    "astronomy textbook": 0.90,
    "textbook": 0.85,
    "wikipedia": 0.75,
    "encyclopedia britannica": 0.88,
    "gov": 0.85,
    "edu": 0.82,
    "arxiv": 0.70,
    "blog": 0.40,
    "anonymous blog": 0.30,
    "anonymous": 0.25,
    "social media": 0.25,
    "twitter": 0.25,
    "x": 0.25,
    "reddit": 0.30,
    "forum": 0.30,
    "unknown": 0.50,
}

_registry: dict[str, float] = deepcopy(DEFAULT_SOURCE_REPUTATION)


def reset_registry() -> None:
    """Restore built-in defaults (used by tests)."""
    global _registry
    _registry = deepcopy(DEFAULT_SOURCE_REPUTATION)


def get_registry() -> dict[str, float]:
    return dict(sorted(_registry.items()))


def set_reputation(source: str, score: float) -> None:
    if not 0.0 <= score <= 1.0:
        raise ValueError("reputation score must be between 0 and 1")
    _registry[source.strip().lower()] = score


def lookup_reputation(source: str, fallback: float | None = None) -> float:
    """Resolve a reputation score for a source name.

    Exact lowercase match first, then substring heuristics (e.g. 'NASA.gov').
    """
    key = source.strip().lower()
    if key in _registry:
        return _registry[key]

    for known, score in _registry.items():
        if known in key or key in known:
            return score

    if fallback is not None:
        return fallback
    return _registry.get("unknown", 0.5)


def apply_reputation(
    source: str,
    caller_reliability: float | None = None,
    *,
    override: bool = False,
) -> float:
    """Return effective reliability.

    By default the caller-supplied Evidence.reliability wins when explicitly
    provided on the request. Pass override=True (or omit caller value) to use
    the registry. API layer treats an explicit reliability as caller override.
    """
    if caller_reliability is not None and not override:
        return caller_reliability
    return lookup_reputation(source, fallback=caller_reliability)
