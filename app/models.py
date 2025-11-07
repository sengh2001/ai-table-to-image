# app/models.py
from pydantic import BaseModel

class Item(BaseModel):
    name: str
    price: float


class LLMTablePayload(BaseModel):
    # Accept either your full LLM response object or the inner "table" object
    caption: str | None = None
    label: str | None = None
    table: Dict[str, Any]
    theme: str | None = "tailwind"  # "tailwind" or "bootstrap" or freeform hint like "pink"
