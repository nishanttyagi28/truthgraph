"""TruthGraph FastAPI service — verify + evidence gate."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from app.config import APP_VERSION, DEFAULT_POLICY, HISTORY_ENABLED, USE_SEMANTIC
from app.models.claim import Claim
from app.models.evidence import Evidence
from app.models.results import VerificationResult
from app.services.audit import build_audit_payload, render_audit_markdown
from app.services.gate import GateResult, gate
from app.services.history import list_history, record_verification
from app.services.policy import PolicyConfig, list_presets
from app.services.rag import Citation, RagVerifyInput, annotate_rag_meta, citation_aware_reasons, rag_to_claim_evidence
from app.services.reputation import get_registry, lookup_reputation
from app.services.verifier import verify_claim

app = FastAPI(
    title="TruthGraph API",
    description=(
        "Deterministic evidence gate for AI agents & RAG — "
        "ALLOW / REVIEW / BLOCK with an inspectable dossier. "
        "Not a web-browsing fact checker. Not an LLM-as-judge."
    ),
    version=APP_VERSION,
)


class VerificationRequest(BaseModel):
    claim: Claim | None = None
    evidence: list[Evidence] | None = Field(default=None)
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
    # RAG citation verify mode (additive; /verify contract otherwise unchanged)
    mode: str | None = Field(
        default=None,
        description="Set to 'rag' to treat claim.text as answer and evidence as citations "
        "(adds citation-aware reasons). Or send answer+citations fields instead.",
    )
    answer: str | None = Field(
        default=None,
        description="RAG mode: generated answer (alternative to claim when citations provided).",
    )
    citations: list[Citation] | None = Field(
        default=None,
        description="RAG mode: citation chunks used as evidence.",
    )


class BatchVerificationRequest(BaseModel):
    items: list[VerificationRequest] = Field(min_length=1, max_length=50)
    use_semantic: bool | None = None
    use_registry: bool = False
    decompose: bool | None = None


class BatchVerificationResponse(BaseModel):
    results: list[VerificationResult]
    count: int


class GateRequest(BaseModel):
    """Verify + policy decision in one call."""

    claim: Claim | None = None
    evidence: list[Evidence] | None = None
    # RAG shortcut
    answer: str | None = None
    citations: list[Citation] | None = None
    policy_id: str | None = Field(
        default=None,
        description="Preset: agent_tool_gate | rag_citation_gate | caption_gate",
    )
    policy: PolicyConfig | None = Field(
        default=None,
        description="Optional per-request policy overrides / full custom config.",
    )
    risk_tags: list[str] = Field(default_factory=list)
    use_semantic: bool | None = None
    use_registry: bool = False
    decompose: bool | None = None
    include_audit: bool = Field(
        default=False,
        description="When true, include audit JSON (+ markdown) in the response.",
    )


class GateResponse(BaseModel):
    decision: str
    verdict: str
    confidence: float
    reasons: list[str]
    policy_id: str
    policy_reasons: list[str] = Field(default_factory=list)
    verification: VerificationResult
    policy: dict[str, Any]
    audit: dict[str, Any] | None = None
    audit_markdown: str | None = None


def _run_verify(request: VerificationRequest) -> VerificationResult:
    # RAG path: answer + citations
    if request.citations and (request.answer or (request.claim and request.mode == "rag")):
        answer_text = request.answer or (request.claim.text if request.claim else "")
        rag_input = RagVerifyInput(
            answer=answer_text,
            citations=request.citations,
            source_url=request.claim.source_url if request.claim else None,
        )
        claim, evidence = rag_to_claim_evidence(rag_input)
        if request.use_registry:
            evidence = [
                e.model_copy(update={"reliability": lookup_reputation(e.source, e.reliability)})
                for e in evidence
            ]
        result = verify_claim(
            claim,
            evidence,
            use_semantic=request.use_semantic,
            use_registry=request.use_registry,
            decompose=request.decompose,
        )
        result.reasons = citation_aware_reasons(
            result.reasons,
            request.citations,
            supporting_sources=[e.source for e in result.supporting_evidence],
            contradicting_sources=[e.source for e in result.contradicting_evidence],
        )
        result.meta = annotate_rag_meta(result.meta, request.citations)
        return result

    if request.claim is None or not request.evidence:
        raise ValueError("claim and evidence are required unless answer+citations is provided")

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

    # Soft RAG annotation when mode=rag with plain evidence
    if request.mode == "rag":
        fake_cites = [
            Citation(text=e.text, source=e.source, reliability=e.reliability)
            for e in evidence
        ]
        result.reasons = citation_aware_reasons(
            result.reasons,
            fake_cites,
            supporting_sources=[e.source for e in result.supporting_evidence],
            contradicting_sources=[e.source for e in result.contradicting_evidence],
        )
        result.meta = annotate_rag_meta(result.meta, fake_cites)

    return result


@app.get("/health")
def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "semantic_default": USE_SEMANTIC,
        "history_enabled": HISTORY_ENABLED,
        "default_policy": DEFAULT_POLICY,
        "product": "deterministic_evidence_gate",
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


@app.get("/policies")
def policies() -> dict[str, Any]:
    return {
        "default": DEFAULT_POLICY,
        "presets": list_presets(),
        "note": (
            "Map verdict + confidence (+ risk tags) → ALLOW | REVIEW | BLOCK. "
            "Override via env TRUTHGRAPH_POLICY_*, YAML under app/policies/, "
            "or request body policy / policy_id on POST /gate."
        ),
    }


@app.post("/verify", response_model=VerificationResult)
def verify(request: VerificationRequest) -> VerificationResult:
    try:
        result = _run_verify(request)
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail=str(exc)) from exc
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
        merged = item.model_copy(
            update={
                "use_semantic": use_semantic,
                "use_registry": use_registry,
                "decompose": decompose,
            }
        )
        result = _run_verify(merged)
        record_verification(result)
        results.append(result)

    return BatchVerificationResponse(results=results, count=len(results))


@app.post("/gate", response_model=GateResponse)
def gate_endpoint(request: GateRequest) -> GateResponse:
    """Verify + policy decision (ALLOW / REVIEW / BLOCK) in one call."""
    if request.answer and request.citations:
        gr = gate(
            answer=request.answer,
            citations=request.citations,
            policy_id=request.policy_id,
            policy=request.policy,
            risk_tags=request.risk_tags,
            use_semantic=request.use_semantic,
            use_registry=request.use_registry,
            decompose=request.decompose,
        )
    else:
        if request.claim is None or not request.evidence:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=422,
                detail="Provide claim+evidence, or answer+citations for RAG mode.",
            )
        gr = gate(
            request.claim,
            request.evidence,
            policy_id=request.policy_id,
            policy=request.policy,
            risk_tags=request.risk_tags,
            use_semantic=request.use_semantic,
            use_registry=request.use_registry,
            decompose=request.decompose,
        )

    record_verification(gr.verification)
    audit_payload = None
    audit_md = None
    if request.include_audit:
        audit_payload = build_audit_payload(gr.verification, decision=gr.policy)
        audit_md = render_audit_markdown(audit_payload)

    return GateResponse(
        decision=gr.decision,
        verdict=gr.verdict,
        confidence=gr.confidence,
        reasons=gr.reasons,
        policy_id=gr.policy_id,
        policy_reasons=gr.policy_reasons,
        verification=gr.verification,
        policy=gr.policy.model_dump(),
        audit=audit_payload,
        audit_markdown=audit_md,
    )


@app.get("/history")
def verification_history(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    rows = list_history(limit=limit)
    return {
        "enabled": HISTORY_ENABLED,
        "count": len(rows),
        "items": rows,
    }
