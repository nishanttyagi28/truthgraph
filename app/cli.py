"""TruthGraph CLI — verify claims from JSON/YAML files."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

import typer

from app.models.claim import Claim
from app.models.evidence import Evidence
from app.services.reputation import get_registry
from app.services.verifier import verify_claim

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

app = typer.Typer(
    name="truthgraph",
    help="Explainable claim verification against provided evidence.",
    add_completion=False,
)


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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
