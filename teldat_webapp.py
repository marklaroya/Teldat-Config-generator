import streamlit as st
import subprocess
import os
import io
import zipfile
import shutil
from datetime import datetime

# -------------------- PAGE CONFIG --------------------
st.set_page_config(page_title="Teldat Config Generator", page_icon="⚙️")

# -------------------- HEADER --------------------
st.markdown(
    """
    <div style='text-align:center; margin-bottom:20px;'>
        <h1 style='margin-bottom:0;'>⚙️ Teldat Router Config Generator</h1>
        <h4 style='color:gray; margin-top:5px;'>Powered by <b>Integrated BigData Technologies corp. </b></h4>
        <hr style='border:1px solid #ccc;'>
    </div>
    """,
    unsafe_allow_html=True
)

st.write("Upload your CSV and Template file to automatically generate router configuration files.")

# -------------------- FILE UPLOAD SECTION --------------------
uploaded_csv = st.file_uploader("📄 Upload teldat_sites.csv", type=["csv"])
uploaded_template = st.file_uploader("📄 Upload Teldat Template (.txt)", type=["txt"])

# -------------------- GENERATE CONFIGS BUTTON --------------------
if st.button(" Generate Configs"):
    if uploaded_csv and uploaded_template:
        try:
            # Save uploaded files
            with open("teldat_sites.csv", "wb") as f:
                f.write(uploaded_csv.read())
            with open("TELDAT_RS123_TEMPLATE_NEW_2025.txt", "wb") as f:
                f.write(uploaded_template.read())

            # Clean up old outputs
            if os.path.exists("output_configs"):
                shutil.rmtree("output_configs")
            os.makedirs("output_configs", exist_ok=True)

            # Run your generator script
            result = subprocess.run(
                ["python", "generate_teldat_configs.py"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                # Create ZIP of generated files
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                    for root, _, files in os.walk("output_configs"):
                        for file in files:
                            zipf.write(os.path.join(root, file), arcname=file)
                zip_buffer.seek(0)

                # Dynamic ZIP filename with date
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                zip_filename = f"teldat_configs_{timestamp}.zip"

                st.success("✅ Configs generated successfully!")
                st.download_button(
                    label="⬇️ Download All Configs (ZIP)",
                    data=zip_buffer,
                    file_name=zip_filename,
                    mime="application/zip"
                )
            else:
                st.error("❌ Error while generating configs.")
                st.text(result.stderr)

        except Exception as e:
            st.error(f"⚠️ Unexpected error: {e}")

    else:
        st.warning("Please upload both CSV and template files first.")

# -------------------- FOOTER --------------------
st.markdown(
    st.image("Integrated BigData Technologies.png", width=120)
    """
    <hr style='margin-top:40px;'>
    <div style='text-align:center; color:gray; font-size:14px;'>
        © 2025 <b>Your Company Name</b>. All rights reserved.<br>
        Developed by <b>Mark Lester Laroya</b>
    </div>
    """,
    unsafe_allow_html=True
)

