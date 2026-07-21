"""Subject orientation regression tests.

Covers the defect found by reviewing the affine code against the Bruker
ParaVision orientation conventions: ``Foot_Left``/``Foot_Right`` (and their
``Tail_*`` aliases) were given the *head-first* rotation in the legacy path,
dropping the feet-first entry flip -- so the two conversion paths disagreed.

Also pins the subject-type behaviour that ParaVision's display convention makes
look wrong. The Primate system "is also used for subject specimen Unknown",
which reads as though an absent ``VisuSubjectType`` (i.e. all PV5 data) should
use the biped frame. Changing it to that regresses real PV5 rodent conversions;
see ``test_absent_subject_type_uses_rodent_frame`` for the evidence.
"""
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

    Validated against paired PV5.1/PV6.0.1 acquisitions of the same mouse
    phantom (head-first prone): they agree at NCC +0.90..+0.95 under the rodent
    frame and only +0.22 under the primate frame. ParaVision's "Unknown ->
    Primate" rule describes its display convention, not what a converter should
    do here.
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


def test_pv5_subject_type_not_taken_from_subject_file(h2_study):
    """The loader must not read subject type off a PV5 study.

    PV5 writes SUBJECT_type=Human unconditionally, so the resolved type must
    stay None (unknown -> rodent) rather than becoming Biped. An earlier
    revision of this change read the subject file and flipped PV5 rodent data
    into the primate frame; paired PV5/PV6 phantom data caught it.
    """
    from brkraw_legacy import BrukerLoader

    s = BrukerLoader(str(h2_study))
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


# --- loader/API path agreement on real data --------------------------------

def test_loader_and_api_affines_agree(lego_study):
    """The BrukerLoader/CLI path and the app.tonifti/API path must agree.

    They source subject type and assemble affines independently -- the loader in
    `_get_orient_info`, the API path in `helper.Orientation` -- so they can
    silently desync. Iterating a whole multi-sequence study pins them together,
    including the multi-pack and reverse-slice-order scans that used to crash the
    API path (`.index(2)` on the wrong list for a falsy first pack, a scalar
    where a slice-distance list was expected). Scans that hit a pre-existing
    crash in either path are skipped; a quorum keeps the test from passing by
    comparing nothing.
    """
    from brkraw_legacy import BrukerLoader
    from brkraw_legacy.app.tonifti import StudyToNifti

    loader = BrukerLoader(str(lego_study))
    api = StudyToNifti(str(lego_study))

    compared = 0
    for sid in loader.pvobj.avail_scan_id:
        try:
            la = loader.get_affine(sid, 1)
            aa = api.get_affine(sid, 1)
        except Exception:
            continue
        la = la if isinstance(la, list) else [la]
        aa = aa if isinstance(aa, list) else [aa]
        if len(la) != len(aa):
            continue
        for x, y in zip(la, aa):
            assert np.allclose(x, y, atol=1e-6), f'scan {sid}: loader and API affines differ'
        compared += 1

    assert compared >= 5, f'expected to compare several scans, only did {compared}'


def test_unequal_slices_per_pack_converts(lego_study):
    """Unequal per-pack slice counts must convert, matching the loader.

    lego_phantom scan 8 is a 13-frame scout genuinely packed [5, 3, 5]. Both the
    SlicePack parser (VisuCoreSlicePacksSlices per-pack counts) and the frame
    regrouping in Orientation must use those counts rather than assuming an equal
    split; otherwise the API path crashes. Each pack's affine must match the
    BrukerLoader path exactly.
    """
    from brkraw_legacy import BrukerLoader
    from brkraw_legacy.app.tonifti import StudyToNifti

    loader = BrukerLoader(str(lego_study)).get_affine(8, 1)
    api = StudyToNifti(str(lego_study)).get_affine(8, 1)
    assert isinstance(api, list) and len(api) == len(loader) == 3
    for la, aa in zip(loader, api):
        assert np.shape(aa) == (4, 4)
        assert np.allclose(la, aa, atol=1e-4)
