from pydantic import BaseModel
from typing import Any

class OcrResponse(BaseModel):
    raw_text: str
    structured_data:  dict[str, Any]
    confidence_score: float
    pages_processed: int
    file_type: str