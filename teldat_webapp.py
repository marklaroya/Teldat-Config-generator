import streamlit as st
import subprocess
import os

st.set_page_config(page_title="Teldat Config Generator", page_icon="⚙️")

st.title("Teldat Router Config Generator")
st.write("Upload your CSV and Template, then auto-generate configs.")

uploaded_csv = st.file_uploader("Upload teldat_sites.csv", type=["csv"])
uploaded_template = st.file_uploader("Upload Teldat template (.txt)", type=["txt"])

if st.button("Generate Configs"):
    if uploaded_csv and uploaded_template:
        with open("teldat_sites.csv", "wb") as f:
            f.write(uploaded_csv.read())
        with open("TELDAT_RS123_TEMPLATE_NEW_2025.txt", "wb") as f:
            f.write(uploaded_template.read())

        result = subprocess.run(["python", "generate_teldat_configs.py"], capture_output=True, text=True)
        if result.returncode == 0:
            st.success(" Configs generated! Check the output_configs folder.")
        else:
            st.error("Error while generating configs.")
            st.text(result.stderr)
    else:
        st.warning("Please upload both CSV and template files first.")
