from pydantic import BaseModel, Field

class Claim(BaseModel):
    text: str = Field(min_length=10, max_length=500)
    source_url: str | None = None
    status: str = "pending"
    