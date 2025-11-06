import json
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from typing import Any
from app.schemas import TableJSON
from app.llm_client import parse_table_with_llm
from app.renderer import render_table_image
from io import BytesIO
from fastapi.responses import StreamingResponse

app = FastAPI(title="TableParse & Render API")

@app.post("/parse", response_model=TableJSON)
def parse_endpoint(payload: dict):
    """
    Expects JSON: {"text": "<input in markdown/html/latex/plain>"}
    Returns parsed TableJSON produced by the LLM (and validated).
    """
    text = payload.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="No text provided.")

    raw = parse_table_with_llm(text_input=text, temperature=0.0)
    # The model must return valid JSON. Attempt to parse.
    try:
        parsed = json.loads(raw)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM did not return valid JSON: {e}\nRaw output: {raw[:1000]}")

    # Validate against schema
    try:
        table = TableJSON(**parsed)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"Parsed JSON didn't match schema: {e}")

    # Basic validation: ensure columns length matches rows' cells
    for ridx, row in enumerate(table.rows):
        if len(row) != len(table.columns):
            # Try to be forgiving: pad or truncate
            if len(row) < len(table.columns):
                padded = row + [None] * (len(table.columns) - len(row))
                table.rows[ridx] = padded
            else:
                table.rows[ridx] = row[:len(table.columns)]

    return table

@app.post("/render")
def render_endpoint(payload: TableJSON):
    """
    Accepts TableJSON as request body and returns a PNG image.
    """
    # simple validation
    if not payload.columns:
        raise HTTPException(status_code=400, detail="Table must have at least one column.")
    img = render_table_image(payload.columns, payload.rows, title=payload.title, max_width=1200)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

@app.post("/parse_and_render")
def parse_and_render(payload: dict):
    """
    Accepts {"text": "..."} -> parse with LLM -> validate -> render and return PNG
    """
    table_resp = parse_endpoint(payload)
    # Convert Pydantic model to dict
    table_dict = table_resp.dict()
    img = render_table_image(table_dict["columns"], table_dict["rows"], title=table_dict.get("title"), max_width=1200)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")
