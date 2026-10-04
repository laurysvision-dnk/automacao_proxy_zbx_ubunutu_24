#!/usr/bin/env python3
"""Discover Huawei optical interfaces by matching names, without row limits."""
import json
import re
import subprocess
import sys


def walk(ip, community, port, oid):
    result = subprocess.run(
        ['snmpbulkwalk', '-Cr10', '-On', '-Cc', '-t', '2', '-r', '2', '-v2c', '-c', community, f'{ip}:{port}', oid],
        capture_output=True, text=True, timeout=25, check=True,
    )
    pattern = re.compile(r'^\.' + re.escape(oid) + r'\.(\d+)\s*=\s*STRING:\s*(.*)$')
    rows = {}
    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match:
            rows[match[1]] = match[2].strip()
    return rows


def discover(names, aliases, physical_names, lane):
    physical = {}
    for index, raw_name in physical_names.items():
        physical.setdefault(raw_name.strip('"'), index)
    rows = []
    for index, raw_name in names.items():
        name = raw_name.strip('"')
        if not re.fullmatch(r'(?:100GE|40GE|25GE|10GE|XGigabitEthernet|GigabitEthernet|XGE|GE)\d+(?:/\d+)+', name):
            continue
        multi = name.startswith(('100GE', '40GE'))
        if (lane == 'M' and not multi) or (lane == 'S' and multi):
            continue
        if name not in physical:
            continue
        rows.append({'{#SNMPINDEXOLD}': index, '{#ENTPHYSICALNAME}': raw_name,
                     '{#IFALIAS}': aliases.get(index, '""'), '{#SNMPINDEX}': physical[name],
                     '{#IFALIASOLD}': raw_name})
    return rows


def main():
    if len(sys.argv) not in (4, 5) or (len(sys.argv) == 5 and sys.argv[4] not in ('M', 'S')):
        raise ValueError('Expected: <IP> <community> <port> [M|S]')
    ip, community, port = sys.argv[1:4]
    lane = sys.argv[4] if len(sys.argv) == 5 else None
    names = walk(ip, community, port, '1.3.6.1.2.1.31.1.1.1.1')
    aliases = walk(ip, community, port, '1.3.6.1.2.1.31.1.1.1.18')
    physical = walk(ip, community, port, '1.3.6.1.2.1.47.1.1.1.1.7')
    print(json.dumps(discover(names, aliases, physical, lane)))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, subprocess.SubprocessError) as error:
        print(f'Optical discovery failed: {type(error).__name__}', file=sys.stderr)
        sys.exit(1)
