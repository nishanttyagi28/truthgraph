"""CLI coverage for gate, audit, suite."""

import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app

runner = CliRunner()


def test_cli_gate_json(tmp_path: Path):
    payload = {
        "claim": {"text": "Earth has one natural satellite."},
        "evidence": [
            {
                "text": "NASA confirms that Earth has one natural satellite called the Moon.",
                "source": "NASA",
                "reliability": 0.98,
            }
        ],
    }
    path = tmp_path / "claim.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = runner.invoke(app, ["gate", str(path), "--json", "--no-decompose"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["decision"] == "ALLOW"
    assert data["policy_id"] == "agent_tool_gate"


def test_cli_audit(tmp_path: Path):
    payload = {
        "claim": {"text": "Earth has one natural satellite."},
        "evidence": [
            {
                "text": "NASA confirms that Earth has one natural satellite called the Moon.",
                "source": "NASA",
                "reliability": 0.98,
            }
        ],
    }
    path = tmp_path / "claim.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    out = tmp_path / "reports"
    result = runner.invoke(
        app,
        ["audit", str(path), "--out", str(out), "--basename", "demo", "--no-decompose"],
    )
    assert result.exit_code == 0, result.output
    assert (out / "demo.json").exists()
    assert (out / "demo.md").exists()


def test_cli_suite_run():
    result = runner.invoke(app, ["suite", "run", "examples/golden/suite.yaml"])
    assert result.exit_code == 0, result.output
    assert "passed" in result.output.lower() or "PASS" in result.output


def test_cli_suite_gate():
    result = runner.invoke(
        app,
        [
            "suite",
            "gate",
            "examples/golden/suite.yaml",
            "--lockfile",
            "examples/golden/suite.lock.json",
        ],
    )
    assert result.exit_code == 0, result.output


def test_cli_policies():
    result = runner.invoke(app, ["policies", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "caption_gate" in data
