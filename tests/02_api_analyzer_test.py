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


# --------------------------------------------------------------------------- #
# A derived reconstruction inherits acquisition params it omits (VisuAcq*)
# --------------------------------------------------------------------------- #

class _TwoRecoPv:
    """pvobj stand-in with a primary and a derived reconstruction."""
    avail = [1, 2]

    def __init__(self, primary, derived):
        self._vp = {1: primary, 2: derived}

    def get_visu_pars(self, reco_id):
        return self._vp[reco_id]


def test_derived_reco_inherits_only_acquisition_params():
    """A derived reconstruction (e.g. a computed T2/ADC map) inherits the
    acquisition-level VisuAcq* parameters it omits from the primary reco, while
    keeping its own reconstruction geometry."""
    primary = {'VisuAcqGradEncoding': ['read_enc', 'phase_enc'],
               'VisuAcqImagePhaseEncDir': ['col_dir'],
               'VisuCoreSize': [256, 256]}
    derived = {'VisuCoreSize': [128, 128]}   # no VisuAcq*; its own smaller matrix

    ScanInfoAnalyzer._inherit_acq_params(_TwoRecoPv(primary, derived), 2, derived)

    assert derived['VisuAcqGradEncoding'] == ['read_enc', 'phase_enc']  # inherited
    assert derived['VisuAcqImagePhaseEncDir'] == ['col_dir']            # inherited
    assert derived['VisuCoreSize'] == [128, 128]                        # kept, not primary's


def test_primary_reco_params_untouched():
    """The primary reconstruction has nothing to inherit and is unchanged."""
    primary = {'VisuAcqGradEncoding': ['read_enc'], 'VisuCoreSize': [256, 256]}
    ScanInfoAnalyzer._inherit_acq_params(_TwoRecoPv(primary, {}), 1, primary)
    assert set(primary) == {'VisuAcqGradEncoding', 'VisuCoreSize'}
