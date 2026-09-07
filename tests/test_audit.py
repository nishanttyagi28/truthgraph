"""Tests for audit dossier export."""

from pathlib import Path

from app.models.claim import Claim
from app.models.evidence import Evidence
from app.services.audit import build_audit_payload, export_audit, render_audit_markdown
from app.services.gate import gate
from app.services.verifier import verify_claim


def test_export_audit_writes_md_and_json(tmp_path: Path):
    claim = Claim(text="Earth has one natural satellite.")
    evidence = [
        Evidence(
            text="NASA confirms that Earth has one natural satellite called the Moon.",
            source="NASA",
            reliability=0.98,
        )
    ]
    gr = gate(claim, evidence, decompose=False)
    paths = export_audit(gr.verification, tmp_path, basename="demo", decision=gr.policy)
    assert paths["json"].exists()
    assert paths["markdown"].exists()
    md = paths["markdown"].read_text(encoding="utf-8")
    assert "TruthGraph Audit Dossier" in md
    assert "ALLOW" in md or gr.decision in md
    payload = build_audit_payload(gr.verification, decision=gr.policy)
    assert payload["schema"] == "truthgraph.audit.v1"
    assert payload["decision"] == gr.decision


def test_render_markdown_without_decision():
    result = verify_claim(
        Claim(text="Earth has one natural satellite."),
        [
            Evidence(
                text="Earth has one natural satellite called the Moon.",
                source="NASA",
                reliability=0.95,
            )
        ],
        decompose=False,
    )
    md = render_audit_markdown(build_audit_payload(result))
    assert "supported" in md
    assert "Supporting evidence" in md
