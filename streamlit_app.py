# streamlit_app.py
import streamlit as st
import requests
import json
import pandas as pd
import io
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional, Dict, Any

API_BASE = "http://127.0.0.1:8000/api"

st.set_page_config(page_title="Table Renderer from LLM", layout="wide")
st.title("LLM → Beautiful Table & Charts")
st.write("Send a text description to the LLM, then render the returned data as an aesthetic table or chart.")

# -------------------------
# Helpers
# -------------------------
def try_parse_json(raw: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(raw)
    except Exception:
        return None

def parsed_to_df(parsed: Dict[str, Any]) -> pd.DataFrame:
    """Convert parsed JSON (various shapes) into pandas DataFrame."""
    if isinstance(parsed, dict):
        # Case: {"columns":[...], "rows":[[...]...]}
        if "columns" in parsed and "rows" in parsed:
            cols = parsed.get("columns") or []
            rows = parsed.get("rows") or []
            normalized = []
            for r in rows:
                if isinstance(r, dict):
                    normalized.append([r.get(c, None) for c in cols])
                else:
                    row = list(r)
                    if len(row) < len(cols):
                        row = row + [None] * (len(cols) - len(row))
                    normalized.append(row[:len(cols)])
            return pd.DataFrame(normalized, columns=cols)
        # Case: {"rows":[{...}, {...}], "columns":[optional]}
        if "rows" in parsed and isinstance(parsed["rows"], list) and parsed["rows"]:
            rows = parsed["rows"]
            if all(isinstance(r, dict) for r in rows):
                df = pd.DataFrame(rows)
                if "columns" in parsed and isinstance(parsed["columns"], list):
                    cols = [c for c in parsed["columns"] if c in df.columns]
                    other = [c for c in df.columns if c not in cols]
                    df = df[cols + other]
                return df
    # If parsed is a list-of-lists and first row looks like header:
    if isinstance(parsed, list) and parsed and all(isinstance(r, list) for r in parsed):
        if len(parsed) >= 2:
            cols = parsed[0]
            rows = parsed[1:]
            return parsed_to_df({"columns": cols, "rows": rows})
    # Fallback: if it's a plain list of objects
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        return pd.DataFrame(parsed)

    raise ValueError("Unrecognized JSON shape for conversion to table")

def df_is_mostly_numeric(df: pd.DataFrame, threshold: float = 0.6) -> bool:
    num_cols = df.select_dtypes(include="number").shape[1]
    if df.shape[1] == 0:
        return False
    return (num_cols / df.shape[1]) >= threshold

def choose_chart(df: pd.DataFrame) -> str:
    # If many numeric columns and not too many rows → heatmap
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if len(numeric_cols) >= 2 and df.shape[0] <= 100:
        return "Heatmap"
    # If exactly one numeric and at least one categorical → bar chart
    if len(numeric_cols) == 1:
        cat_cols = [c for c in df.columns if c not in numeric_cols]
        if cat_cols:
            return "Bar"
    # default to table
    return "Table"

def plotly_table_from_df(df: pd.DataFrame) -> go.Figure:
    header_vals = list(df.columns)
    cells = [df[col].astype(str).fillna("") for col in df.columns]
    fig = go.Figure(data=[go.Table(
        header=dict(values=header_vals, fill_color="#0f62fe", font=dict(color="white", size=12)),
        cells=dict(values=cells, fill_color=[["#f8fbff" if i%2==0 else "white" for i in range(df.shape[0])] for _ in df.columns],
                   align="left"))
    ])
    fig.update_layout(margin=dict(l=5,r=5,t=5,b=5), height=400)
    return fig

def plot_heatmap(df: pd.DataFrame) -> go.Figure:
    numeric = df.select_dtypes(include="number")
    if numeric.empty:
        # attempt to coerce
        numeric = df.apply(pd.to_numeric, errors="coerce").select_dtypes(include="number")
    fig = px.imshow(numeric.corr() if numeric.shape[1] > 1 else numeric, text_auto=True)
    fig.update_layout(margin=dict(l=20,r=20,t=40,b=20), height=450)
    return fig

def plot_bar(df: pd.DataFrame, numeric_col: str, cat_col: str) -> go.Figure:
    d = df[[cat_col, numeric_col]].dropna()
    fig = px.bar(d, x=cat_col, y=numeric_col, text=numeric_col)
    fig.update_layout(margin=dict(l=20,r=20,t=40,b=20), height=450)
    return fig

def style_pandas(df: pd.DataFrame) -> str:
    """Return HTML for a styled DataFrame (pandas Styler)."""
    sty = df.style.set_table_styles([
        {"selector":"th","props":[("background-color","#0f62fe"),("color","white"),("font-weight","bold")]},
        {"selector":"td","props":[("padding","8px"),("border","1px solid #eee")]}
    ]).set_properties(**{"text-align":"left"})
    # render to HTML
    return sty.to_html()

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

# -------------------------
# UI: input & call
# -------------------------
with st.sidebar:
    st.header("Settings")
    auto_chart = st.checkbox("Auto-select chart", value=True)
    manual_mode = st.checkbox("Allow manual template/chart selection", value=True)
    st.markdown("**Tip:** If LLM returns plain text, switch to manual mode and copy JSON or edit it.")

text = st.text_area("Enter English description for the table", height=200, placeholder="e.g. A table with columns Name, Age. Rows: Alice - 30; Bob - 25")
if st.button("Send to LLM"):
    if not text.strip():
        st.warning("Enter some text first.")
        st.stop()

    try:
        resp = requests.post(f"{API_BASE}/parse_table", json={"text": text}, timeout=60)
    except Exception as e:
        st.error("Failed to call API")
        st.exception(e)
        st.stop()

    # server returns {"ok": True, "raw": "..."} in your current server impl
    raw = None
    try:
        server_json = resp.json()
        raw = server_json.get("raw") if isinstance(server_json, dict) else json.dumps(server_json)
    except Exception:
        raw = resp.text

    st.subheader("LLM raw output")
    st.code(raw, language=None)

    parsed = try_parse_json(raw)
    if parsed is None:
        st.warning("LLM output is not valid JSON — rendering raw text instead.")
        st.text_area("Raw output (edit to be valid JSON if you want a table)", value=raw, height=200)
        st.stop()

    # convert parsed JSON to DataFrame
    try:
        df = parsed_to_df(parsed)
    except Exception as e:
        st.error("Couldn't convert LLM JSON to a table automatically.")
        st.exception(e)
        st.stop()

    st.success("Parsed JSON converted to DataFrame.")

    # show dataframe preview and provide CSV download
    st.subheader("Data preview")
    st.dataframe(df.head(10))

    csv_bytes = df_to_csv_bytes(df)
    st.download_button("Download CSV", data=csv_bytes, file_name="parsed_table.csv", mime="text/csv")

    # choose visualization
    chosen_chart = None
    if auto_chart:
        chosen_chart = choose_chart(df)
    if manual_mode:
        chosen_chart = st.selectbox("Chart / Template", options=["Table", "Plotly Table", "Heatmap", "Bar"], index=["Table","Plotly Table","Heatmap","Bar"].index(chosen_chart) if chosen_chart in ["Table","Plotly Table","Heatmap","Bar"] else 0)

    # Render according to chosen_chart
    if chosen_chart in ("Table", "Plotly Table"):
        fig = plotly_table_from_df(df)
        st.plotly_chart(fig, use_container_width=True)
        # also offer styled HTML for download/display
        st.markdown("Styled HTML table (alternative):", unsafe_allow_html=True)
        html_str = style_pandas(df)
        st.components.v1.html(html_str, height=400, scrolling=True)
    elif chosen_chart == "Heatmap":
        try:
            fig = plot_heatmap(df)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error("Could not build heatmap")
            st.exception(e)
            st.plotly_chart(plotly_table_from_df(df), use_container_width=True)
    elif chosen_chart == "Bar":
        numerics = df.select_dtypes(include="number").columns.tolist()
        if len(numerics) == 0:
            # try coercion
            coerced = df.apply(pd.to_numeric, errors="coerce")
            numerics = coerced.select_dtypes(include="number").columns.tolist()
            if numerics:
                df[numerics] = coerced[numerics]
        if len(numerics) >= 1:
            numeric_col = st.selectbox("Numeric column (value)", numerics, index=0)
            cat_cols = [c for c in df.columns if c != numeric_col]
            if not cat_cols:
                st.error("No categorical column available to group by.")
                st.plotly_chart(plotly_table_from_df(df), use_container_width=True)
            else:
                cat_col = st.selectbox("Categorical column (category)", cat_cols, index=0)
                fig = plot_bar(df, numeric_col, cat_col)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("No numeric column found for Bar chart.")
            st.plotly_chart(plotly_table_from_df(df), use_container_width=True)

    # export image of the figure (Plotly)
    if 'fig' in locals() and isinstance(fig, (go.Figure, px.Figure)):
        try:
            img_bytes = fig.to_image(format="png", width=1200, height=600, scale=2)
            st.download_button("Download image (PNG)", data=img_bytes, file_name="visual.png", mime="image/png")
        except Exception:
            # to_image might need kaleido; provide hint
            st.info("To enable image export, install 'kaleido' (pip install kaleido).")

else:
    st.info("Enter a description and click 'Send to LLM'. Example: 'A table with columns Name, Age. Rows: Alice - 30; Bob - 25.'")
    st.write("This app will call your FastAPI endpoint, parse the LLM output (if JSON), and show an aesthetic table or chart.")
