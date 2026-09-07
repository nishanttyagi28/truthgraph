"""Agent gate surface: verify + policy decision in one call.

Python helper so an agent can `gate(claim, evidence)` before acting.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from app.models.claim import Claim
from app.models.evidence import Evidence
from app.models.results import VerificationResult
from app.services.policy import (
    Decision,
    PolicyConfig,
    PolicyDecision,
    decide_from_result,
    merge_policy,
)
from app.services.rag import (
    Citation,
    RagVerifyInput,
    annotate_rag_meta,
    citation_aware_reasons,
    rag_to_claim_evidence,
)
from app.services.reputation import lookup_reputation
from app.services.verifier import verify_claim

F = TypeVar("F", bound=Callable[..., Any])


class GateResult(BaseModel):
    """Clear JSON: decision, verdict, confidence, reasons, policy_id (+ dossier)."""

    decision: Decision
    verdict: str
    confidence: float
    reasons: list[str] = Field(default_factory=list)
    policy_id: str
    policy_reasons: list[str] = Field(default_factory=list)
    verification: VerificationResult
    policy: PolicyDecision

    def allowed(self) -> bool:
        return self.decision == "ALLOW"

    def blocked(self) -> bool:
        return self.decision == "BLOCK"


class GateBlockedError(RuntimeError):
    """Raised by require_allow / decorator when decision is not ALLOW."""

    def __init__(self, gate_result: GateResult):
        self.gate_result = gate_result
        super().__init__(
            f"TruthGraph gate {gate_result.decision}: "
            f"verdict={gate_result.verdict} confidence={gate_result.confidence} "
            f"policy={gate_result.policy_id}"
        )


def _prepare_evidence(
    evidence: list[Evidence],
    *,
    use_registry: bool,
) -> list[Evidence]:
    if not use_registry:
        return evidence
    return [
        e.model_copy(update={"reliability": lookup_reputation(e.source, e.reliability)})
        for e in evidence
    ]


def gate(
    claim: Claim | str | None = None,
    evidence: list[Evidence] | None = None,
    *,
    policy_id: str | None = None,
    policy: PolicyConfig | dict[str, Any] | None = None,
    risk_tags: list[str] | None = None,
    use_semantic: bool | None = None,
    use_registry: bool = False,
    decompose: bool | None = None,
    # RAG mode
    answer: str | None = None,
    citations: list[Citation] | dict[str, Any] | None = None,
) -> GateResult:
    """Verify claim against evidence and apply the decision policy.

    Either pass ``claim`` + ``evidence``, or RAG mode via ``answer`` + ``citations``
    (``claim`` may be omitted when ``answer`` is set).
    """
    rag_citations: list[Citation] | None = None
    if answer is not None and citations is not None:
        raw_cites = citations
        if isinstance(raw_cites, list) and raw_cites and isinstance(raw_cites[0], dict):
            rag_citations = [Citation(**c) for c in raw_cites]  # type: ignore[arg-type]
        elif isinstance(raw_cites, list):
            rag_citations = list(raw_cites)  # type: ignore[arg-type]
        else:
            raise TypeError("citations must be a list of Citation or dict")
        claim_obj, evidence_items = rag_to_claim_evidence(
            RagVerifyInput(answer=answer, citations=rag_citations)
        )
    else:
        if claim is None:
            raise ValueError("claim is required unless answer+citations (RAG mode) is used")
        if evidence is None:
            raise ValueError("evidence is required unless answer+citations (RAG mode) is used")
        if isinstance(claim, str):
            claim_obj = Claim(text=claim)
        else:
            claim_obj = claim
        evidence_items = list(evidence)

    evidence_items = _prepare_evidence(evidence_items, use_registry=use_registry)
    result = verify_claim(
        claim_obj,
        evidence_items,
        use_semantic=use_semantic,
        use_registry=use_registry,
        decompose=decompose,
    )

    if rag_citations is not None:
        result.reasons = citation_aware_reasons(
            result.reasons,
            rag_citations,
            supporting_sources=[e.source for e in result.supporting_evidence],
            contradicting_sources=[e.source for e in result.contradicting_evidence],
        )
        result.meta = annotate_rag_meta(result.meta, rag_citations)

    cfg = merge_policy(policy_id=policy_id, overrides=policy, apply_env=True)
    decision = decide_from_result(result, policy=cfg, risk_tags=risk_tags)

    # Combined reasons: verification + policy (gate JSON surface).
    combined_reasons = list(result.reasons) + [
        f"policy[{decision.policy_id}]: {r}" for r in decision.reasons
    ]

    return GateResult(
        decision=decision.decision,
        verdict=result.verdict,
        confidence=result.confidence,
        reasons=combined_reasons,
        policy_id=decision.policy_id,
        policy_reasons=list(decision.reasons),
        verification=result,
        policy=decision,
    )


def require_allow(gate_result: GateResult) -> GateResult:
    """Raise GateBlockedError unless decision is ALLOW."""
    if gate_result.decision != "ALLOW":
        raise GateBlockedError(gate_result)
    return gate_result


def gate_context(
    claim: Claim | str,
    evidence: list[Evidence],
    **kwargs: Any,
):
    """Context manager: enter only when ALLOW; otherwise raise GateBlockedError.

    Example::

        with gate_context(claim, evidence, policy_id="agent_tool_gate") as gr:
            do_side_effect()
    """

    class _Ctx:
        def __enter__(self) -> GateResult:
            self.result = gate(claim, evidence, **kwargs)
            return require_allow(self.result)

        def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

    return _Ctx()


def gated(
    *,
    claim_arg: str = "claim",
    evidence_arg: str = "evidence",
    policy_id: str | None = None,
    **gate_kwargs: Any,
) -> Callable[[F], F]:
    """Decorator: run gate on kwargs/args before calling the wrapped function.

    Expects the wrapped function to receive claim/evidence by keyword (or the
    names given). Blocks (raises) unless decision is ALLOW.
    """

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if claim_arg not in kwargs or evidence_arg not in kwargs:
                raise TypeError(
                    f"@gated requires keyword args {claim_arg!r} and {evidence_arg!r}"
                )
            gr = gate(
                kwargs[claim_arg],
                kwargs[evidence_arg],
                policy_id=policy_id,
                **gate_kwargs,
            )
            require_allow(gr)
            kwargs["_gate_result"] = gr
            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
