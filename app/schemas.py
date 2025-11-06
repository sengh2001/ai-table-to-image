from pydantic import BaseModel, Field
from typing import List, Optional, Any

class TableRow(BaseModel):
    cells: List[Optional[str]]  # cells can be null/empty

class TableJSON(BaseModel):
    title: Optional[str] = None
    columns: List[str]
    rows: List[List[Optional[str]]]  # rows of cells, must match columns length
    meta: Optional[dict] = Field(default_factory=dict)
