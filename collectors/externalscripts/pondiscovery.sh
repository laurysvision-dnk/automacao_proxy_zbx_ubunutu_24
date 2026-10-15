#!/usr/bin/env python3
"""Serve only a recent PON cache for a configured Huawei OLT."""

import ipaddress
import json
from pathlib import Path
import sys
import time

TARGETS_DIR = Path('/etc/alta/olt-huawei/targets.d')
CACHE_DIR = Path('/var/lib/alta-olt-huawei')
LEGACY_ENV = Path('/etc/alta/OLT HUAWEI - SGP/.env')
LEGACY_CACHE = Path('/var/lib/alta-olt-conecta/discovery.json')


def target_from_file(path):
    target = json.loads(path.read_text())
    host_id = str(target['host_id'])
    ipaddress.ip_address(target['ip'])
    port = str(int(target['port']))
    if not host_id.isdecimal() or not 1 <= int(port) <= 65535 or not target['community']:
        raise ValueError('Invalid OLT target')
    return target['ip'], port, target['community'], CACHE_DIR / host_id / 'discovery.json'


def legacy_target():
    values = dict(line.split('=', 1) for line in LEGACY_ENV.read_text().splitlines() if '=' in line)
    ipaddress.ip_address(values['LOCAL_OLT_IP'])
    port = str(int(values['LOCAL_OLT_PORT']))
    if not 1 <= int(port) <= 65535 or not values['LOCAL_OLT_COMMUNITY']:
        raise ValueError('Invalid legacy OLT target')
    return values['LOCAL_OLT_IP'], port, values['LOCAL_OLT_COMMUNITY'], LEGACY_CACHE


def discover(arguments):
    if len(arguments) != 2:
        raise ValueError('Invalid target arguments')
    targets = [target_from_file(path) for path in TARGETS_DIR.glob('*.json')]
    if LEGACY_ENV.exists():
        targets.append(legacy_target())
    matches = [cache for ip, port, community, cache in targets
               if arguments in ([ip, port], [community, ip])]
    if len(matches) != 1:
        raise ValueError('OLT target missing or ambiguous')
    cache = matches[0]
    if time.time() - cache.stat().st_mtime > 1800:
        raise ValueError('Stale PON cache')
    payload = json.loads(cache.read_text())
    if not isinstance(payload, dict) or not isinstance(payload.get('data'), list) or not payload['data']:
        raise ValueError('Empty PON inventory')
    return json.dumps(payload, ensure_ascii=False)


if __name__ == '__main__':
    try:
        print(discover(sys.argv[1:]))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        print('Falha no cache PON ou alvo invalido; verificar integracao central', file=sys.stderr)
        sys.exit(1)
