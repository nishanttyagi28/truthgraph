"""Tests for golden suite runner + lockfile gate."""

import json
from pathlib import Path

from app.services.suite import (
    build_lockfile,
    gate_against_lockfile,
    load_suite,
    run_suite,
)


SUITE = Path("examples/golden/suite.yaml")
LOCK = Path("examples/golden/suite.lock.json")


def test_load_and_run_golden_suite():
    suite = load_suite(SUITE)
    assert len(suite.cases) >= 5
    report = run_suite(SUITE)
    assert report.ok
    assert report.failed == 0


def test_suite_gate_against_lockfile():
    report = gate_against_lockfile(SUITE, LOCK)
    assert report.ok


def test_suite_gate_detects_drift(tmp_path: Path):
    report = run_suite(SUITE)
    lock = build_lockfile(report)
    # Flip one locked verdict to force failure
    first_id = next(iter(lock["cases"]))
    lock["cases"][first_id]["verdict"] = "contradicted"
    lock_path = tmp_path / "broken.lock.json"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    drifted = gate_against_lockfile(SUITE, lock_path)
    assert not drifted.ok
    assert drifted.failed >= 1
