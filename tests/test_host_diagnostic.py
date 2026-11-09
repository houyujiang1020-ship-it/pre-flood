import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

spec = importlib.util.spec_from_file_location('host_diagnostic', Path(__file__).resolve().parents[1] / 'scripts/verify_mapgis_host.py')
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


def test_failure_detected_in_both_native_encodings():
    assert host.authorization_failed('授权验证失败。'.encode('gb18030'))
    assert host.authorization_failed('授权验证失败。'.encode('utf-8'))


def test_liveness_is_not_success():
    assert not host.authorization_failed(b'process initialized')
    assert not host.authorization_failed('开始授权验证'.encode('gb18030'))
    assert not host.authorization_succeeded('开始授权验证'.encode('gb18030'))


def test_license_success_requires_explicit_native_message():
    assert host.authorization_succeeded('授权验证成功。'.encode('gb18030'))
    assert host.authorization_succeeded('授权验证成功。'.encode('utf-8'))
    assert not host.authorization_succeeded(b'process initialized')
