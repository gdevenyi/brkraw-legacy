"""Unit tests for app.tonifti.header.Header (NIfTI header population).

Pure-unit: the Header class only needs a ScanInfo-shaped object and a
Nifti1Image, so these run offline (no ``data`` marker) with a light stub.
"""
from types import SimpleNamespace

import numpy as np
import nibabel as nib
import pytest

from brkraw_legacy.app.tonifti.header import Header


def _scaninfo(slice_order_scheme='Sequential', num_cycles=1, time_step=0.0,
              num_slices=10, slope=1.0, offset=0.0):
    """A minimal ScanInfo stub carrying only what Header reads."""
    return SimpleNamespace(
        slicepack={'slice_order_scheme': slice_order_scheme,
                   'num_slices_each_pack': [num_slices]},
        cycle={'num_cycles': num_cycles, 'time_step': time_step},
        dataarray={'slope': slope, 'offset': offset},
    )


def _make_header(info, shape=(8, 8, 10), affine=None, scale_mode='header'):
    affine = np.diag([0.3, 0.3, 0.7, 1.0]) if affine is None else affine
    nii = nib.Nifti1Image(np.zeros(shape, dtype='int16'), affine)
    return Header(scaninfo=info, nifti1image=nii, scale_mode=scale_mode).get()


@pytest.mark.parametrize('scheme, expected', [
    ('Sequential', 1),
    ('Reverse_sequential', 2),
    ('Interlaced', 3),
    ('Reverse_interlaced', 4),
])
def test_slice_code_maps_bruker_scheme(scheme, expected):
    """Each known PVM_ObjOrderScheme maps to its NIfTI slice_code (H1 regression).

    The old code's ``... or slice_order_scheme`` short-circuit forced slice_code
    to 0 for every non-empty scheme, so these mappings were dead code.
    """
    out = _make_header(_scaninfo(slice_order_scheme=scheme))
    assert int(out.header['slice_code']) == expected


def test_slice_code_unknown_scheme_is_zero_and_warns():
    info = _scaninfo(slice_order_scheme='User_defined_slice_scheme')
    with pytest.warns(UserWarning, match="slice_code"):
        out = _make_header(info)
    assert int(out.header['slice_code']) == 0


def test_spatial_units_labelled_mm_without_cycles():
    """Non-cine scans must still label spatial units as mm (H4 regression).

    Previously set_xyzt_units ran only in the cycle branch, so ordinary
    anatomical scans were written with NIFTI_UNITS_UNKNOWN.
    """
    out = _make_header(_scaninfo(num_cycles=1))
    assert out.header.get_xyzt_units()[0] == 'mm'


def test_units_and_time_step_with_cycles():
    """Cine/cycle data carries mm + sec and a per-volume time step on pixdim[4]."""
    out = _make_header(_scaninfo(num_cycles=4, time_step=2000.0, num_slices=10))
    assert out.header.get_xyzt_units() == ('mm', 'sec')
    assert float(out.header['pixdim'][4]) == pytest.approx(2.0)      # 2000 ms -> s
    assert float(out.header['slice_duration']) == pytest.approx(2.0 / 10)
