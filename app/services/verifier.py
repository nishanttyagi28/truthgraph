"""Public verifier API — re-exports the implementation module."""

from app.services.verifier_impl import (  # noqa: F401
    MINIMUM_RELEVANCE,
    classify_evidence,
    verify_claim,
)

__all__ = [
    "MINIMUM_RELEVANCE",
    "classify_evidence",
    "verify_claim",
]
