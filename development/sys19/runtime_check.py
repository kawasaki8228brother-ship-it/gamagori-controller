"""Offline SYS-19 reference inspection. Never installs dependencies or starts apps."""
import hashlib
import re


def normalized(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def parse_pins(raw):
    if not isinstance(raw, bytes):
        raise TypeError('BYTES_REQUIRED')
    try:
        lines = raw.decode('utf-8').splitlines()
    except UnicodeDecodeError:
        raise ValueError('INVALID_REQUIREMENTS_UTF8') from None
    pins = {}
    for line in lines:
        if not line.strip():
            continue
        m = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9_.+!-]+)', line)
        if m is None:
            raise ValueError('EXACT_PINS_ONLY_NO_URL_OR_EDITABLE_OR_MARKER')
        name, version = m.groups()
        key = normalized(name)
        if key in pins:
            raise ValueError('DUPLICATE_NORMALIZED_PACKAGE')
        if key == 'pip':
            raise ValueError('PIP_NOT_AN_APPLICATION_PIN')
        pins[key] = version
    if not pins:
        raise ValueError('NO_APPLICATION_PINS')
    return pins


def inspect_runtime(raw, expected_sha256, installed, python_version, target_python='3.14.3'):
    if not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        raise ValueError('REFERENCE_SHA256_INVALID')
    pins = parse_pins(raw)
    actual = {}
    duplicate_names = []
    for name, version in installed:
        n = normalized(name)
        if n in actual:
            duplicate_names.append(n)
        actual[n] = version
    missing = sorted(set(pins)-set(actual))
    extras = sorted(set(actual)-set(pins)-{'pip'})
    mismatches = {n: {'expected':v,'actual':actual[n]} for n,v in pins.items() if n in actual and actual[n]!=v}
    sha = hashlib.sha256(raw).hexdigest()
    matched = sha==expected_sha256 and python_version==target_python and not (missing or extras or mismatches or duplicate_names)
    return {'status':'REFERENCE_ENV_MATCH' if matched else 'ENV_DIFFERS', 'requirements_sha256':sha,
            'requirements_sha_match':sha==expected_sha256,'reference_pin_count':len(pins),
            'python_actual':python_version,'python_target':target_python,'python_exact_match':python_version==target_python,
            'missing':missing,'extras_excluding_pip':extras,'version_mismatches':mismatches,
            'duplicate_installed_names':sorted(set(duplicate_names)), 'pip_excluded_from_pin_comparison':True,
            'installation_performed':False,'Production_compatibility':'NOT_ESTABLISHED','production_GO':False}


def known_vectors():
    vectors = [(b'', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
               (b'abc','ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')]
    return all(hashlib.sha256(raw).hexdigest()==expected for raw,expected in vectors)
