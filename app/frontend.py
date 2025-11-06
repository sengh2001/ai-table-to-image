import streamlit as st
import requests
from io import BytesIO
from PIL import Image

API_URL = "http://localhost:8000/parse_and_render"

st.title("AI Table to Image Generator")

text_input = st.text_area("Enter your text:", height=200)

if st.button("Generate Image"):
    if not text_input.strip():
        st.warning("Please enter some text.")
    else:
        with st.spinner("Generating table image..."):
            response = requests.post(API_URL, json={"text": text_input})
            st.write("### Debug Info:")
            st.write("Status Code:", response.status_code)

            if response.status_code == 200:
                try:
                    img = Image.open(BytesIO(response.content))  # ✅ handle binary
                    st.image(img, caption="Generated Table", use_container_width=True)
                except Exception as e:
                    st.error(f"Could not decode image: {e}")
            else:
                st.error(f"Backend returned error: {response.status_code}")
                st.code(response.text)
