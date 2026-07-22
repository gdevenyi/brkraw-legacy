import io
import logging

import pytest

from brkraw_legacy.api.pvobj.base import BaseMethods


def test_fetch_dir_skips_broken_symlink_with_warning(tmp_path):
    """A broken symlink -- unfetched git-annex/DataLad content, or a stray
    .DS_Store -- must not crash directory scanning. It is skipped with a
    warning, and the parallel files/file_sizes lists stay in sync."""
    (tmp_path / 'acqp').write_bytes(b'real data')
    (tmp_path / '.DS_Store').symlink_to(tmp_path / 'no_such_target')  # dangling
    with pytest.warns(UserWarning, match='broken symlink'):
        contents = BaseMethods._fetch_dir(tmp_path)
    entry = contents['.']
    assert 'acqp' in entry['files']                          # real file kept
    assert '.DS_Store' not in entry['files']                 # broken one skipped
    assert len(entry['files']) == len(entry['file_sizes'])   # lists stay in sync


def test_loaddata(dataset):
    logging.info('test')
    for i, pvobj in dataset.items():
        assert len(pvobj.avail) > 0
        for scan_id in pvobj.avail:
            try:
                pvscan = pvobj.get_scan(scan_id)
                logging.info("Scan loaded for %s", pvscan.path[1])
            except Exception:
                raise AssertionError


# --------------------------------------------------------------------------- #
# _is_binary: detecting a data file must not depend on a leading null byte
# --------------------------------------------------------------------------- #

def test_is_binary_detects_headerless_image_data():
    """A 2dseq that fills the FOV (no background) has no null byte in the first
    512 bytes but is still binary. Regression: PV6 FLASH scans whose image data
    starts nonzero crashed conversion with UnicodeDecodeError.
    """
    # 16-bit signed ints, value 2005 -> little-endian bytes D5 07: no null,
    # and 0xD5 is not a valid UTF-8 start byte.
    blob = io.BytesIO(bytes([0xD5, 0x07]) * 300)
    assert BaseMethods._is_binary(blob) is True


def test_is_binary_detects_null_padded_data():
    """A data file with an early null byte is still detected as binary."""
    assert BaseMethods._is_binary(io.BytesIO(b'\x00\x01\x02\x03' * 200)) is True


def test_is_binary_passes_text_parameter_file():
    """A JCAMP-DX parameter file (ASCII, no null) is not binary."""
    text = (b'##TITLE=Parameter List, ParaVision 6.0.1\n'
            b'##$Method=<Bruker:FLASH>\n' + b'##$Foo=<bar>\n' * 40)
    assert BaseMethods._is_binary(io.BytesIO(text)) is False


def test_is_binary_tolerates_multibyte_char_on_sniff_boundary():
    """A multibyte UTF-8 char (e.g. the micro sign in a unit) split across the
    512-byte sniff boundary must not be misread as binary."""
    text = b'a' * 511 + 'µs\n'.encode('utf-8') + b'b' * 100  # 0xC2 at index 511
    assert BaseMethods._is_binary(io.BytesIO(text)) is False