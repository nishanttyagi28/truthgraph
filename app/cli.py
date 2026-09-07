"""TruthGraph CLI — verify, gate, audit, and golden suite."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

import typer

from app.models.claim import Claim
from app.models.evidence import Evidence
from app.services.audit import export_audit
from app.services.gate import gate
from app.services.policy import list_presets
from app.services.reputation import get_registry
from app.services.suite import (
    build_lockfile,
    gate_against_lockfile,
    run_suite,
)
from app.services.verifier import verify_claim

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

app = typer.Typer(
    name="truthgraph",
    help="Deterministic evidence gate: verify claims, ALLOW/REVIEW/BLOCK, audit, suite.",
    add_completion=False,
)
suite_app = typer.Typer(help="Golden claim suite runner + CI gate")
app.add_typer(suite_app, name="suite")


def _load_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise typer.BadParameter("PyYAML is required for YAML input. pip install pyyaml")
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)

    if not isinstance(data, dict):
        raise typer.BadParameter("Input file must contain a JSON/YAML object.")
    return data


def _parse_request(data: dict[str, Any]) -> tuple[Claim, list[Evidence]]:
    claim_raw = data.get("claim")
    if isinstance(claim_raw, str):
        claim = Claim(text=claim_raw)
    elif isinstance(claim_raw, dict):
        claim = Claim(**claim_raw)
    else:
        raise typer.BadParameter("Missing claim (string or object).")

    evidence_raw = data.get("evidence")
    if not isinstance(evidence_raw, list) or not evidence_raw:
        raise typer.BadParameter("evidence must be a non-empty list.")
    evidence = [Evidence(**item) for item in evidence_raw]
    return claim, evidence


@app.command("verify")
def verify_cmd(
    input_file: Path = typer.Argument(..., exists=True, readable=True, help="JSON or YAML file"),
    json_out: bool = typer.Option(False, "--json", help="Print machine-readable JSON only"),
    use_semantic: bool = typer.Option(False, "--semantic", help="Enable hybrid semantic scoring"),
    use_registry: bool = typer.Option(False, "--registry", help="Use source reputation registry"),
    decompose: Optional[bool] = typer.Option(
        None,
        "--decompose/--no-decompose",
        help="Force claim decomposition on/off",
    ),
) -> None:
    """Verify a claim from a JSON or YAML dossier."""
    data = _load_payload(input_file)
    claim, evidence = _parse_request(data)
    result = verify_claim(
        claim,
        evidence,
        use_semantic=use_semantic,
        use_registry=use_registry,
        decompose=decompose,
    )
    payload = result.model_dump()
    if json_out:
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(f"Claim:    {result.claim}")
        typer.echo(f"Verdict:  {result.verdict}")
        typer.echo(f"Confidence: {result.confidence}")
        typer.echo(f"Keywords: {', '.join(result.matched_keywords) or '(none)'}")
        if result.reasons:
            typer.echo("Reasons:")
            for reason in result.reasons[:12]:
                typer.echo(f"  - {reason}")
        if result.subclaims and len(result.subclaims) > 1:
            typer.echo(f"Sub-claims: {len(result.subclaims)}")
            for sub in result.subclaims:
                typer.echo(f"  [{sub.verdict} @ {sub.confidence}] {sub.text}")


@app.command("gate")
def gate_cmd(
    input_file: Path = typer.Argument(..., exists=True, readable=True, help="JSON or YAML file"),
    policy: str = typer.Option(
        "agent_tool_gate",
        "--policy",
        help="Policy preset id: agent_tool_gate | rag_citation_gate | caption_gate",
    ),
    json_out: bool = typer.Option(False, "--json", help="Print machine-readable JSON only"),
    use_semantic: bool = typer.Option(False, "--semantic"),
    use_registry: bool = typer.Option(False, "--registry"),
    decompose: Optional[bool] = typer.Option(None, "--decompose/--no-decompose"),
    risk_tag: list[str] = typer.Option(None, "--risk-tag", help="Optional risk tag (repeatable)"),
) -> None:
    """Verify + policy decision (ALLOW / REVIEW / BLOCK)."""
    data = _load_payload(input_file)
    # RAG file shape: answer + citations
    if "answer" in data and "citations" in data:
        gr = gate(
            answer=data["answer"],
            citations=data["citations"],
            policy_id=policy,
            risk_tags=risk_tag or [],
            use_semantic=use_semantic,
            use_registry=use_registry,
            decompose=decompose,
        )
    else:
        claim, evidence = _parse_request(data)
        gr = gate(
            claim,
            evidence,
            policy_id=policy,
            risk_tags=risk_tag or [],
            use_semantic=use_semantic,
            use_registry=use_registry,
            decompose=decompose,
        )
    payload = {
        "decision": gr.decision,
        "verdict": gr.verdict,
        "confidence": gr.confidence,
        "reasons": gr.reasons,
        "policy_id": gr.policy_id,
        "policy_reasons": gr.policy_reasons,
        "verification": gr.verification.model_dump(),
        "policy": gr.policy.model_dump(),
    }
    if json_out:
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(f"Decision: {gr.decision}")
        typer.echo(f"Verdict:  {gr.verdict}")
        typer.echo(f"Confidence: {gr.confidence}")
        typer.echo(f"Policy:   {gr.policy_id}")
        for reason in gr.policy_reasons:
            typer.echo(f"  - {reason}")


@app.command("audit")
def audit_cmd(
    input_file: Path = typer.Argument(..., exists=True, readable=True),
    out: Path = typer.Option(Path("reports/audit"), "--out", help="Output directory"),
    basename: str = typer.Option("audit", "--basename", help="Output file basename"),
    policy: str = typer.Option("agent_tool_gate", "--policy"),
    use_semantic: bool = typer.Option(False, "--semantic"),
    decompose: Optional[bool] = typer.Option(False, "--decompose/--no-decompose"),
) -> None:
    """Export Markdown + JSON compliance audit dossier."""
    data = _load_payload(input_file)
    claim, evidence = _parse_request(data)
    gr = gate(
        claim,
        evidence,
        policy_id=policy,
        use_semantic=use_semantic,
        decompose=decompose,
    )
    paths = export_audit(
        gr.verification,
        out,
        basename=basename,
        decision=gr.policy,
    )
    typer.echo(f"Wrote {paths['json']}")
    typer.echo(f"Wrote {paths['markdown']}")
    typer.echo(f"Decision: {gr.decision} | Verdict: {gr.verdict} @ {gr.confidence}")


@app.command("policies")
def policies_cmd(
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """List documented decision-policy presets."""
    presets = list_presets()
    if json_out:
        typer.echo(json.dumps(presets, indent=2))
    else:
        for pid, cfg in presets.items():
            typer.echo(f"{pid}")
            typer.echo(f"  min_confidence_allow={cfg['min_confidence_allow']}")
            typer.echo(f"  {cfg['description'][:100]}...")


@app.command("sources")
def sources_cmd(
    json_out: bool = typer.Option(False, "--json", help="Print JSON"),
) -> None:
    """List the built-in source reputation registry."""
    registry = get_registry()
    if json_out:
        typer.echo(json.dumps(registry, indent=2))
    else:
        for name, score in registry.items():
            typer.echo(f"{score:.2f}  {name}")


@app.command("version")
def version_cmd() -> None:
    from app.config import APP_VERSION

    typer.echo(f"truthgraph {APP_VERSION}")


@suite_app.command("run")
def suite_run_cmd(
    suite_path: Path = typer.Argument(
        Path("examples/golden/suite.yaml"),
        exists=True,
        readable=True,
        help="Golden suite YAML/JSON",
    ),
    json_out: bool = typer.Option(False, "--json"),
    write_lock: Optional[Path] = typer.Option(
        None,
        "--write-lock",
        help="Optional path to write a lockfile from current results",
    ),
) -> None:
    """Run the golden claim suite and report passes/fails."""
    report = run_suite(suite_path)
    if write_lock is not None:
        lock = build_lockfile(report)
        write_lock.parent.mkdir(parents=True, exist_ok=True)
        if write_lock.suffix.lower() in {".yaml", ".yml"} and yaml is not None:
            write_lock.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")
        else:
            write_lock.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
        typer.echo(f"Wrote lockfile {write_lock}", err=True)
    if json_out:
        typer.echo(json.dumps(report.to_dict(), indent=2))
    else:
        typer.echo(f"Suite: {report.name}  {report.passed}/{report.total} passed")
        for o in report.outcomes:
            mark = "PASS" if o.passed else "FAIL"
            typer.echo(
                f"  [{mark}] {o.id}: verdict={o.actual_verdict} "
                f"decision={o.actual_decision} conf={o.confidence}"
            )
            if not o.passed:
                for m in o.messages:
                    typer.echo(f"         {m}")
    raise typer.Exit(code=0 if report.ok else 1)


@suite_app.command("gate")
def suite_gate_cmd(
    suite_path: Path = typer.Argument(
        Path("examples/golden/suite.yaml"),
        exists=True,
        readable=True,
    ),
    lockfile: Path = typer.Option(
        ...,
        "--lockfile",
        exists=True,
        readable=True,
        help="Lockfile of expected verdicts/decisions",
    ),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """CI gate: fail when expected verdicts/decisions flip vs lockfile."""
    report = gate_against_lockfile(suite_path, lockfile)
    if json_out:
        typer.echo(json.dumps(report.to_dict(), indent=2))
    else:
        typer.echo(
            f"Suite gate: {report.name}  {report.passed}/{report.total} locked-stable"
        )
        for o in report.outcomes:
            mark = "PASS" if o.passed else "FAIL"
            typer.echo(f"  [{mark}] {o.id}: {', '.join(o.messages)}")
    raise typer.Exit(code=0 if report.ok else 1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
