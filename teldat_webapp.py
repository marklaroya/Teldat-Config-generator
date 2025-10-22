import streamlit as st
import subprocess
import os
import io
import zipfile
import shutil
from datetime import datetime

# -------------------- PAGE CONFIG --------------------
st.set_page_config(
    page_title="Teldat Config Generator",
    page_icon="https://github.com/marklaroya/Teldat-Config-generator/blob/main/Integrated%20BigData%20Technologies.png?raw=true",
    layout="centered"
)

# -------------------- HEADER WITH CENTERED LOGO --------------------
st.markdown(
    """
    <div style='text-align:center; margin-top:-30px;'>
        <img src='https://github.com/marklaroya/Teldat-Config-generator/blob/main/Integrated%20BigData%20Technologies.png?raw=true'
             width='90' style='margin-bottom:10px; border-radius:10px;'>
        <h1 style='margin-bottom:0; color:white;'>⚙️ Teldat Config Generator</h1>
        <h4 style='color:gray; margin-top:5px;'>InterVlan & FlatVlan Support</h4>
        <p style='color:#888; font-size:14px;'>By <b>Integrated BigData Technologies Corp.</b></p>
        <hr style='border:1px solid #555; margin-top:15px;'>
    </div>
    """,
    unsafe_allow_html=True
)

st.write("Upload your CSV and Template file to automatically generate router configuration files.")

# -------------------- TEMPLATE TYPE INFO --------------------
with st.expander("ℹ️ Template Types & CSV Requirements"):
    st.markdown("""
    ### **InterVlan Template**
    - Multiple VLANs (3100, 3137-3141)
    - Required CSV columns: `StoreName`, `Tnip1`, `Tnip2`, `VLAN3100`, `VLAN3137`, etc.
    - Recommended naming: `INTER_VLAN_RS123_TEMPLATE.txt` or `INTER_VLAN_M1_TEMPLATE.txt`
    
    ### **FlatVlan Template**
    - Single LAN subnet
    - Required CSV columns: `StoreName`, `Tnip1`, `Tnip2`, `BVI_IP`, `Branch_Mask`
    - Alternative columns: `LAN_IP`, `LAN_Mask` (also supported)
    - Note: VRF route is auto-calculated from BVI_IP network (no need for VRF_Branch_IP)
    - Recommended naming: `FLAT_VLAN_RS123_TEMPLATE.txt` or `FLAT_VLAN_M1_TEMPLATE.txt`
    
    ### **Recommended File Naming Convention**
    - ✅ `FLAT_VLAN_RS123_TEMPLATE.txt` → FlatVlan with RS123 model
    - ✅ `FLAT_VLAN_M1_TEMPLATE.txt` → FlatVlan with M1 model
    - ✅ `INTER_VLAN_RS123_TEMPLATE.txt` → InterVlan with RS123 model
    - ✅ `INTER_VLAN_M1_TEMPLATE.txt` → InterVlan with M1 model
    - ✅ `flatvlan_sites.csv` or `intervlan_sites.csv` for CSV files
    
    ### **Common Columns (Both)**
    - `VRF_Branch_IP`, `VRF_Branch_Mask` (optional for InterVlan, not needed for FlatVlan)
    """)

# -------------------- FILE UPLOAD SECTION --------------------
col1, col2 = st.columns(2)

with col1:
    uploaded_csv = st.file_uploader("📄 Upload CSV File", type=["csv"])
    
with col2:
    uploaded_template = st.file_uploader("📄 Upload Template File", type=["txt"])

if uploaded_template:
    template_name = uploaded_template.name.upper()
    if "FLAT_VLAN" in template_name or "FLATVLAN" in template_name:
        st.info("🔷 **FlatVlan** template detected")
    elif "INTER_VLAN" in template_name or "INTERVLAN" in template_name:
        st.info("🔶 **InterVlan** template detected")
    else:
        st.warning("⚠️ Template type unclear. Script will auto-detect based on content.")

# -------------------- GENERATE CONFIGS BUTTON --------------------
if st.button("🚀 Generate Configs", type="primary"):
    if uploaded_csv and uploaded_template:
        try:
            with st.spinner("⏳ Generating configurations..."):
                # CRITICAL: Clean up old template and CSV files to prevent wrong file detection
                for f in os.listdir("."):
                    # Delete old template files
                    if f.lower().endswith(".txt") and ("template" in f.lower() or "teldat" in f.lower()):
                        try:
                            os.remove(f)
                            print(f"🗑️ Removed old template: {f}")
                        except:
                            pass
                    # Delete old CSV files
                    elif f.lower().endswith(".csv"):
                        try:
                            os.remove(f)
                            print(f"🗑️ Removed old CSV: {f}")
                        except:
                            pass
                
                # Save files with their ORIGINAL names to preserve detection logic
                csv_filename = uploaded_csv.name
                template_filename = uploaded_template.name
                
                # Save CSV
                with open(csv_filename, "wb") as f:
                    f.write(uploaded_csv.read())
                
                # Save template
                with open(template_filename, "wb") as f:
                    f.write(uploaded_template.read())

                # Clean up old outputs
                if os.path.exists("output_configs"):
                    shutil.rmtree("output_configs")
                os.makedirs("output_configs", exist_ok=True)

                # Run your generator script
                result = subprocess.run(
                    ["python", "generate_teldat_configs.py"],
                    capture_output=True,
                    text=True,
                    encoding='utf-8'
                )

                if result.returncode == 0:
                    # Display script output
                    st.success("✅ Configs generated successfully!")
                    with st.expander("📋 View Generation Log"):
                        st.code(result.stdout, language="text")
                    
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

                    # Download button
                    st.download_button(
                        label="⬇️ Download All Configs (ZIP)",
                        data=zip_buffer,
                        file_name=zip_filename,
                        mime="application/zip",
                        use_container_width=True
                    )
                    
                    # Show file count
                    config_files = [f for f in os.listdir("output_configs") if f.endswith(".txt")]
                    st.metric("Generated Configs", len(config_files))
                    
                else:
                    st.error("❌ Error while generating configs.")
                    with st.expander("🔍 View Error Details"):
                        st.code(result.stderr, language="text")
                        if result.stdout:
                            st.code(result.stdout, language="text")

        except Exception as e:
            st.error(f"⚠️ Unexpected error: {e}")
            st.exception(e)

    else:
        st.warning("⚠️ Please upload both CSV and template files first.")

# -------------------- SAMPLE CSV TEMPLATES --------------------
with st.expander("📥 Download Sample CSV Templates"):
    st.markdown("### InterVlan CSV Sample")
    intervlan_sample = """StoreName,Tnip1,Tnip2,VLAN3100,VLAN3137,VLAN3138,VLAN3139,VLAN3140,VLAN3141,VRF_Branch_IP,VRF_Branch_Mask
Store_001,11.11.0.10,11.12.0.10,192.168.10.1,192.168.20.1,192.168.30.1,192.168.40.1,192.168.50.1,192.168.60.1,10.0.1.0,255.255.255.0"""
    
    st.download_button(
        label="Download InterVlan Sample CSV",
        data=intervlan_sample,
        file_name="sample_intervlan.csv",
        mime="text/csv"
    )
    
    st.markdown("### FlatVlan CSV Sample")
    flatvlan_sample = """StoreName,Tnip1,Tnip2,BVI_IP,Branch_Mask
Store_001,11.11.0.10,11.12.0.10,172.17.90.142,255.255.255.192
Store_002,11.11.0.11,11.12.0.11,172.17.91.142,255.255.255.192"""
    
    st.download_button(
        label="Download FlatVlan Sample CSV",
        data=flatvlan_sample,
        file_name="sample_flatvlan.csv",
        mime="text/csv"
    )

# -------------------- FOOTER --------------------
st.markdown(
    """
    <hr style='margin-top:40px;'>
    <div style='text-align:center; color:gray; font-size:14px;'>
        © 2025 <b>Integrated BigData Technologies Corp.</b> All rights reserved.<br>
        Developed by <b>Integrated BigData Technologies Corp.</b>
    </div>
    """,
    unsafe_allow_html=True
)