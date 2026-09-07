"""TruthGraph FastAPI service."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from app.config import APP_VERSION, HISTORY_ENABLED, USE_SEMANTIC
from app.models.claim import Claim
from app.models.evidence import Evidence
from app.models.results import VerificationResult
from app.services.history import list_history, record_verification
from app.services.reputation import get_registry, lookup_reputation
from app.services.verifier import verify_claim

app = FastAPI(
    title="TruthGraph API",
    description=(
        "Evidence-based, explainable claim verification. "
        "Deterministic keyword core with optional hybrid semantic scoring, "
        "claim decomposition, and source reputation registry."
    ),
    version=APP_VERSION,
)


class VerificationRequest(BaseModel):
    claim: Claim
    evidence: list[Evidence] = Field(min_length=1)
    use_semantic: bool | None = Field(
        default=None,
        description="Override TRUTHGRAPH_SEMANTIC for this request. Default = env/keyword-only.",
    )
    use_registry: bool = Field(
        default=False,
        description="When true, resolve source reliability from the reputation registry.",
    )
    decompose: bool | None = Field(
        default=None,
        description="Override TRUTHGRAPH_DECOMPOSE for this request.",
    )


class BatchVerificationRequest(BaseModel):
    items: list[VerificationRequest] = Field(min_length=1, max_length=50)
    use_semantic: bool | None = None
    use_registry: bool = False
    decompose: bool | None = None


class BatchVerificationResponse(BaseModel):
    results: list[VerificationResult]
    count: int


@app.get("/health")
def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "semantic_default": USE_SEMANTIC,
        "history_enabled": HISTORY_ENABLED,
    }


@app.get("/sources")
def list_sources() -> dict[str, Any]:
    registry = get_registry()
    return {
        "count": len(registry),
        "sources": registry,
        "note": (
            "Caller-supplied Evidence.reliability wins unless use_registry=true "
            "on /verify. Lookup is case-insensitive with substring fallback."
        ),
    }


@app.post("/verify", response_model=VerificationResult)
def verify(request: VerificationRequest) -> VerificationResult:
    # Optionally stamp registry reliability onto copies when requested.
    evidence = request.evidence
    if request.use_registry:
        evidence = [
            e.model_copy(update={"reliability": lookup_reputation(e.source, e.reliability)})
            for e in request.evidence
        ]

    result = verify_claim(
        request.claim,
        evidence,
        use_semantic=request.use_semantic,
        use_registry=request.use_registry,
        decompose=request.decompose,
    )
    record_verification(result)
    return result


@app.post("/verify/batch", response_model=BatchVerificationResponse)
def verify_batch(request: BatchVerificationRequest) -> BatchVerificationResponse:
    results: list[VerificationResult] = []
    for item in request.items:
        use_semantic = (
            item.use_semantic if item.use_semantic is not None else request.use_semantic
        )
        use_registry = item.use_registry or request.use_registry
        decompose = item.decompose if item.decompose is not None else request.decompose

        evidence = item.evidence
        if use_registry:
            evidence = [
                e.model_copy(update={"reliability": lookup_reputation(e.source, e.reliability)})
                for e in item.evidence
            ]

        result = verify_claim(
            item.claim,
            evidence,
            use_semantic=use_semantic,
            use_registry=use_registry,
            decompose=decompose,
        )
        record_verification(result)
        results.append(result)

    return BatchVerificationResponse(results=results, count=len(results))


@app.get("/history")
def verification_history(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    rows = list_history(limit=limit)
    return {
        "enabled": HISTORY_ENABLED,
        "count": len(rows),
        "items": rows,
    }
