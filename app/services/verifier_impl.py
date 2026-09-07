"""Verifier implementation facade."""

from app.services.verifier_atomic import (  # noqa: F401
    MINIMUM_RELEVANCE,
    classify_evidence,
    _verify_atomic,
)
from app.services.verifier_rollup import (  # noqa: F401
    verify_claim,
)

__all__ = [
    "MINIMUM_RELEVANCE",
    "classify_evidence",
    "verify_claim",
]
