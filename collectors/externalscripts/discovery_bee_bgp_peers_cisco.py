#!/usr/bin/python3
# Adaptado do coletor Bee Solutions, Fernando Almondes (2024), licença MIT.
# Preserva as macros LLD do template Cisco BGP SNMP - ALTA.
import ipaddress
import json
import re
import subprocess
import sys
import time


def main():
    if len(sys.argv) != 5:
        raise ValueError('Expected: <host> <community> <port> <ipv4|ipv6>')
    host, community, port, family = sys.argv[1:]
    ipaddress.ip_address(host)
    if not port.isdigit() or not 1 <= int(port) <= 65535 or family not in ('ipv4', 'ipv6'):
        raise ValueError('Invalid port or address family')
    version = 4 if family == 'ipv4' else 6
    suffix = '1.4' if version == 4 else '2.16'
    oid = '.1.3.6.1.4.1.9.9.187.1.2.5.1.11.' + suffix
    result = subprocess.run(['snmpwalk', '-On', '-v2c', '-t', '2', '-r', '1', '-c', community,
                             host + ':' + port, oid], capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise ValueError('SNMP query failed or timed out')
    rows = []
    names = {}
    deadline = time.monotonic() + 6
    pattern = re.compile(re.escape(oid) + r'\.([0-9.]+)\s*=\s*(?:Gauge32|INTEGER|Unsigned32):\s*(\d+)')
    for index, asn in pattern.findall(result.stdout):
        octets = [int(x) for x in index.split('.')]
        if len(octets) != (4 if version == 4 else 16) or any(x > 255 for x in octets):
            raise ValueError('Invalid BGP peer index')
        peer = str(ipaddress.ip_address(bytes(octets)))
        if asn not in names:
            names[asn] = 'AS' + asn
            remaining = deadline - time.monotonic()
            if remaining > 0.1:
                try:
                    lookup = subprocess.run(['whois', '-h', 'whois.cymru.com', ' -f AS' + asn + ' '],
                                            capture_output=True, text=True, timeout=min(2, remaining))
                    lines = [x.strip() for x in lookup.stdout.splitlines() if x.strip() and 'AS Name' not in x]
                    if lookup.returncode == 0 and lines:
                        names[asn] = lines[-1].split('|')[-1].strip() or names[asn]
                except (OSError, subprocess.TimeoutExpired):
                    pass
        rows.append({'{#SNMPINDEX}': index, '{#PEERIP}': peer, '{#SNMPASN}': asn,
                     '{#BEEPEERNAME}': names[asn], '{#PEERTIPO}': version})
    if not rows and result.stdout.strip() and 'No Such' not in result.stdout and 'No more variables' not in result.stdout:
        raise ValueError('Unrecognized SNMP response')
    print(json.dumps(rows))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print('BGP discovery failed: ' + (str(error) if isinstance(error, ValueError) else 'command unavailable or timed out'), file=sys.stderr)
        sys.exit(1)
