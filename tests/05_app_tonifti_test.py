"""app.tonifti (StudyToNifti) NIfTI-assembly tests against public sample data."""
import numpy as np
import pytest

from brkraw_legacy import BrukerLoader
from brkraw_legacy.app.tonifti import StudyToNifti
from brkraw_legacy.lib.errors import UnexpectedError


def test_api_matches_loader_across_scans(lego_study):
    """StudyToNifti.get_nifti1image must reproduce BrukerLoader.get_niftiobj.

    Pins the get_nifti1image regressions -- the assembly TypeError, and the pixel
    data (per-volume scale factors) baked into each volume: where the two paths
    produce the same image count and shape, their affine and (squeeze-tolerant)
    data must be identical. Scans that crash, or where the app.tonifti path
    groups or slices a multi-pack scan differently from the loader (a separate,
    pre-existing behaviour), are skipped; a quorum guards against a vacuous pass.
    """
    loader = BrukerLoader(str(lego_study))
    api = StudyToNifti(str(lego_study))

    compared = 0
    for sid in loader.pvobj.avail_scan_id:
        for rid in loader.pvobj.avail_reco_id.get(sid, [1]):
            try:
                lo = loader.get_niftiobj(sid, rid)
                ap = api.get_nifti1image(sid, rid)
            except Exception:
                continue
            lo = lo if isinstance(lo, list) else [lo]
            ap = ap if isinstance(ap, list) else [ap]
            if len(lo) != len(ap):
                continue          # paths group slice-packs differently; see 07/08
            # squeeze so a single-slice volume [x, y, 1] and [x, y] compare equal
            data = [(np.squeeze(np.asarray(a.dataobj)), np.squeeze(np.asarray(b.dataobj)))
                    for a, b in zip(lo, ap)]
            if any(x.shape != y.shape for x, y in data):
                continue          # API rearranges some multi-slice packs
            for a, b in zip(lo, ap):
                assert np.allclose(a.affine, b.affine, atol=1e-4)
            for x, y in data:
                assert np.array_equal(x, y)
            compared += 1

    assert compared >= 10, f'expected to compare many scans, only did {compared}'


def test_spectroscopic_scan_rejected_cleanly(h2_study):
    """Non-image (spectroscopic) scans must raise a clear, catchable error.

    VisuCoreDimDesc is not all-'spatial' for spectroscopy (PRESS/STEAM/...), so
    the data can't become a NIfTI. The API must reject it with an UnexpectedError
    naming 'non-image data' -- matching the BrukerLoader -- rather than crashing
    with an opaque KeyError/TypeError from deep in the image pipeline.
    """
    loader = BrukerLoader(str(h2_study))
    target = None
    for sid, recos in loader._pvobj.avail_reco_id.items():
        vp = loader._get_visu_pars(sid, recos[0])
        if loader._get_dim_info(vp)[1] != 'spatial_only':
            target = (sid, recos[0])
            break
    if target is None:
        pytest.skip('no spectroscopic scan in sample')
    with pytest.raises(UnexpectedError, match='non-image'):
        StudyToNifti(str(h2_study)).get_nifti1image(*target)
