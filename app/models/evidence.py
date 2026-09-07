from pydantic import BaseModel, Field


class Evidence(BaseModel):
    text: str = Field(min_length=10, max_length=1000)
    source: str = Field(min_length=2, max_length=100)
    reliability: float = Field(default=0.7, ge=0.0, le=1.0)
