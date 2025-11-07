# app/routes.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Any
import os
import json
import traceback
from dotenv import load_dotenv

load_dotenv()

# groq SDK
import groq
from groq import Groq

router = APIRouter()

# ------------------------------
# Models
# ------------------------------
class Item(BaseModel):
    name: str
    price: float

class ParseRequest(BaseModel):
    text: str

# ------------------------------
# Demo endpoints (router)
# ------------------------------
items_db: List[Any] = []

@router.get("/hello")
def say_hello(name: str = "World"):
    return {"message": f"Hello, {name}!"}

@router.post("/item")
def create_item(item: Item):
    item_dict = item.dict()
    items_db.append(item_dict)
    return {"status": "success", "item": item_dict}

@router.get("/items", response_model=List[Item])
def list_items():
    return items_db

# ------------------------------
# LLM parsing endpoint (RAW output)
# ------------------------------
@router.post("/parse_table")
def parse_table(req: ParseRequest):
    """
    Accepts English description of a table, sends it to the LLM, and returns the raw model output.
    No JSON parsing or repair is attempted — the LLM response is returned verbatim.
    """
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="`text` must not be empty")

    if "GROQ_API_KEY" not in os.environ:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY not set in environment. Set your Groq API key and restart the server."
        )

    client = Groq()

    system_prompt = """
    You are an expert table parser that converts raw textual tables into clean structured JSON.

    ### Objective
    Given a table-like text input (which may include multiple header rows, missing values, or uneven spacing), your task is to infer:
    - The column hierarchy (including sub-columns if any),
    - The correct data rows,
    - And produce a clean, machine-readable JSON structure.

    ### Instructions
    1. Identify how many header rows exist.
    - The first header line defines main categories (e.g., “Consensus(%)”, “Relevancy(%)”).
    - The second header line defines sub-columns under each main category (e.g., “BASE”, “FT”, “TT”).
    2. Merge the headers into flattened column names using underscores.
    - Example: “Consensus(%)” + “BASE” → “Consensus_BASE”.
    3. Extract all data rows below the headers.
    4. Replace any missing or placeholder symbols like “–”, “—”, or “NA” with "null".
    5. Output **only JSON**, with the following structure:

    {
    "columns": ["column_1", "column_2", "..."],
    "rows": [
        ["row_1_value_1", "row_1_value_2", "..."],
        ["row_2_value_1", "row_2_value_2", "..."]
    ]
    }

    6. Do not include captions, notes, explanations, or markdown formatting.
    7. If the input appears malformed, make a best-effort interpretation.

    ### Example Input
    Lang Consensus(%) Relevancy(%) Factuality(%)
    BASE FT TT BASE FT TT BASE FT TT
    En 98.0 99.3 – 32.3 70.6 – 32.6 55.3 –
    Hi 97.5 93.3 96.2 62.5 66.6 74.1 28.7 38.3 42.0
    Pa 95.0 85.4 96.6 38.3 62.5 72.9 25.8 35.4 37.9

    ### Example Output
    {
    "columns": [
        "Lang",
        "Consensus_BASE", "Consensus_FT", "Consensus_TT",
        "Relevancy_BASE", "Relevancy_FT", "Relevancy_TT",
        "Factuality_BASE", "Factuality_FT", "Factuality_TT"
    ],
    "rows": [
        ["En", 98.0, 99.3, null, 32.3, 70.6, null, 32.6, 55.3, null],
        ["Hi", 97.5, 93.3, 96.2, 62.5, 66.6, 74.1, 28.7, 38.3, 42.0],
        ["Pa", 95.0, 85.4, 96.6, 38.3, 62.5, 72.9, 25.8, 35.4, 37.9]
    ]
    }
    """
        

    user_prompt = (
        f"Input description:\n{text}\n\n"
        "Now output your response (if JSON, that's fine). Return exactly what you generate — no extra wrapping."
    )

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_completion_tokens=1024,
            top_p=1,
            stream=False
        )

        # defensive extraction of raw text from SDK response shapes
        out_text = ""
        try:
            if hasattr(completion, "choices") and completion.choices:
                first = completion.choices[0]
                # new shape: .message.content
                if hasattr(first, "message") and getattr(first.message, "content", None):
                    out_text = first.message.content
                # older shape: .text
                elif getattr(first, "text", None):
                    out_text = first.text
                # fallback
                elif getattr(first, "delta", None) and getattr(first.delta, "content", None):
                    out_text = first.delta.content
        except Exception:
            out_text = repr(completion)

        # final fallback
        if not out_text:
            out_text = getattr(completion, "text", "") or getattr(completion, "content", "") or str(completion)

        # Return raw output verbatim
        return {"ok": True, "raw": out_text}

    except groq.AuthenticationError:
        # Clear message for invalid API key
        print("=== parse_table: AuthenticationError from Groq ===")
        print(traceback.format_exc())
        raise HTTPException(status_code=401, detail="Invalid GROQ_API_KEY (authentication failed). Check your key.")
    except Exception as e:
        print("=== parse_table: Exception calling Groq ===")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error calling LLM: {str(e)} (see server logs)")
