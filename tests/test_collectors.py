import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


optical = load('optical', 'collectors/externalscripts/discovery_hw_interfaces_opticas_debian11.py')
v4 = load('v4', 'collectors/asnname/asnamev4.py')
v6 = load('v6', 'collectors/asnname/asnamev6.py')
status = load('status', 'collectors/asnname/status_as.py')


class CollectorsTest(unittest.TestCase):
    def test_optical_discovers_100ge_after_row_80_with_physical_index(self):
        names = {str(i): f'"GigabitEthernet0/0/{i}"' for i in range(1, 100)}
        names['120'] = '"100GE0/0/2"'
        physical = {'700': '"100GE0/0/2"'}
        rows = optical.discover(names, {'120': '"UPLINK"'}, physical, 'M')
        self.assertEqual(rows, [{'{#SNMPINDEXOLD}': '120', '{#ENTPHYSICALNAME}': '"100GE0/0/2"', '{#IFALIAS}': '"UPLINK"', '{#SNMPINDEX}': '700', '{#IFALIASOLD}': '"100GE0/0/2"'}])
        self.assertEqual(optical.discover(names, {}, physical, 'S'), [])

    def test_discovery_never_guesses_a_missing_transceiver_index(self):
        self.assertEqual(optical.discover({'1': '"100GE0/0/2"'}, {}, {}, 'M'), [])

    def test_ipv4_ipv6_indices_remain_distinct(self):
        ipv4 = '.1.3.6.1.4.1.2011.5.25.177.1.1.2.1.4.0.1.1.1.4.192.0.2.1 = STRING: "192.0.2.1"'
        ipv6 = '.1.3.6.1.4.1.2011.5.25.177.1.1.2.1.4.0.1.1.2.16.32.1.13.184.0.0.0.0.0.0.0.0.0.0.0.1 = STRING: "2001:db8::1"'
        self.assertEqual(v4.extract_ipv4_and_indices([ipv4]), {'192.0.2.1': '192.0.2.1'})
        self.assertEqual(v6.extract_ipv6_and_indices([ipv6]), {'32.1.13.184.0.0.0.0.0.0.0.0.0.0.0.1': '2001:db8::1'})
        self.assertEqual(v4.extract_ipv4_and_indices([ipv6]), {})
        self.assertEqual(v6.extract_ipv6_and_indices([ipv4]), {})

    def test_bgp_status_uses_community_host_and_port_in_correct_order(self):
        with patch.object(status.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stdout='ok')) as run:
            status.query('snmpget', 'TEST', '192.0.2.1', '161', ['1.2.3'])
        args = run.call_args.args[0]
        self.assertEqual(args[args.index('-c') + 1], 'TEST')
        self.assertIn('192.0.2.1:161', args)
        self.assertEqual(args[-1], '1.2.3')

    def test_unreachable_peer_fails_instead_of_returning_negative_numeric_status(self):
        with patch.object(status.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, stdout='')):
            with self.assertRaisesRegex(ValueError, 'SNMP query failed'):
                status.query('snmpget', 'TEST', '192.0.2.1', '161', ['1.2.3'])

    def test_payload_checksums_match_audited_files(self):
        for name, expected in json.loads((ROOT / 'manifest.json').read_text()).items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected, name)

    def test_beeppp_script_has_linux_shebang_and_valid_python(self):
        script = (ROOT / 'collectors/externalscripts/beeppp_api_zbx.py').read_bytes()
        self.assertTrue(script.startswith(b'#!/usr/lib/zabbix/externalscripts/venv/bin/python3\n'))
        self.assertNotIn(b'\r\n', script)
        compile(script, 'beeppp_api_zbx.py', 'exec')

    def test_installer_rejects_incomplete_pppoe_parameters_before_mutation(self):
        result = subprocess.run(['bash', str(ROOT / 'install.sh'), '--server', '192.0.2.2', '--hostname', 'PRX-TESTE', '--pppoe-target', '198.51.100.1', '--dry-run'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PPPoE exige', result.stderr)

    def test_installer_rejects_config_injection_before_mutation(self):
        result = subprocess.run(['bash', str(ROOT / 'install.sh'), '--server', '192.0.2.2\nDBName=/tmp/evil', '--hostname', 'PRX-TESTE', '--dry-run'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)

    def test_bootstrap_rejects_password_in_git_url(self):
        result = subprocess.run(['bash', str(ROOT / 'bootstrap.sh'), '--repo', 'https://user:TEST@github.com/example/repo.git', '--ref', 'main'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('user:TEST', result.stderr)


if __name__ == '__main__':
    unittest.main()
