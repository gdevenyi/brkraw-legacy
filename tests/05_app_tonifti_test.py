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
