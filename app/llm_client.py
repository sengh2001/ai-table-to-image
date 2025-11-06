import os
from groq import Groq

# initialize client; adjust per the actual Groq API
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", None)
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else Groq()

def parse_table_with_llm(text_input: str, max_tokens: int = 1024, temperature: float = 0.0) -> str:
    """
    Calls the LLM to parse arbitrary text into a strict JSON table structure.
    Returns the raw assistant content (expected to be JSON).
    """
    # Strong system + user instructions to force only JSON output
    system_prompt = (
        "You are a JSON-only parser. Parse the user's input into a JSON object "
        "representing a single table. Output ONLY valid JSON and nothing else. "
        "If multiple tables are in the input, return the first table. "
        "If you cannot find a table, return {\"columns\": [], \"rows\": []}."
    )

    # Provide a strict schema example
    example = {
        "title": "Example Table Title",
        "columns": ["Col A", "Col B", "Col C"],
        "rows": [
            ["a1", "b1", "c1"],
            ["a2", "b2", "c2"]
        ],
        "meta": {"source_format": "markdown"}
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Here is the input to parse:\n\n```\n{text_input}\n```\n\nReturn ONLY JSON with this shape: {example}"}
    ]

    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant", 
        messages=messages,
        temperature=temperature,
        max_completion_tokens=max_tokens,
        top_p=1,
        stream=False,
    )

    # The exact attribute names may differ depending on groq client; adapt as needed
    # We assume the model's reply is in completion.choices[0].message.content or similar
    # Example uses the shape similar to OpenAI/Groq
    try:
        content = completion.choices[0].message.content
    except Exception:
        # fallback if structure differs (match your client)
        content = getattr(completion.choices[0].delta, "content", None) or str(completion)
    return content
