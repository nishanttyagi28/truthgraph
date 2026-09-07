"""Optional offline semantic similarity (pure-Python TF-IDF cosine).

No network, no paid APIs, no heavyweight model download. Disabled by default
so CI and the deterministic keyword path stay inspectable and stable.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from app.services.text_analyzer import STOP_WORDS

_TOKEN_RE = re.compile(r"[a-z0-9']+")


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in STOP_WORDS]


def _tf(tokens: list[str]) -> dict[str, float]:
    counts = Counter(tokens)
    total = float(len(tokens)) or 1.0
    return {term: count / total for term, count in counts.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    dot = sum(a[t] * b[t] for t in shared)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def semantic_similarity(claim_text: str, evidence_text: str) -> float:
    """Return TF-IDF-ish cosine similarity in [0, 1].

    Uses term frequency only (single-document IDF would be constant). Pure CPU.
    """
    claim_tokens = _tokens(claim_text)
    evidence_tokens = _tokens(evidence_text)
    if not claim_tokens or not evidence_tokens:
        return 0.0
    score = _cosine(_tf(claim_tokens), _tf(evidence_tokens))
    return round(min(max(score, 0.0), 1.0), 3)
