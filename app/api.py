from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.models.claim import Claim
from app.models.evidence import Evidence
from app.models.results import VerificationResult
from app.services.verifier import verify_claim


class VerificationRequest(BaseModel):
    claim: Claim
    evidence: list[Evidence] = Field(min_length=1)


app = FastAPI(
    title="TruthGraph API",
    description="Evidence-based claim verification service",
    version="1.0.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/verify", response_model=VerificationResult)
def verify(request: VerificationRequest) -> VerificationResult:
    return verify_claim(
        request.claim,
        request.evidence,
    )