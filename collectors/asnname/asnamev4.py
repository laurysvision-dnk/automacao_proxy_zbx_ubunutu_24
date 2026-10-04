import sys
import ipaddress
import subprocess
import re
import json

def get_asn_name(asnumber):
    """Retrieve the ASN name using whois commands."""
    try:
        asname = subprocess.check_output(
            ["whois", "-h", "whois.cymru.com", f"AS{asnumber}"],
            universal_newlines=True
        ).splitlines()
        asname = [line for line in asname if "AS Name" not in line]
        if asname:
            asname = asname[0].strip()
        else:
            asname = "NO_NAME"
    except subprocess.CalledProcessError:
        asname = "NO_NAME"

    if asname == "NO_NAME":
        try:
            asname = subprocess.check_output(
                ["whois", asnumber],
                universal_newlines=True
            )
            match = re.search(r"owner:\s*(.*)", asname)
            if match:
                asname = match.group(1).strip()
            else:
                match = re.search(r"network:Org-Name:\s*(.*)", asname)
                if match:
                    asname = match.group(1).strip()
                else:
                    match = re.search(r"netname:\s*(.*)", asname)
                    if match:
                        asname = match.group(1).strip()
                    else:
                        asname = "NO_NAME"
        except subprocess.CalledProcessError:
            asname = "NO_NAME"

    return asname

def snmpwalk(ip, community, port, oid):
    """Perform an SNMP walk and return the results as a list of lines."""
    try:
        result = subprocess.check_output(
            ["snmpwalk", "-On", "-v", "2c", "-c", community, f"{ip}:{port}", oid],
            universal_newlines=True
        )
        return result.splitlines()
    except subprocess.CalledProcessError:
        return []

def peer_index(oid):
    match = re.search(r"\.0\.\d+\.\d+\.1\.4\.([0-9.]+)$", oid)
    return match.group(1) if match else None


def extract_ipv4_and_indices(lines):
    peers = {}
    for line in lines:
        parts = line.split(" = STRING: ", 1)
        if len(parts) != 2:
            continue
        index = peer_index(parts[0])
        address = parts[1].strip().strip('"')
        try:
            valid = ipaddress.ip_address(address).version == 4
        except ValueError:
            valid = False
        if index is not None and valid:
            peers[index] = address
    return peers


def extract_asns_and_indices(lines):
    asns = {}
    for line in lines:
        parts = line.split(" = Gauge32: ", 1)
        if len(parts) != 2:
            continue
        index = peer_index(parts[0])
        if index is not None:
            asns[index] = parts[1].strip()
    return asns


def main():
    if len(sys.argv) != 4:
        print(f"Uso: {sys.argv[0]} <ip> <comunidade> <porta>")
        sys.exit(1)

    ip, community, port = sys.argv[1], sys.argv[2], sys.argv[3]

    ip_results = snmpwalk(ip, community, port, "1.3.6.1.4.1.2011.5.25.177.1.1.2.1.4.0")
    asn_results = snmpwalk(ip, community, port, "1.3.6.1.4.1.2011.5.25.177.1.1.2.1.2.0")

    ipv4_dict = extract_ipv4_and_indices(ip_results)
    asn_dict = extract_asns_and_indices(asn_results)

    output = {"data": []}

    for index, ip in ipv4_dict.items():
        asn = asn_dict.get(index, "UNKNOWN")
        asn_name = get_asn_name(asn) if asn != "UNKNOWN" else "NO_NAME"
        entry = {
            "{#IPV4}": ip,
            "{#IPINDEX}": index,
            "{#ASN}": asn,
            "{#ASNAME}": asn_name
        }
        output["data"].append(entry)

    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()
