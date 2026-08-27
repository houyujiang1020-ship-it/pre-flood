import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('host_diagnostic', Path(__file__).resolve().parents[1] / 'scripts/verify_mapgis_host.py')
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


def test_failure_detected_in_both_native_encodings():
    assert host.authorization_failed('授权验证失败。'.encode('gb18030'))
    assert host.authorization_failed('授权验证失败。'.encode('utf-8'))


def test_liveness_is_not_success():
    assert not host.authorization_failed(b'process initialized')
    assert not host.authorization_failed('开始授权验证'.encode('gb18030'))
