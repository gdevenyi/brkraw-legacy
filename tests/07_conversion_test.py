"""Regression tests for raw->NIfTI conversion against local sample datasets.

These exercise parsing/conversion paths that previously crashed or produced
wrong output. They are skipped when the relevant sample data is absent or has
been stripped to header-only stubs.
"""
import warnings
from pathlib import Path

import pytest

from brkraw import BrukerLoader
from brkraw.lib.utils import convert_data_to

_TESTDATA = Path(__file__).parents[1] / 'testdata'


# Sample datasets are organized as testdata/<pv>/<full|headers>/<name>/
_DATASETS = {
    '0.2H2': 'pv5/full/0.2H2',
    'lego_phantom': 'pv6/full/lego_phantom',
    'mch_dev_022': 'pv6/full/mch_dev_022',
}


def _study(name):
    path = _TESTDATA / _DATASETS.get(name, name)
    if not (path.is_dir() and (path / 'subject').exists()):
        pytest.skip('sample dataset {} not available'.format(name))
    return BrukerLoader(str(path))


def _has_real_2dseq(loader, scan_id, reco_id, min_bytes=1024):
    """Skip helper: sample fixtures sometimes ship truncated 2dseq stubs."""
    for r in loader._pvobj._2dseq.get(scan_id, []):
        if r.reco_id == reco_id:
            try:
                return Path(r.idx).stat().st_size >= min_bytes
            except (OSError, AttributeError):
                return False
    return False


# --------------------------------------------------------------------------- #
# Parameter parser: string literals <...> are opaque (FILE_FORMAT.md 2.2)
# --------------------------------------------------------------------------- #

def test_struct_array_with_parens_in_comment():
    """A struct whose <...> comment contains parens/commas must not corrupt parsing."""
    raw = '(5, <FG_ISA>, <T2 relaxation: y=A+C*exp(-t/T2)>, 0, 2)'
    parsed = convert_data_to(raw, '( 1 )')
    assert parsed == [[5, 'FG_ISA', 'T2 relaxation: y=A+C*exp(-t/T2)', 0, 2]]


def test_multi_struct_array_with_parens_in_comment():
    raw = ('(5, <FG_ISA>, <T2 relaxation: y=A+C*exp(-t/T2)>, 0, 2) '
           '(6, <FG_MOVIE>, <vtr>, 2, 2)')
    parsed = convert_data_to(raw, '( 2 )')
    assert parsed[0] == [5, 'FG_ISA', 'T2 relaxation: y=A+C*exp(-t/T2)', 0, 2]
    assert parsed[1] == [6, 'FG_MOVIE', 'vtr', 2, 2]


# --------------------------------------------------------------------------- #
# Frame-group parsing no longer crashes on single/complex-comment groups
# --------------------------------------------------------------------------- #

def test_frame_group_info_parses_all_scans():
    d = _study('0.2H2')
    for sid, recos in d._pvobj.avail_reco_id.items():
        for rid in recos:
            vp = d._get_visu_pars(sid, rid)
            fg = d._get_frame_group_info(vp)        # must not raise
            assert isinstance(fg['group_id'], list)


# --------------------------------------------------------------------------- #
# Multi-slice-package with heterogeneous pack sizes (e.g. 5/3/5 slices)
# --------------------------------------------------------------------------- #

def test_multi_slicepack_heterogeneous():
    d = _study('lego_phantom')
    sid, rid = 8, 1
    if not _has_real_2dseq(d, sid, rid):
        pytest.skip('scan 8 2dseq is a stub')
    vp = d._get_visu_pars(sid, rid)
    counts = d._get_slice_info(vp)['num_slices_each_pack']
    assert counts == [5, 3, 5]
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        objs = d.get_niftiobj(sid, rid)
    assert [o.shape[2] for o in objs] == [5, 3, 5]
    # slices must total the frame count with no loss/overlap
    assert sum(o.shape[2] for o in objs) == 13


# --------------------------------------------------------------------------- #
# Spectroscopic / non-image data is rejected cleanly, not with a cryptic crash
# --------------------------------------------------------------------------- #

def test_spectroscopic_rejected_cleanly():
    d = _study('0.2H2')
    # find a spectroscopic scan
    target = None
    for sid, recos in d._pvobj.avail_reco_id.items():
        vp = d._get_visu_pars(sid, recos[0])
        if d._get_dim_info(vp)[1] != 'spatial_only':
            target = (sid, recos[0])
            break
    if target is None:
        pytest.skip('no spectroscopic scan in sample')
    with pytest.raises(Exception, match='non-image data'):
        d.get_niftiobj(*target)


# --------------------------------------------------------------------------- #
# Non-PvDataset directory (no subject file) does not raise a TypeError
# --------------------------------------------------------------------------- #

def test_non_pvdataset_directory_is_clean():
    pv360 = _TESTDATA / 'pv360' / 'full' / 'std_data'
    if not pv360.is_dir():
        pytest.skip('pv360/full/std_data not available')
    loader = BrukerLoader(str(pv360))   # must not raise
    # the collection root has no scans of its own -> not a single PvDataset
    assert loader.is_pvdataset is False


# --------------------------------------------------------------------------- #
# Standalone scan/EXPNO directory (no subject file) loads as a one-scan dataset
# --------------------------------------------------------------------------- #

def test_standalone_scan_directory_loads():
    scan = _TESTDATA / 'pv360' / 'full' / 'std_data' / 'T1_FLASH'
    if not (scan / 'acqp').exists():
        pytest.skip('pv360 T1_FLASH scan not available')
    if not _has_real_2dseq(BrukerLoader(str(scan)), 1, 1):
        pytest.skip('T1_FLASH 2dseq is an unpulled LFS stub')
    d = BrukerLoader(str(scan))
    assert d.is_pvdataset is True
    assert d.num_scans == 1
    assert d.pvobj.avail_reco_id == {1: [1]}
    assert d.pvobj.subj_id is None            # no subject file
    nii = d.get_niftiobj(1, 1)
    assert nii.shape == (384, 384, 9)
