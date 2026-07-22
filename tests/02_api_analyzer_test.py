"""Unit tests for the analyzers owning and releasing their file handles.

Pure-unit (offline): the readers (DataArrayAnalyzer, ScanInfoAnalyzer) must
close the handles they open instead of leaving them for the garbage collector.
"""
import types
from collections import OrderedDict

import numpy as np

from brkraw_legacy.api.analyzer.dataarray import DataArrayAnalyzer
from brkraw_legacy.api.analyzer.scaninfo import ScanInfoAnalyzer


def test_datarray_analyzer_closes_buffer_after_read(tmp_path):
    """The data-array reader owns its 2dseq handle and closes it after the single
    read; the returned array stays valid once the handle is closed."""
    p = tmp_path / '2dseq'
    p.write_bytes(np.arange(6, dtype='<i2').tobytes())
    fh = open(p, 'rb')
    info = types.SimpleNamespace(
        dataarray={'slope': 1, 'offset': 0, 'dtype': np.dtype('<i2')},
        image={'shape': [6], 'dim_desc': ['spatial']},
        frame_group=None)

    arr = DataArrayAnalyzer(info, fh).get_dataarray()

    assert fh.closed                              # reader released the handle
    assert arr.tolist() == [0, 1, 2, 3, 4, 5]     # data intact after close


def test_scaninfo_analyzer_does_not_leak_fid_handle(tmp_path):
    """Building scan info must not leave the fid handle open. The fid dtype is
    derived from acqp, so the fid buffer is never read -- it must not leak."""
    fid = tmp_path / 'fid'
    fid.write_bytes(b'\x00' * 16)
    opened = []

    def get_fid():
        fh = open(fid, 'rb')
        opened.append(fh)
        return fh

    # debug=True isolates _set_pars, the only place the fid is opened.
    pvobj = types.SimpleNamespace(
        get_fid=get_fid,
        get_visu_pars=lambda reco_id=None: OrderedDict())
    ScanInfoAnalyzer(pvobj, reco_id=1, debug=True)

    assert all(fh.closed for fh in opened), 'fid handle left open'
