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

for f in os.listdir("."):
    if "teldat" in f.lower() and "template" in f.lower():
        template_file = f
    elif f.lower().endswith(".csv"):
        csv_file = f

if not template_file:
    raise FileNotFoundError(" Could not find Teldat template file (should contain 'template' in the name).")
if not csv_file:
    raise FileNotFoundError(" Could not find CSV file (should end with .csv).")

print(f" Using template: {template_file}")
print(f" Using CSV: {csv_file}")

# --- Ensure output folder exists ---
OUTPUT_DIR = "output_configs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Load the template ---
with open(template_file, "r", encoding="utf-8") as f:
    template = f.read()

# --- VLAN mask mapping (pwedeng i change)---
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
    reader = csv.DictReader(csvfile)
    for row in reader:
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

        # --- Replace VLANs and DHCP settings ---
        for vlan, mask in VLAN_MASK_MAP.items():
            csv_key = f"VLAN{vlan}"
            if csv_key not in row or not row[csv_key].strip():
                continue

            vlan_ip = row[csv_key].strip()
            network_addr, range_start, range_end = compute_network_info(vlan_ip, mask)

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

        # --- Replace VRF WAN2 route (only inside that section) ---
        new_ip = row.get("VRF_Branch_IP", "").strip()
        new_mask = row.get("VRF_Branch_Mask", "").strip()
        if new_ip and new_mask:
            pattern_vrf_wan2 = r"(vrf wan2[\s\S]*?)(?=^vrf |\Z)"
            match = re.search(pattern_vrf_wan2, config, flags=re.MULTILINE)
            if match:
                vrf_block = match.group(1)
                vrf_block_updated = re.sub(
                    r"route\s+\d+\.\d+\.\d+\.\d+\s+\d+\.\d+\.\d+\.\d+\s+loopback11",
                    f"route {new_ip} {new_mask} loopback11",
                    vrf_block,
                    count=1
                )
                config = config.replace(vrf_block, vrf_block_updated)

        # --- Save output file ---
        safe_store_name = safe_hostname
        output_path = os.path.join(OUTPUT_DIR, f"{safe_store_name}_TELDAT_CONFIG.txt")
        with open(output_path, "w", encoding="utf-8") as out:
            out.write(config)

        print(f"Generated config for {row[store_key].strip()} -> {output_path}")

print("\nAll configurations generated successfully!")
