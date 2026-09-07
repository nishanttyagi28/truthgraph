"""Golden claim suite runner + CI gate (VisionEval traps-gate energy).

Fail CI-style when expected verdicts (or decisions) flip.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.models.claim import Claim
from app.models.evidence import Evidence
from app.services.gate import gate
from app.services.verifier import verify_claim

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore


class GoldenCase(BaseModel):
    """One locked claim/evidence scenario with expected outcomes."""

    id: str
    claim: str | dict[str, Any]
    evidence: list[dict[str, Any]]
    expected_verdict: str
    expected_decision: str | None = None
    policy_id: str | None = "agent_tool_gate"
    decompose: bool | None = False
    use_semantic: bool | None = False
    risk_tags: list[str] = Field(default_factory=list)
    description: str = ""
    # RAG mode optional
    mode: str | None = None  # "rag" to treat claim as answer + evidence as citations


class GoldenSuite(BaseModel):
    name: str = "truthgraph-golden"
    version: str = "1"
    cases: list[GoldenCase]


@dataclass
class CaseOutcome:
    id: str
    passed: bool
    expected_verdict: str
    actual_verdict: str
    expected_decision: str | None
    actual_decision: str | None
    confidence: float
    messages: list[str] = field(default_factory=list)


@dataclass
class SuiteReport:
    name: str
    total: int
    passed: int
    failed: int
    outcomes: list[CaseOutcome]

    @property
    def ok(self) -> bool:
        return self.failed == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "ok": self.ok,
            "outcomes": [
                {
                    "id": o.id,
                    "passed": o.passed,
                    "expected_verdict": o.expected_verdict,
                    "actual_verdict": o.actual_verdict,
                    "expected_decision": o.expected_decision,
                    "actual_decision": o.actual_decision,
                    "confidence": o.confidence,
                    "messages": o.messages,
                }
                for o in self.outcomes
            ],
        }


def _load_raw(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML required for YAML suites")
        return yaml.safe_load(text)
    return json.loads(text)


def load_suite(path: str | Path) -> GoldenSuite:
    raw = _load_raw(Path(path))
    if isinstance(raw, list):
        return GoldenSuite(cases=[GoldenCase(**c) for c in raw])
    if isinstance(raw, dict):
        if "cases" in raw:
            return GoldenSuite(**raw)
        # single case file
        return GoldenSuite(cases=[GoldenCase(**raw)])
    raise ValueError(f"Unsupported suite format in {path}")


def _claim_from(case: GoldenCase) -> Claim:
    if isinstance(case.claim, str):
        return Claim(text=case.claim)
    return Claim(**case.claim)


def run_case(case: GoldenCase) -> CaseOutcome:
    claim = _claim_from(case)
    evidence = [Evidence(**e) for e in case.evidence]
    messages: list[str] = []

    if case.expected_decision:
        gr = gate(
            claim,
            evidence,
            policy_id=case.policy_id,
            risk_tags=case.risk_tags,
            use_semantic=case.use_semantic,
            decompose=case.decompose,
        )
        actual_verdict = gr.verdict
        actual_decision = gr.decision
        confidence = gr.confidence
    else:
        result = verify_claim(
            claim,
            evidence,
            use_semantic=case.use_semantic,
            decompose=case.decompose,
        )
        actual_verdict = result.verdict
        actual_decision = None
        confidence = result.confidence

    passed = actual_verdict == case.expected_verdict
    if case.expected_decision is not None:
        if actual_decision != case.expected_decision:
            passed = False
            messages.append(
                f"decision: expected {case.expected_decision}, got {actual_decision}"
            )
    if actual_verdict != case.expected_verdict:
        messages.append(
            f"verdict: expected {case.expected_verdict}, got {actual_verdict}"
        )
    if passed:
        messages.append("ok")

    return CaseOutcome(
        id=case.id,
        passed=passed,
        expected_verdict=case.expected_verdict,
        actual_verdict=actual_verdict,
        expected_decision=case.expected_decision,
        actual_decision=actual_decision,
        confidence=confidence,
        messages=messages,
    )


def run_suite(path: str | Path) -> SuiteReport:
    suite = load_suite(path)
    outcomes = [run_case(c) for c in suite.cases]
    passed = sum(1 for o in outcomes if o.passed)
    failed = len(outcomes) - passed
    return SuiteReport(
        name=suite.name,
        total=len(outcomes),
        passed=passed,
        failed=failed,
        outcomes=outcomes,
    )


def build_lockfile(report: SuiteReport) -> dict[str, Any]:
    """Snapshot of expected verdicts/decisions for CI gating."""
    locks = {}
    for o in report.outcomes:
        locks[o.id] = {
            "verdict": o.actual_verdict,
            "decision": o.actual_decision,
            "confidence": o.confidence,
        }
    return {
        "schema": "truthgraph.suite.lock.v1",
        "suite": report.name,
        "cases": locks,
    }


def load_lockfile(path: str | Path) -> dict[str, Any]:
    raw = _load_raw(Path(path))
    if not isinstance(raw, dict):
        raise ValueError("Lockfile must be a JSON/YAML object")
    return raw


def gate_against_lockfile(
    suite_path: str | Path,
    lockfile_path: str | Path,
) -> SuiteReport:
    """Re-run suite and fail cases whose verdict/decision drifted from the lockfile."""
    suite = load_suite(suite_path)
    lock = load_lockfile(lockfile_path)
    locked_cases: dict[str, Any] = lock.get("cases") or {}
    outcomes: list[CaseOutcome] = []

    for case in suite.cases:
        outcome = run_case(case)
        locked = locked_cases.get(case.id)
        messages = list(outcome.messages)
        passed = outcome.passed
        if locked is None:
            passed = False
            messages.append(f"missing from lockfile: {case.id}")
        else:
            if locked.get("verdict") != outcome.actual_verdict:
                passed = False
                messages.append(
                    f"lock verdict drift: locked={locked.get('verdict')} "
                    f"actual={outcome.actual_verdict}"
                )
            locked_decision = locked.get("decision")
            if locked_decision is not None and locked_decision != outcome.actual_decision:
                passed = False
                messages.append(
                    f"lock decision drift: locked={locked_decision} "
                    f"actual={outcome.actual_decision}"
                )
        outcomes.append(
            CaseOutcome(
                id=outcome.id,
                passed=passed,
                expected_verdict=outcome.expected_verdict,
                actual_verdict=outcome.actual_verdict,
                expected_decision=outcome.expected_decision,
                actual_decision=outcome.actual_decision,
                confidence=outcome.confidence,
                messages=messages,
            )
        )

    # Also flag lock entries that disappeared from the suite.
    suite_ids = {c.id for c in suite.cases}
    for lid in locked_cases:
        if lid not in suite_ids:
            outcomes.append(
                CaseOutcome(
                    id=lid,
                    passed=False,
                    expected_verdict=str(locked_cases[lid].get("verdict")),
                    actual_verdict="(missing from suite)",
                    expected_decision=locked_cases[lid].get("decision"),
                    actual_decision=None,
                    confidence=0.0,
                    messages=["present in lockfile but missing from suite"],
                )
            )

    passed_n = sum(1 for o in outcomes if o.passed)
    failed_n = len(outcomes) - passed_n
    return SuiteReport(
        name=suite.name,
        total=len(outcomes),
        passed=passed_n,
        failed=failed_n,
        outcomes=outcomes,
    )
