"""Subject orientation regression tests.

Covers the two bugs found by reviewing the affine code against FILE_FORMAT.md
and the ParaVision 6.0.1 Software Manual:

1. ``Foot_Left``/``Foot_Right`` (and their ``Tail_*`` aliases) were given the
   *head-first* rotation in the legacy path, dropping the feet-first entry flip.
2. An absent ``VisuSubjectType`` selected the quadruped correction. The manual
   (S1.3.6.2) states the Primate/biped system "is also used for subject
   specimen Unknown", and ``VisuSubjectType`` does not exist before PV6 -- so
   every PV5 dataset was getting an animal-specific rotation.
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

def test_absent_subject_type_is_not_quadruped():
    """PV5 has no VisuSubjectType; unknown must use the Primate system.

    ParaVision 6.0.1 Software Manual S1.3.6.2: the Primate coordinate system
    "is also used for subject specimen Unknown".
    """
    assert uses_quadruped_frame(None) is False


def test_pv5_human_normalizes_to_biped():
    """PV5 spells the biped type 'Human' in the study-level subject file."""
    assert normalize_subject_type('Human') == 'Biped'
    assert uses_quadruped_frame('Human') is False


@pytest.mark.parametrize('subj_type', ['Quadruped', 'Other', 'OtherAnimal', 'Phantom'])
def test_non_biped_types_still_corrected(subj_type):
    """Existing behaviour for known non-biped types is unchanged."""
    assert uses_quadruped_frame(subj_type) is True


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
