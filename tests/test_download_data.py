import hashlib
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock

spec = importlib.util.spec_from_file_location('download_data', Path(__file__).resolve().parents[1] / 'scripts/download_data.py')
download_data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(download_data)


def response(size):
    remote = MagicMock()
    remote.__enter__.return_value.headers = {'Content-Length': str(size)}
    return remote


def test_existing_file_is_verified_without_download(tmp_path):
    target = tmp_path / '影像.tif'
    target.write_bytes(b'official fixture')
    with patch.object(download_data.urllib.request, 'urlopen', return_value=response(16)), \
         patch.object(download_data.subprocess, 'run') as curl:
        result = download_data.download('sample.tif', target)
    curl.assert_not_called()
    assert result['sha256'] == hashlib.sha256(b'official fixture').hexdigest()
    assert result['bytes'] == 16


def test_truncated_download_does_not_replace_target(tmp_path):
    target = tmp_path / '影像.tif'
    target.write_bytes(b'old')
    def partial_write(*args, **kwargs):
        target.with_suffix('.tif.part').write_bytes(b'short')
    with patch.object(download_data.urllib.request, 'urlopen', return_value=response(100)), \
         patch.object(download_data.subprocess, 'run', side_effect=partial_write):
        import pytest
        with pytest.raises(RuntimeError, match='size mismatch'):
            download_data.download('sample.tif', target)
    assert target.read_bytes() == b'old'


def test_low_disk_space_prevents_transfer(tmp_path):
    target = tmp_path / '影像.tif'
    with patch.object(download_data.urllib.request, 'urlopen', return_value=response(100)), \
         patch.object(download_data.shutil, 'disk_usage', return_value=MagicMock(free=0)), \
         patch.object(download_data.subprocess, 'run') as curl:
        import pytest
        with pytest.raises(RuntimeError, match='disk space'):
            download_data.download('sample.tif', target)
    curl.assert_not_called()
