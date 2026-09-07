"""Rule-based claim decomposition into atomic sub-claims."""

from __future__ import annotations

import re

# Split on sentence boundaries and light coordinating patterns.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_CLAUSE_SPLIT = re.compile(
    r"\s*;\s*|\s+\band\b\s+(?=[A-Z0-9])|\s+\balso\b\s+|\s+\bwhile\b\s+",
    re.IGNORECASE,
)


def decompose_claim(text: str) -> list[str]:
    """Split a compound claim into smaller verifiable statements.

    Deterministic and inspectable. Falls back to the original text when no
    useful split is found. Preserves order and strips empty fragments.
    """
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return []

    parts: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(cleaned):
        sentence = sentence.strip()
        if not sentence:
            continue
        clauses = [c.strip(" ,;") for c in _CLAUSE_SPLIT.split(sentence) if c.strip()]
        if len(clauses) > 1:
            parts.extend(clauses)
        else:
            parts.append(sentence)

    # Drop tiny fragments that are not useful as claims.
    atomic = [p if p.endswith((".", "!", "?")) else f"{p}." for p in parts if len(p) >= 8]

    if not atomic:
        return [cleaned if cleaned.endswith((".", "!", "?")) else f"{cleaned}."]

    # If decomposition produced only the original (normalized), keep one entry.
    if len(atomic) == 1:
        return atomic

    return atomic
