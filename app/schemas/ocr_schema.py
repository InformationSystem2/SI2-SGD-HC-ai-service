from pydantic import BaseModel

class OcrResponse(BaseModel):
    raw_text: str
    confidence_score: float
    pages_processed: int
    file_type: str