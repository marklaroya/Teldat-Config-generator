import streamlit as st
import subprocess
import os
import io
import zipfile
import shutil

st.set_page_config(page_title="Teldat Config Generator", page_icon="⚙️")

st.title("⚙️ Teldat Router Config Generator")
st.write("Upload your CSV and Template file to automatically generate configuration files.")

# --- File upload section ---
uploaded_csv = st.file_uploader("📄 Upload teldat_sites.csv", type=["csv"])
uploaded_template = st.file_uploader("📄 Upload Teldat Template (.txt)", type=["txt"])

# --- Generate button ---
if st.button("🚀 Generate Configs"):
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

                st.success("✅ Configs generated successfully!")
                st.download_button(
                    label="⬇️ Download All Configs (ZIP)",
                    data=zip_buffer,
                    file_name="teldat_configs.zip",
                    mime="application/zip"
                )
            else:
                st.error("❌ Error while generating configs.")
                st.text(result.stderr)

        except Exception as e:
            st.error(f"⚠️ Unexpected error: {e}")

    else:
        st.warning("Please upload both CSV and template files first.")
