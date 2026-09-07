import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app

runner = CliRunner()


def test_cli_verify_json(tmp_path: Path):
    payload = {
        "claim": {"text": "Earth has one natural satellite."},
        "evidence": [
            {
                "text": "Earth has one natural satellite called the Moon.",
                "source": "NASA",
                "reliability": 0.95,
            }
        ],
    }
    path = tmp_path / "claim.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = runner.invoke(app, ["verify", str(path), "--json", "--no-decompose"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["verdict"] == "supported"


def test_cli_verify_yaml(tmp_path: Path):
    path = tmp_path / "claim.yaml"
    path.write_text(
        """
claim:
  text: Earth has one natural satellite.
evidence:
  - text: Earth has one natural satellite called the Moon.
    source: NASA
    reliability: 0.95
""",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["verify", str(path), "--json", "--no-decompose"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["verdict"] == "supported"


def test_cli_sources_json():
    result = runner.invoke(app, ["sources", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "nasa" in data


def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "truthgraph" in result.output.lower()
