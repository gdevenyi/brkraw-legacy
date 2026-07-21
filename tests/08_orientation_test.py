"""Subject orientation regression tests.

Covers the defect found by reviewing the affine code against FILE_FORMAT.md and
the ParaVision 6.0.1 Software Manual: ``Foot_Left``/``Foot_Right`` (and their
``Tail_*`` aliases) were given the *head-first* rotation in the legacy path,
dropping the feet-first entry flip -- so the two conversion paths disagreed.

Also pins the subject-type behaviour that the manual makes look wrong. S1.3.6.2
says the Primate system "is also used for subject specimen Unknown", which reads
as though an absent ``VisuSubjectType`` (i.e. all PV5 data) should use the biped
frame. Changing it to that regresses real PV5 rodent conversions; see
``test_absent_subject_type_uses_rodent_frame`` and the cross-study checks at the
bottom of this file, which are the evidence.
"""
from pathlib import Path

import numpy as np
import pytest

from brkraw_legacy.api.analyzer.affine import AffineAnalyzer
from brkraw_legacy.lib.orient import apply_rotate
from brkraw_legacy.lib.subject_orient import (
    SUBJECT_POSE_ROTATION,
    get_pose_rotation,
    normalize_subject_type,
    uses_quadruped_frame,
)

PI = np.pi
SIDES = ['Supine', 'Prone', 'Left', 'Right']
_TESTDATA = Path(__file__).parents[1] / 'testdata'


def _pv5_study():
    """Any PV5 study directory under ./testdata, or None."""
    for base in (_TESTDATA / 'new-orientation', _TESTDATA / 'pv5' / 'full'):
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            if (d / 'subject').is_file() and 'PV5' in d.name.upper():
                return d
    pv5 = _TESTDATA / 'pv5' / 'full'
    if pv5.is_dir():
        for d in sorted(pv5.iterdir()):
            if (d / 'subject').is_file():
                return d
    return None

#: Head_Prone is the reference (identity). The other head-first poses differ by
#: a roll about the bore/head-foot axis.
HEAD_FIRST = {
    'Prone': {},
    'Supine': {'rad_z': PI},
    'Left': {'rad_z': PI / 2},
    'Right': {'rad_z': -PI / 2},
}


def _rot(**kwargs):
    """3x3 rotation, same composition as apply_rotate (Rz @ Ry @ Rx)."""
    return apply_rotate(np.eye(4), **kwargs)[:3, :3]


def _expected(pose):
    """Derived truth: Foot_X == Ry(pi) @ Head_X (180 deg end-for-end entry flip)."""
    part, side = pose.split('_')
    head = _rot(**HEAD_FIRST[side])
    if part == 'Head':
        return head
    return _rot(rad_y=PI) @ head


ALL_POSES = ['{}_{}'.format(p, s) for p in ('Head', 'Foot', 'Tail') for s in SIDES]


@pytest.mark.parametrize('pose', ALL_POSES)
def test_pose_rotation_matches_derivation(pose):
    """Every defined pose must equal the geometrically derived rotation."""
    assert np.allclose(_rot(**get_pose_rotation(pose)), _expected(pose), atol=1e-9)


@pytest.mark.parametrize('side', SIDES)
def test_feet_first_differs_from_head_first(side):
    """Regression: feet-first must not reuse the head-first rotation.

    ``Foot_Left``/``Foot_Right`` previously shared the ``Head_*`` rotation,
    which silently mislabels left/right for feet-first acquisitions.
    """
    head = _rot(**get_pose_rotation('Head_{}'.format(side)))
    foot = _rot(**get_pose_rotation('Foot_{}'.format(side)))
    assert not np.allclose(head, foot, atol=1e-9)


@pytest.mark.parametrize('side', SIDES)
def test_tail_is_alias_of_foot(side):
    """Bruker spells the quadruped feet-first entry Tail_*."""
    assert (SUBJECT_POSE_ROTATION['Tail_{}'.format(side)]
            == SUBJECT_POSE_ROTATION['Foot_{}'.format(side)])


@pytest.mark.parametrize('pose', ALL_POSES)
def test_both_code_paths_agree(pose):
    """The legacy loader path and the API path must not drift apart again.

    These carried independent copies of the pose table, which is how they came
    to disagree on Foot_Left/Foot_Right in the first place.
    """
    api = AffineAnalyzer._est_rotate_angle(pose)
    lib = {'rad_x': 0, 'rad_y': 0, 'rad_z': 0}
    lib.update(get_pose_rotation(pose))
    assert np.allclose(_rot(**api), _rot(**lib), atol=1e-9)


def test_rotations_are_proper_rotations():
    """No pose may introduce a reflection (det must be +1, not -1)."""
    for pose in ALL_POSES:
        assert np.isclose(np.linalg.det(_rot(**get_pose_rotation(pose))), 1.0, atol=1e-9)


def test_unknown_pose_raises():
    with pytest.raises(KeyError):
        get_pose_rotation('Head_Sideways')


def test_empty_pose_is_identity():
    assert get_pose_rotation(None) == {}
    assert get_pose_rotation('') == {}


# --- subject type -------------------------------------------------------

def test_absent_subject_type_uses_rodent_frame():
    """Unknown subject type must keep the rodent correction.

    VisuSubjectType exists only from PV6 onwards, and PV5 cannot express a
    subject type at all (it writes SUBJECT_type=Human for every study), so on
    PV5 the type is genuinely unknown and the data is overwhelmingly rodent.

    Validated against testdata/new-orientation/: the same mouse phantom scanned
    head-first prone on PV5.1 and PV6.0.1 agrees at NCC +0.90..+0.95 under the
    rodent frame and only +0.22 under the primate frame. The PV6 manual's
    "Unknown -> Primate" rule describes ParaVision's display convention, not
    what a converter should do here.
    """
    assert uses_quadruped_frame(None) is True


def test_explicit_human_override_is_biped():
    """'Human' is accepted as the PV5 spelling of Biped for explicit overrides.

    This is only for a user-supplied --subjecttype. It must never be read off a
    PV5 study automatically: see test_pv5_subject_type_not_taken_from_subject_file.
    """
    assert normalize_subject_type('Human') == 'Biped'
    assert uses_quadruped_frame('Human') is False


@pytest.mark.parametrize('subj_type', ['Quadruped', 'Other', 'OtherAnimal', 'Phantom'])
def test_non_biped_types_still_corrected(subj_type):
    """Existing behaviour for known non-biped types is unchanged."""
    assert uses_quadruped_frame(subj_type) is True


def test_pv5_subject_type_not_taken_from_subject_file():
    """The loader must not read subject type off a PV5 study.

    PV5 writes SUBJECT_type=Human unconditionally, so the resolved type must
    stay None (unknown -> rodent) rather than becoming Biped. An earlier
    revision of this change read the subject file and flipped PV5 rodent data
    into the primate frame; testdata/new-orientation/ caught it.
    """
    from brkraw_legacy import BrukerLoader

    study = _pv5_study()
    if study is None:
        pytest.skip('no PV5 study under ./testdata')
    s = BrukerLoader(str(study))
    assert s.pvobj.subj_type == 'Human', 'expected the PV5 subject file to say Human'
    sid = s.pvobj.avail_scan_id[0]
    info = s._get_orient_info(s.get_visu_pars(sid, 1), s.get_method(sid))
    assert info['subject_type'] is None, (
        'PV5 subject type must stay unknown, not be read from SUBJECT_type')
    assert uses_quadruped_frame(info['subject_type']) is True


def test_biped_not_corrected():
    assert uses_quadruped_frame('Biped') is False


def test_quadruped_correction_applied_after_pose():
    """The animal correction is a fixed-frame convention change.

    It must left-multiply the pose rotation (Q @ P), not be folded into it,
    otherwise the pose angles would be interpreted in already-rotated axes --
    the failure mode reported upstream in BrkRaw/brkraw#228.
    """
    from brkraw_legacy.lib.orient import build_affine_from_orient_info

    kwargs = dict(resol=(1.0, 1.0, 1.0), rmat=np.eye(3), pose=np.zeros(3),
                  slice_orient='axial')
    biped = build_affine_from_orient_info(subj_pose='Head_Supine',
                                          subj_type='Biped', **kwargs)
    quad = build_affine_from_orient_info(subj_pose='Head_Supine',
                                         subj_type='Quadruped', **kwargs)
    q = apply_rotate(np.eye(4), rad_x=-PI / 2, rad_y=PI)[:3, :3]
    assert np.allclose(quad[:3, :3], q @ biped[:3, :3], atol=1e-9)


# --- cross-study validation (needs testdata/new-orientation/) --------------

_NEWORIENT = _TESTDATA / 'new-orientation'
_PV5_STUDY = _NEWORIENT / '20201230_CIC_PLANTEST_PV5_001.5S1'
_PV6_STUDY = _NEWORIENT / '20201230_101610_CIC_LRMousePhantom_1_1'


def _load(study, scan_id, subj_type=None):
    from brkraw_legacy import BrukerLoader
    s = BrukerLoader(str(study))
    if subj_type:
        s.override_subjtype(subj_type)
    nii = s.get_niftiobj(scan_id, 1)
    nii = nii[0] if isinstance(nii, list) else nii
    data = np.asarray(nii.dataobj, dtype=float)
    while data.ndim > 3:
        data = data[..., 0]
    return data, nii.affine


def _resample_into(src, src_affine, ref_shape, ref_affine):
    from scipy.ndimage import affine_transform
    m = np.linalg.inv(src_affine) @ ref_affine
    return affine_transform(src, m[:3, :3], offset=m[:3, 3],
                            output_shape=ref_shape, order=1, cval=0.0)


def _ncc(a, b):
    a = a.ravel() - a.mean()
    b = b.ravel() - b.mean()
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


needs_neworient = pytest.mark.skipif(
    not (_PV5_STUDY.is_dir() and _PV6_STUDY.is_dir()),
    reason='needs testdata/new-orientation/ (PV5 + PV6 phantom studies)')


@needs_neworient
@pytest.mark.parametrize('pv5_scan', [8, 9, 10, 13])
def test_pv5_rodent_frame_matches_pv6_reference(pv5_scan):
    """PV5 data must land in the same frame as the PV6 scan of the same object.

    The same mouse phantom was scanned head-first prone on a PV5.1 and a
    PV6.0.1 system. PV5 declares Human (it cannot declare anything else), PV6
    declares Quadruped. Treating the absent PV5 type as rodent makes the two
    agree; treating it as biped does not.
    """
    ref, ref_aff = _load(_PV6_STUDY, 13)
    rodent, rodent_aff = _load(_PV5_STUDY, pv5_scan, 'Quadruped')
    primate, primate_aff = _load(_PV5_STUDY, pv5_scan, 'Biped')

    r_rodent = _ncc(ref, _resample_into(rodent, rodent_aff, ref.shape, ref_aff))
    r_primate = _ncc(ref, _resample_into(primate, primate_aff, ref.shape, ref_aff))

    assert r_rodent > 0.85, f'rodent frame should match PV6 reference, got {r_rodent:.3f}'
    assert r_rodent > r_primate + 0.5, (
        f'rodent frame ({r_rodent:.3f}) must clearly beat primate ({r_primate:.3f})')


@needs_neworient
@pytest.mark.parametrize('scan_id', [14, 15])
def test_slice_orientation_is_world_consistent(scan_id):
    """Sagittal/coronal must land where axial does.

    Physical placement and subject declaration are constant across the whole
    study; only slice orientation and readout direction vary. Note the coronal
    affine is left-handed (det -1) by design -- the coronal 2dseq is stored
    mirrored and the [1,1,-1] resolution flip compensates -- so this checks the
    image agrees directly, not merely that the determinants match.
    """
    ref, ref_aff = _load(_PV6_STUDY, 13)
    mov, mov_aff = _load(_PV6_STUDY, scan_id)

    direct = _ncc(ref, _resample_into(mov, mov_aff, ref.shape, ref_aff))
    flip = np.diag([-1.0, 1, 1, 1])
    mirrored = _ncc(ref, _resample_into(mov, flip @ mov_aff, ref.shape, ref_aff))

    assert direct > 0.85, f'scan {scan_id} should match axial reference, got {direct:.3f}'
    assert direct > mirrored, f'scan {scan_id} is mirrored vs the axial reference'


@needs_neworient
@pytest.mark.parametrize('study_attr', ['_PV5_STUDY', '_PV6_STUDY'])
def test_loader_and_api_paths_agree(study_attr):
    """The BrukerLoader/CLI path and the app.tonifti/API path must agree.

    They source subject type independently -- the loader reads VisuSubjectType
    in `_get_orient_info`, the API path reads it in `helper.Orientation` -- so a
    change to one (e.g. re-adding a PV5 SUBJECT_type fallback to only one path)
    could silently desync them. This pins them together on real data, including
    the PV5 case where both must resolve the absent type to the rodent frame.

    Some scans hit a pre-existing crash in the API path's `_correct_origin`
    (reverse slice order), unrelated to orientation; those are skipped, and the
    test requires a quorum so it cannot pass by comparing nothing.
    """
    from brkraw_legacy import BrukerLoader
    from brkraw_legacy.app.tonifti import StudyToNifti

    study = str(globals()[study_attr])
    loader = BrukerLoader(study)
    api = StudyToNifti(study)

    compared = 0
    for sid in loader.pvobj.avail_scan_id:
        try:
            la = loader.get_affine(sid, 1)
            aa = api.get_affine(sid, 1)
        except Exception:
            continue
        la = la[0] if isinstance(la, list) else la
        aa = aa[0] if isinstance(aa, list) else aa
        assert np.allclose(la, aa, atol=1e-6), (
            f'scan {sid}: loader and API affines differ')
        compared += 1

    assert compared >= 5, f'expected to compare several scans, only did {compared}'


# --- API-path affine assembly (multi-pack / reverse slice order) -----------
# These pin fixes to AffineAnalyzer._calculate_affine and
# helper.Orientation._est_volume_origin, which crashed the app.tonifti path on
# any scan whose first slice pack is index 0 (falsy) or whose slices are stored
# in reverse order -- while the BrukerLoader path handled them fine.

@needs_neworient
def test_api_handles_reverse_slice_order():
    """A reverse-slice-order scan must build an affine, matching the loader.

    PV6 scan 15 (coronal) has reverse_slice_order=True; the API path previously
    raised `ValueError: setting an array element with a sequence` because it
    passed the whole slice-distance list where a scalar was required.
    """
    from brkraw_legacy import BrukerLoader
    from brkraw_legacy.app.tonifti import StudyToNifti

    loader = BrukerLoader(str(_PV6_STUDY)).get_affine(15, 1)
    api = StudyToNifti(str(_PV6_STUDY)).get_affine(15, 1)
    loader = loader[0] if isinstance(loader, list) else loader
    api = api[0] if isinstance(api, list) else api
    assert np.allclose(loader, api, atol=1e-4)


@needs_neworient
def test_api_handles_multislice_localizer():
    """A multi-slice-pack localizer must yield one proper affine per pack.

    PV6 scan 3 is a 3-plane scout (15 frames -> 3 packs). The API path
    previously crashed twice: `.index(2)` on the wrong (whole) list for pack 0,
    then a scalar volume origin from _est_volume_origin. Each pack's affine must
    be a full 4x4 and match the loader.
    """
    from brkraw_legacy import BrukerLoader
    from brkraw_legacy.app.tonifti import StudyToNifti

    loader = BrukerLoader(str(_PV6_STUDY)).get_affine(3, 1)
    api = StudyToNifti(str(_PV6_STUDY)).get_affine(3, 1)
    assert isinstance(api, list) and len(api) == len(loader) > 1
    for la, aa in zip(loader, api):
        assert np.shape(aa) == (4, 4)
        assert np.allclose(la, aa, atol=1e-4)


def test_unequal_slices_per_pack_raises_clearly():
    """Unequal per-pack slice counts must fail with a clear, catchable error.

    The API path cannot recover unequal packing (e.g. a 13-frame scout grouped
    [5, 3, 5]) from the frame count alone; it must raise NotImplementedError
    with an explanation rather than a raw IndexError from downstream assembly.
    lego_phantom scan 8 is such a scan; skip if that corpus is absent.
    """
    lego = _TESTDATA / 'pv6' / 'full' / 'lego_phantom'
    if not lego.is_dir():
        pytest.skip('no lego_phantom study under ./testdata')
    from brkraw_legacy.app.tonifti import StudyToNifti
    with pytest.raises(NotImplementedError, match='[Uu]nequal'):
        StudyToNifti(str(lego)).get_affine(8, 1)
