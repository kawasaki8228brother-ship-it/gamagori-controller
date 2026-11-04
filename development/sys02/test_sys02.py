"""Synthetic classification tests and independent SHA known vectors."""
from pathlib import Path
import base64
import hashlib
import json
import shutil
import subprocess
import unittest

import json_integrity as sut

HERE = Path(__file__).resolve().parent
CASES = json.loads((HERE / 'fixtures.json').read_text())["cases"]


class FixtureTests(unittest.TestCase):
    pass


def case_test(case):
    def test(self):
        left = base64.b64decode(case['left_b64'], validate=True)
        right = base64.b64decode(case['right_b64'], validate=True)
        expected = case['expected']
        result = sut.compare_bytes(left, right, **case['settings'])
        for axis, key in [('raw_bytes', 'raw'), ('canonical', 'canonical'), ('semantic', 'semantic')]:
            self.assertIs(result['axes'][axis]['match'], expected[key])
        for side in ('left', 'right'):
            self.assertEqual(result[side]['input_status'], expected[side+'_status'])
            self.assertEqual(result[side]['canonical']['status'], expected[side+'_canonical_status'])
            self.assertEqual(result[side]['warnings'], expected[side+'_warnings'])
            canonical = case.get('canonical_utf8_'+side)
            if canonical is not None:
                self.assertEqual(result[side]['canonical']['sha256'], hashlib.sha256(canonical.encode()).hexdigest())
        self.assertFalse(result['production_GO'])
        self.assertEqual(result['left']['LOCK_validity'], 'NOT_EVALUATED')
    return test


for case in CASES:
    setattr(FixtureTests, 'test_'+case['id'].replace('-', '_'), case_test(case))


class ContractTests(unittest.TestCase):
    def test_SHA_empty_and_abc_known_vectors(self):
        vectors = [(b'', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
                   (b'abc', 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'),
                   (b'abc\n', 'edeaaff3f1774ad2888673770c6d64097e391bc362d7d6fb34982ddf0efd18cb'),
                   ('蒲郡・JSON・🚀\n'.encode(), 'fd05a5ce89bd33e176d382cae07de75d2d15f5224d004e7a6290fd4c1bf43309')]
        for raw, expected in vectors:
            with self.subTest(raw=raw):
                self.assertEqual(sut.sha256_bytes(raw), expected)

    def test_SHA_independent_coreutils_backend(self):
        if shutil.which('sha256sum') is None:
            self.skipTest('GNU SHA backend unavailable; no independent-backend PASS')
        for data in [b'', b'abc', b'abc\n', '蒲郡・JSON・🚀\n'.encode()]:
            expected = subprocess.run(['sha256sum'], input=data, capture_output=True, check=True).stdout.decode().split()[0]
            self.assertEqual(sut.sha256_bytes(data), expected)

    def test_expected_hash_axes_true_false_and_absent(self):
        raw = b'{"b":2,"a":1}'
        rh, ch = hashlib.sha256(raw).hexdigest(), hashlib.sha256(b'{"a":1,"b":2}').hexdigest()
        matching = sut.inspect_bytes(raw, expected_raw_sha256=rh.upper(), expected_canonical_sha256=ch)
        self.assertIs(matching['raw']['expected_match'], True)
        self.assertIs(matching['canonical']['expected_match'], True)
        mismatching = sut.inspect_bytes(raw, expected_raw_sha256='0'*64, expected_canonical_sha256='0'*64)
        self.assertIs(mismatching['raw']['expected_match'], False)
        self.assertIs(mismatching['canonical']['expected_match'], False)
        absent = sut.inspect_bytes(raw)
        self.assertIsNone(absent['raw']['expected_match'])
        self.assertIsNone(absent['canonical']['expected_match'])
        # Wrong expectation kind cannot be silently converted into the other axis.
        crossed = sut.inspect_bytes(raw, expected_raw_sha256=ch, expected_canonical_sha256=rh)
        self.assertIs(crossed['raw']['expected_match'], False)
        self.assertIs(crossed['canonical']['expected_match'], False)

    def test_invalid_json_can_still_have_matching_raw_hash(self):
        raw = b'not-json'
        report = sut.inspect_bytes(raw, expected_raw_sha256=hashlib.sha256(raw).hexdigest(), expected_canonical_sha256='0'*64)
        self.assertIs(report['raw']['expected_match'], True)
        self.assertEqual(report['input_status'], 'INVALID_JSON')
        self.assertIsNone(report['canonical']['expected_match'])

    def test_invalid_hash_configuration_rejected_without_echo(self):
        for bad in ['', 'secret-not-a-digest', 'g'*64, 9, True]:
            for field in ('expected_raw_sha256', 'expected_canonical_sha256'):
                with self.subTest(field=field, type=type(bad).__name__):
                    with self.assertRaisesRegex(ValueError, '^EXPECTED_SHA256_INVALID$'):
                        sut.inspect_bytes(b'{}', **{field: bad})

    def test_invalid_limits_rejected(self):
        for settings in [{'max_bytes':0}, {'max_bytes':True}, {'max_bytes':'2'}, {'max_depth':-1}, {'max_depth':129}, {'max_depth':True}, {'max_depth':1.5}]:
            with self.subTest(settings=settings):
                with self.assertRaises(ValueError):
                    sut.compare_bytes(b'{}', b'{}', **settings)
        self.assertEqual(sut.inspect_bytes(b'{}', max_bytes=2, max_depth=0)['input_status'], 'VALID')

    def test_only_bytes_accepted(self):
        for bad in ['{}', None, bytearray(b'{}')]:
            with self.assertRaisesRegex(TypeError, '^BYTES_REQUIRED$'):
                sut.inspect_bytes(bad)
        with self.assertRaises(TypeError):
            sut.compare_bytes(b'{}', None)

    def test_resource_limit_never_hashes_a_truncated_prefix(self):
        raw = b'{"a":1234}'
        report = sut.inspect_bytes(raw, max_bytes=2)
        self.assertEqual(report['input_status'], 'RESOURCE_LIMIT')
        self.assertEqual(report['raw']['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertNotEqual(report['raw']['sha256'], hashlib.sha256(raw[:2]).hexdigest())

    def test_no_values_or_keys_echoed_in_reports(self):
        raw = b'{"SYNTHETIC_PRIVATE_KEY_NAME":"SYNTHETIC_PRIVATE_VALUE"}'
        text = json.dumps(sut.compare_bytes(raw, raw))
        self.assertNotIn('SYNTHETIC_PRIVATE', text)

    def test_all_public_classification_labels_exercised(self):
        statuses, canonical, states = set(), set(), set()
        for f in CASES:
            r = sut.compare_bytes(base64.b64decode(f['left_b64']), base64.b64decode(f['right_b64']), **f['settings'])
            for side in ('left', 'right'):
                statuses.add(r[side]['input_status'])
                canonical.add(r[side]['canonical']['status'])
            states.update(a['state'] for a in r['axes'].values())
        self.assertEqual(statuses, set(sut.INPUT_STATUSES))
        self.assertEqual(canonical, set(sut.CANONICAL_STATUSES))
        self.assertEqual(states, set(sut.AXIS_STATES))


if __name__ == '__main__':
    unittest.main(verbosity=2)
