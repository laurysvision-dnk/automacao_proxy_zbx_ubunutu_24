import ipaddress
import re
import subprocess
import sys

ADDRESS_OID = '1.3.6.1.4.1.2011.5.25.177.1.1.2.1.4.0'
STATUS_OID = '1.3.6.1.4.1.2011.5.25.177.1.1.2.1.5.0'


def query(command, community, host, port, oids):
    arguments = [command, '-On', '-Oe', '-v2c', '-t', '2', '-r', '1', '-c', community, f'{host}:{port}']
    if command == 'snmpbulkwalk':
        arguments += ['-Cr10']
    result = subprocess.run(arguments + oids, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise ValueError('SNMP query failed')
    return result.stdout


def find_peer_indices(output, peer):
    wanted = ipaddress.ip_address(peer)
    pattern = re.compile(r'^\.' + re.escape(ADDRESS_OID) + r'\.([0-9.]+)\s*=\s*STRING:\s*(.*)$')
    indices = []
    for line in output.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        try:
            address = ipaddress.ip_address(match[2].strip().strip('"'))
        except ValueError:
            continue
        if address == wanted:
            indices.append(match[1])
    return indices


def main():
    if len(sys.argv) != 5:
        raise ValueError('Expected: <community> <host> <port> <peer>')
    community, host, port, peer = sys.argv[1:]
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ValueError('Invalid SNMP port')
    indices = find_peer_indices(query('snmpbulkwalk', community, host, port, [ADDRESS_OID]), peer)
    if not indices:
        raise ValueError('BGP peer not found in SNMP table')
    response = query('snmpget', community, host, port, [STATUS_OID + '.' + index for index in indices])
    states = []
    for line in response.splitlines():
        match = re.search(r'=\s*INTEGER:\s*(\d+)\s*$', line)
        if not match or not 1 <= int(match[1]) <= 6:
            raise ValueError('Invalid BGP state returned by SNMP')
        states.append(int(match[1]))
    if len(states) != len(indices) or len(set(states)) != 1:
        raise ValueError('Ambiguous BGP peer state')
    print(states[0])


if __name__ == '__main__':
    try:
        main()
    except (ValueError, subprocess.SubprocessError) as error:
        message = str(error) if isinstance(error, ValueError) else 'SNMP query timed out'
        print('BGP status collection failed: ' + message, file=sys.stderr)
        sys.exit(1)
