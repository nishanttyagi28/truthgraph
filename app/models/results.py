from typing import Literal

from pydantic import BaseModel, Field

from app.models.evidence import Evidence


class VerificationResult(BaseModel):
    claim: str
    verdict: Literal["supported", "contradicted", "insufficient"]
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[Evidence]
    contradicting_evidence: list[Evidence]
    matched_keywords: list[str]