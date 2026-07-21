"""app.tonifti (StudyToNifti / ScanToNifti) NIfTI assembly tests."""
from pathlib import Path

import numpy as np
import pytest
from nibabel.nifti1 import Nifti1Image

from brkraw_legacy import BrukerLoader
from brkraw_legacy.app.tonifti import StudyToNifti

_TESTDATA = Path(__file__).parents[1] / 'testdata'
# A clean single-pack, single-volume 3D scan (no reverse slice order), so the
# assertion holds independently of the multi-pack/reverse-slice affine fixes.
_PV6 = _TESTDATA / 'new-orientation' / '20201230_101610_CIC_LRMousePhantom_1_1'
_CLEAN_SCAN = 13
_PV5 = _TESTDATA / 'new-orientation' / '20201230_CIC_PLANTEST_PV5_001.5S1'


@pytest.mark.skipif(not _PV6.is_dir(),
                    reason='needs testdata/new-orientation/ PV6 study')
def test_get_nifti1image_assembles_and_matches_loader():
    """get_nifti1image must build a NIfTI, not raise TypeError.

    Regression: get_nifti1image called _assemble_nifti1image(dataobj, affine),
    but the static method's signature is (scanobj, dataobj, affine, scale_mode).
    scanobj bound to dataobj, dataobj to affine, and affine was left unfilled, so
    every scan raised `TypeError: ... missing 1 required positional argument:
    'affine'`. The result must be a Nifti1Image whose data and affine match the
    BrukerLoader path.
    """
    loader_img = BrukerLoader(str(_PV6)).get_niftiobj(_CLEAN_SCAN, 1)
    api_img = StudyToNifti(str(_PV6)).get_nifti1image(_CLEAN_SCAN, 1)

    assert isinstance(api_img, Nifti1Image)
    assert np.allclose(loader_img.affine, api_img.affine, atol=1e-4)
    assert np.array_equal(np.asarray(loader_img.dataobj), np.asarray(api_img.dataobj))


# --- BIDS-aligned multi-volume grouping ------------------------------------
# echo -> one image per echo; diffusion/fMRI (and any other non-echo 4th axis)
# -> a single 4D image; plain 3D unchanged. These PV6 scans are single-pack /
# non-reverse, so they hold independently of the multi-pack affine fixes.
_needs_pv6 = pytest.mark.skipif(not _PV6.is_dir(),
                                reason='needs testdata/new-orientation/ PV6 study')


@_needs_pv6
def test_multiecho_splits_into_one_image_per_echo():
    """MSME (echo axis) must yield one 3D image per echo, matching the loader.

    BIDS emits a file per echo (``_echo-1`` ...), so the API returns a list of
    per-echo 3D images rather than a single 4D volume.
    """
    scan = 20  # 3-echo MSME
    loader = BrukerLoader(str(_PV6)).get_niftiobj(scan, 1)
    api = StudyToNifti(str(_PV6)).get_nifti1image(scan, 1)
    assert isinstance(api, list) and len(api) == len(loader) == 3
    for a, b in zip(loader, api):
        assert b.ndim == 3
        assert np.allclose(a.affine, b.affine, atol=1e-4)
        assert np.array_equal(np.asarray(a.dataobj), np.asarray(b.dataobj))


@_needs_pv6
@pytest.mark.parametrize('scan,expected_vols', [(21, 10), (22, 11)])
def test_timeseries_and_diffusion_stay_single_4d(scan, expected_vols):
    """fMRI cycles and diffusion directions stay one 4D image (BIDS dwi/bold)."""
    api = StudyToNifti(str(_PV6)).get_nifti1image(scan, 1)
    assert isinstance(api, Nifti1Image)
    assert api.ndim == 4
    assert api.shape[3] == expected_vols


@_needs_pv6
def test_plain_3d_is_single_image():
    """A plain 3D scan must remain one 3D image (no spurious grouping)."""
    api = StudyToNifti(str(_PV6)).get_nifti1image(13, 1)
    assert isinstance(api, Nifti1Image) and api.ndim == 3


# --- per-volume scale factors ----------------------------------------------

_needs_pv5 = pytest.mark.skipif(not _PV5.is_dir(),
                                reason='needs testdata/new-orientation/ PV5 study')


@_needs_pv5
def test_per_volume_scale_matches_loader():
    """Per-frame slope/offset must be baked into the data, matching the loader.

    PV5 scan 15 (fMRI) has a per-slice/per-cycle slope array that a scalar NIfTI
    scl_slope can't hold; the API previously left the data unscaled. It must now
    apply the factors (reshaped Fortran-order onto the frame axes) so the data is
    byte-identical to the BrukerLoader path.
    """
    ref = BrukerLoader(str(_PV5)).get_niftiobj(15, 1)
    api = StudyToNifti(str(_PV5)).get_nifti1image(15, 1)
    ref = ref[0] if isinstance(ref, list) else ref
    api = api[0] if isinstance(api, list) else api
    assert np.array_equal(np.asarray(ref.dataobj), np.asarray(api.dataobj))


@_needs_pv5
def test_scalar_scale_is_applied_once():
    """A scalar-slope scan stays consistent between apply and header modes.

    'apply' bakes slope into the data; 'header' leaves data raw and records the
    scalar slope in scl_slope. Reconstructing (data * scl_slope) from the header
    result must recover the applied data -- i.e. no double scaling.
    """
    st = StudyToNifti(str(_PV5))
    applied = np.asarray(st.get_nifti1image(16, 1, scale_mode='apply').dataobj)
    hdr_img = st.get_nifti1image(16, 1, scale_mode='header')
    recon = np.asarray(hdr_img.dataobj) * float(hdr_img.header['scl_slope'])
    assert np.allclose(applied, recon, rtol=1e-5, atol=1e-3)
