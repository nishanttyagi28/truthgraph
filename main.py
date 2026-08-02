from pathlib import Path

from app.models.claim import Claim
from app.models.evidence import Evidence
from app.services.verifier import verify_claim


def save_report(report_json: str) -> Path:
    reports_folder = Path("reports")
    reports_folder.mkdir(exist_ok=True)

    report_path = reports_folder / "verification_report.json"
    report_path.write_text(report_json, encoding="utf-8")

    return report_path


def main() -> None:
    claim = Claim(
        text="The Earth has one natural satellite."
    )

    evidence_items = [
        Evidence(
            text="NASA confirms that Earth has one natural satellite called the Moon.",
            source="NASA",
            reliability=0.98,
        ),
        Evidence(
            text="Earth has one natural satellite, which is commonly known as the Moon.",
            source="Astronomy Textbook",
            reliability=0.90,
        ),
        Evidence(
            text="Earth does not have one natural satellite according to this anonymous post.",
            source="Anonymous Blog",
            reliability=0.30,
        ),
        Evidence(
            text="Mars has two moons named Phobos and Deimos.",
            source="Space Magazine",
            reliability=0.75,
        ),
    ]

    result = verify_claim(claim, evidence_items)
    report_json = result.model_dump_json(indent=2)
    report_path = save_report(report_json)

    print(report_json)
    print(f"\nReport saved at: {report_path}")


if __name__ == "__main__":
    main()