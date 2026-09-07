from pathlib import Path

from app.models.claim import Claim
from app.models.evidence import Evidence
from app.services.history import list_history, record_verification
from app.services.verifier import verify_claim


def test_history_disabled_by_default(tmp_path: Path):
    claim = Claim(text="Earth has one natural satellite.")
    evidence = [
        Evidence(
            text="Earth has one natural satellite called the Moon.",
            source="NASA",
            reliability=0.95,
        )
    ]
    result = verify_claim(claim, evidence, decompose=False)
    row_id = record_verification(result, db_path=str(tmp_path / "h.db"), enabled=False)
    assert row_id is None
    assert list_history(db_path=str(tmp_path / "h.db"), enabled=False) == []


def test_history_records_when_enabled(tmp_path: Path):
    db = str(tmp_path / "history.sqlite3")
    claim = Claim(text="Earth has one natural satellite.")
    evidence = [
        Evidence(
            text="Earth has one natural satellite called the Moon.",
            source="NASA",
            reliability=0.95,
        )
    ]
    result = verify_claim(claim, evidence, decompose=False)
    row_id = record_verification(result, db_path=db, enabled=True)
    assert row_id is not None
    rows = list_history(limit=5, db_path=db, enabled=True)
    assert len(rows) == 1
    assert rows[0]["verdict"] == "supported"
    assert rows[0]["payload"]["claim"] == result.claim
