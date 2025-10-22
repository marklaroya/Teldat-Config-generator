import csv
import os
import re
import ipaddress
import sys
sys.stdout.reconfigure(encoding='utf-8')

# --- Default DHCP range behavior ---
DEFAULT_RESERVE_COUNT = 2  # Reserve last 2 usable IPs (range ends 2 before router)

# --- Auto-detect template and CSV filenames ---
template_file = None
csv_file = None
priority_csv = None

for f in os.listdir("."):
    # Detect template file
    if "teldat" in f.lower() and "template" in f.lower():
        template_file = f
    elif ("flat_vlan" in f.lower() or "inter_vlan" in f.lower()) and "template" in f.lower():
        template_file = f
    # Detect CSV with priority naming
    elif f.lower().endswith(".csv"):
        if "flatvlan" in f.lower() or "intervlan" in f.lower() or "flat_vlan" in f.lower() or "inter_vlan" in f.lower():
            priority_csv = f  # Priority: flatvlan_sites.csv or intervlan_sites.csv
        elif csv_file is None:
            csv_file = f  # Fallback to any CSV

# Use priority CSV if found, otherwise fallback
csv_file = priority_csv if priority_csv else csv_file

if not template_file:
    raise FileNotFoundError("❌ Could not find Teldat template file (should contain 'template' in the name).")
if not csv_file:
    raise FileNotFoundError("❌ Could not find CSV file (should end with .csv, preferably 'flatvlan_sites.csv' or 'intervlan_sites.csv').")

print(f"✅ Using template: {template_file}")
print(f"✅ Using CSV: {csv_file}")

# --- Detect template type ---
with open(template_file, "r", encoding="utf-8") as f:
    template_content = f.read()

# Detect from filename - TEMPLATE NAME TAKES PRIORITY
is_flat_vlan = False
detection_method = ""

# Priority 1: Template filename (HIGHEST PRIORITY)
template_upper = template_file.upper()
if "FLAT_VLAN" in template_upper or "FLAT VLAN" in template_upper or "FLATVLAN" in template_upper:
    is_flat_vlan = True
    detection_method = f"Template name '{template_file}' contains 'FLAT_VLAN'"
elif "INTER_VLAN" in template_upper or "INTER VLAN" in template_upper or "INTERVLAN" in template_upper:
    is_flat_vlan = False
    detection_method = f"Template name '{template_file}' contains 'INTER_VLAN'"
# Check for generic TELDAT templates - use CSV
elif "TELDAT" in template_upper and "TEMPLATE" in template_upper:
    # Fallback to CSV naming for generic TELDAT templates
    csv_lower = csv_file.lower()
    if "flatvlan" in csv_lower or "flat_vlan" in csv_lower:
        is_flat_vlan = True
        detection_method = f"Template is generic TELDAT, CSV name '{csv_file}' suggests FlatVlan"
    elif "intervlan" in csv_lower or "inter_vlan" in csv_lower:
        is_flat_vlan = False
        detection_method = f"Template is generic TELDAT, CSV name '{csv_file}' suggests InterVlan"
    else:
        # Last resort: check template content
        has_vlan_subinterfaces = bool(re.search(r'network bvi0\.\d+', template_content))
        has_single_bvi = re.search(r'network bvi0\s', template_content) and not has_vlan_subinterfaces
        is_flat_vlan = has_single_bvi
        detection_method = f"Template content analysis (single BVI: {has_single_bvi})"
# Priority 2: CSV filename only
elif "flatvlan" in csv_file.lower() or "flat_vlan" in csv_file.lower():
    is_flat_vlan = True
    detection_method = f"CSV name '{csv_file}' contains 'flatvlan'"
elif "intervlan" in csv_file.lower() or "inter_vlan" in csv_file.lower():
    is_flat_vlan = False
    detection_method = f"CSV name '{csv_file}' contains 'intervlan'"
# Priority 3: Template content (fallback)
else:
    has_vlan_subinterfaces = bool(re.search(r'network bvi0\.\d+', template_content))
    has_single_bvi = re.search(r'network bvi0\s', template_content) and not has_vlan_subinterfaces
    is_flat_vlan = has_single_bvi
    detection_method = f"Template content check (single BVI: {has_single_bvi}, VLAN subinterfaces: {has_vlan_subinterfaces})"

template_type = "FlatVlan" if is_flat_vlan else "InterVlan"
print(f"🔍 Detection: {detection_method}")
print(f"📋 Template type: {template_type}")

# Validate CSV naming matches template type
csv_lower = csv_file.lower()
if is_flat_vlan and ("intervlan" in csv_lower or "inter_vlan" in csv_lower):
    print(f"⚠️  WARNING: Using FlatVlan template but CSV name suggests InterVlan: {csv_file}")
elif not is_flat_vlan and ("flatvlan" in csv_lower or "flat_vlan" in csv_lower):
    print(f"⚠️  WARNING: Using InterVlan template but CSV name suggests FlatVlan: {csv_file}")

print()  # Empty line for readability

# --- Ensure output folder exists ---
OUTPUT_DIR = "output_configs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Load the template ---
template = template_content

# --- VLAN mask mapping (for InterVlan only) ---
VLAN_MASK_MAP = {
    "3100": "255.255.255.240",  # /28
    "3137": "255.255.255.240",
    "3138": "255.255.255.224",  # /27
    "3139": "255.255.255.224",
    "3140": "255.255.255.224",
    "3141": "255.255.255.128",  # /25
}


# --- Helper: compute network info ---
def compute_network_info(vlan_ip, mask, reserve_count=DEFAULT_RESERVE_COUNT):
    network = ipaddress.ip_network(f"{vlan_ip}/{mask}", strict=False)
    hosts = list(network.hosts())

    # Default start = first usable
    if len(hosts) == 0:
        range_start = vlan_ip
        range_end = vlan_ip
    else:
        range_start = str(hosts[0])
        # end = last usable - reserve_count
        end_index = len(hosts) - 1 - reserve_count
        if end_index < 0:
            end_index = 0
        range_end = str(hosts[end_index])

    network_addr = str(network.network_address)
    return network_addr, range_start, range_end


# --- Process each store in CSV ---
with open(csv_file, newline='', encoding="utf-8") as csvfile:
    # Read all content
    content = csvfile.read()
    lines = content.strip().split('\n')
    
    if not lines:
        raise ValueError("❌ CSV file is empty")
    
    # Detect delimiter from first line
    first_line = lines[0]
    
    if ',' in first_line and first_line.count(',') > 5:
        delimiter = ','
        delimiter_name = "Comma"
    elif '\t' in first_line and first_line.count('\t') > 5:
        delimiter = '\t'
        delimiter_name = "Tab"
    else:
        # Multiple spaces - need special handling
        delimiter = None
        delimiter_name = "Whitespace (multiple spaces)"
    
    print(f"📊 CSV Delimiter detected: {delimiter_name}\n")
    
    if delimiter:
        # Standard CSV parsing
        import io
        csv_io = io.StringIO(content)
        reader = csv.DictReader(csv_io, delimiter=delimiter)
        rows = list(reader)
    else:
        # Handle whitespace-separated with multiple spaces
        # Split by multiple spaces/tabs
        headers = re.split(r'\s{2,}|\t+', lines[0].strip())
        
        # Clean headers
        headers = [h.strip() for h in headers if h.strip()]
        
        print(f"📋 Detected columns: {', '.join(headers)}\n")
        
        rows = []
        for line in lines[1:]:
            if not line.strip():
                continue
            # Split by multiple spaces/tabs
            values = re.split(r'\s{2,}|\t+', line.strip())
            values = [v.strip() for v in values if v.strip()]
            
            if len(values) == len(headers):
                rows.append(dict(zip(headers, values)))
            else:
                print(f"⚠️  Skipping malformed row (expected {len(headers)} columns, got {len(values)}): {line[:50]}...")
    
    for row in rows:
        store_key = next((k for k in row.keys() if "store" in k.lower()), None)
        if not store_key:
            raise KeyError("❌ CSV must have a 'StoreName' or similar column.")

        config = template

        # --- Replace hostname ---
        safe_hostname = row[store_key].strip().replace(" ", "_")
        config = re.sub(
            r"set hostname\s+\S+",
            f"set hostname {safe_hostname}",
            config
        )
        
        print(f"\n🔧 Processing: {row[store_key].strip()}")
        print(f"   📊 CSV Data Read:")
        if "Tnip1" in row and row["Tnip1"].strip():
            print(f"      Tnip1: {row['Tnip1'].strip()}")
        if "Tnip2" in row and row["Tnip2"].strip():
            print(f"      Tnip2: {row['Tnip2'].strip()}")
        
        # Show all VLAN values being read
        for vlan in ["3100", "3137", "3138", "3139", "3140", "3141"]:
            csv_key = f"VLAN{vlan}"
            if csv_key in row and row[csv_key].strip():
                print(f"      {csv_key}: {row[csv_key].strip()}")

        # --- Replace TNIP1 & TNIP2 ---
        if "Tnip1" in row and row["Tnip1"].strip():
            config = re.sub(
                r"(network tnip1[\s\S]*?ip address )[\d\.]+",
                lambda m: m.group(1) + row["Tnip1"].strip(),
                config
            )
        if "Tnip2" in row and row["Tnip2"].strip():
            config = re.sub(
                r"(network tnip2[\s\S]*?ip address )[\d\.]+",
                lambda m: m.group(1) + row["Tnip2"].strip(),
                config
            )

        # --- Template-specific processing ---
        if is_flat_vlan:
            # --- FlatVlan: Replace single BVI0 and LAN DHCP ---
            # Support multiple column name variations
            lan_ip_key = None
            lan_mask_key = None
            
            # Check for BVI_IP or LAN_IP
            if "BVI_IP" in row and row["BVI_IP"].strip():
                lan_ip_key = "BVI_IP"
                lan_mask_key = "Branch_Mask" if "Branch_Mask" in row else "BVI_Mask"
            elif "LAN_IP" in row and row["LAN_IP"].strip():
                lan_ip_key = "LAN_IP"
                lan_mask_key = "LAN_Mask"
            
            if lan_ip_key and lan_ip_key in row and row[lan_ip_key].strip():
                lan_ip = row[lan_ip_key].strip()
                lan_mask = row.get(lan_mask_key, "255.255.255.192").strip()
                
                network_addr, range_start, range_end = compute_network_info(lan_ip, lan_mask)
                
                print(f"   📊 FlatVlan Network Info:")
                print(f"      BVI IP: {lan_ip}")
                print(f"      Mask: {lan_mask}")
                print(f"      Network: {network_addr}")
                print(f"      DHCP Range: {range_start} - {range_end}")

                # --- BVI0 IP ---
                config = re.sub(
                    r"(network bvi0[\s\S]*?ip address )[\d\.]+",
                    lambda m, ip=lan_ip: m.group(1) + ip,
                    config
                )

                # --- DHCP network for "subnet lan" ---
                config = re.sub(
                    r"(subnet lan [\d]+ network )[\d\.]+ [\d\.]+",
                    lambda m, net=network_addr, mk=lan_mask: m.group(1) + f"{net} {mk}",
                    config
                )

                # --- DHCP range ---
                config = re.sub(
                    r"(subnet lan [\d]+ range )[\d\.]+ [\d\.]+",
                    lambda m, start=range_start, end=range_end: m.group(1) + f"{start} {end}",
                    config
                )

                # --- DHCP router ---
                config = re.sub(
                    r"(subnet lan [\d]+ router )[\d\.]+",
                    lambda m, ip=lan_ip: m.group(1) + ip,
                    config
                )
                
                # --- VRF WAN2 route for FlatVlan: CRITICAL FIX ---
                # Must use the SAME network address as DHCP (calculated from BVI_IP)
                print(f"   🔧 VRF Route Update:")
                print(f"      Target: route {network_addr} {lan_mask} loopback11")
                
                # Pattern to find any route with loopback11
                route_pattern = r"route\s+[\d\.]+\s+[\d\.]+\s+loopback11"
                match = re.search(route_pattern, config)
                
                if match:
                    old_route = match.group(0)
                    new_route = f"route {network_addr} {lan_mask} loopback11"
                    
                    # Replace only the first occurrence (should be in vrf wan2)
                    config = config.replace(old_route, new_route, 1)
                    
                    print(f"      ✅ VRF Route Updated!")
                    print(f"         Old: {old_route}")
                    print(f"         New: {new_route}")
                    
                    # Verify replacement worked
                    verify_match = re.search(r"route\s+[\d\.]+\s+[\d\.]+\s+loopback11", config)
                    if verify_match and verify_match.group(0) == new_route:
                        print(f"      ✓ Verification: SUCCESS")
                    else:
                        print(f"      ⚠️  Verification: Route found but may not match expected")
                else:
                    print(f"      ❌ ERROR: Could not find route with 'loopback11' in template!")
                    print(f"      💡 Tip: Check template for line like 'route X.X.X.X X.X.X.X loopback11'")

        else:
            # --- InterVlan: Replace VLANs and DHCP settings ---
            for vlan, mask in VLAN_MASK_MAP.items():
                csv_key = f"VLAN{vlan}"
                if csv_key not in row or not row[csv_key].strip():
                    continue

                vlan_ip = row[csv_key].strip()
                network_addr, range_start, range_end = compute_network_info(vlan_ip, mask)
                
                print(f"   ✏️  Updating {csv_key}: {vlan_ip} → Network: {network_addr}/{mask}")

                # --- BVI IP ---
                config = re.sub(
                    rf"(network bvi0\.{vlan}[\s\S]*?ip address )[\d\.]+",
                    lambda m, ip=vlan_ip: m.group(1) + ip,
                    config
                )

                # --- DHCP network ---
                config = re.sub(
                    rf"(subnet vlan{vlan} [\d]+ network )[\d\.]+ [\d\.]+",
                    lambda m, net=network_addr, mk=mask: m.group(1) + f"{net} {mk}",
                    config
                )

                # --- DHCP range ---
                config = re.sub(
                    rf"(subnet vlan{vlan} [\d]+ range )[\d\.]+ [\d\.]+",
                    lambda m, start=range_start, end=range_end: m.group(1) + f"{start} {end}",
                    config
                )

                # --- DHCP router ---
                config = re.sub(
                    rf"(subnet vlan{vlan} [\d]+ router )[\d\.]+",
                    lambda m, ip=vlan_ip: m.group(1) + ip,
                    config
                )

        # --- Replace VRF WAN2 route (for InterVlan only, FlatVlan handles it above) ---
        if not is_flat_vlan:
            new_ip = row.get("VRF_Branch_IP", "").strip()
            new_mask = row.get("VRF_Branch_Mask", "").strip()
            if new_ip and new_mask:
                pattern_vrf_wan2 = r"(vrf wan2[\s\S]*?)(?=^vrf |\Z)"
                match = re.search(pattern_vrf_wan2, config, flags=re.MULTILINE)
                if match:
                    vrf_block = match.group(1)
                    vrf_block_updated = re.sub(
                        r"route\s+[\d\.]+\s+[\d\.]+\s+loopback11",
                        f"route {new_ip} {new_mask} loopback11",
                        vrf_block,
                        count=1
                    )
                    config = config.replace(vrf_block, vrf_block_updated)
                    print(f"   ✏️  VRF Route: {new_ip} {new_mask} loopback11")

        # --- Save output file ---
        safe_store_name = safe_hostname
        output_path = os.path.join(OUTPUT_DIR, f"{safe_store_name}_TELDAT_CONFIG.txt")
        with open(output_path, "w", encoding="utf-8") as out:
            out.write(config)

        print(f"✅ Saved: {output_path}")

print(f"\n🎉 All {template_type} configurations generated successfully!")