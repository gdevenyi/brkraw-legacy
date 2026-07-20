# -*- coding: utf-8 -*-
"""Canonical subject-position and subject-type handling.

Single source of truth for the two conversion paths that need it:

* ``brkraw_legacy.lib.orient``            -- legacy ``BrukerLoader`` / ``tonii`` CLI
* ``brkraw_legacy.api.analyzer.affine``   -- ``app.tonifti`` API

These used to carry independent copies of the table below, which is how they
drifted apart (the legacy copy gave ``Foot_Left``/``Foot_Right`` the *head-first*
rotation).  Keep the table here only.

References
----------
ParaVision 6.0.1 Software Manual, S1.3.6 "Subject Coordinate Systems":

    Rodent (quadrupeds)      Ventral/Dorsal, Left/Right, Caudal/Rostral
    Primate (bipeds)         Anterior/Posterior, Left/Right, Head/Foot
                             "This coordinate system is also used for subject
                             specimen Unknown."
    Material (phantoms)      XYZ
"""

import numpy as np

SUBJECT_TYPES = ['Biped', 'Quadruped', 'Phantom', 'Other', 'OtherAnimal']
SUBJECT_POSE = {
    'part': ['Head', 'Foot', 'Tail'],
    'side': ['Supine', 'Prone', 'Left', 'Right'],
}

#: ParaVision 5 spells the biped subject type ``Human`` in the study-level
#: ``subject`` file; PV6+ spells it ``Biped`` in ``VisuSubjectType``.
_TYPE_ALIASES = {'Human': 'Biped'}

#: Rotation taking the image frame to the subject frame, keyed by
#: ``VisuSubjectPosition``.  ``Head_Prone`` is the reference (identity).
#:
#: Supine/Prone/Left/Right differ by a roll about the bore (head-foot) axis.
#: Feet-first entry is the head-first rotation composed with a 180 degree flip
#: about the table-normal axis, i.e. ``Foot_X == Ry(pi) @ Head_X`` -- which is
#: why every ``Foot_*``/``Tail_*`` entry carries ``rad_y=pi``.  Angles are
#: consumed by ``apply_rotate``/``rotate_affine``, which compose as Rz @ Ry @ Rx
#: in the fixed frame.
SUBJECT_POSE_ROTATION = {
    'Head_Supine': {'rad_z': np.pi},
    'Head_Prone':  {},
    'Head_Left':   {'rad_z': np.pi / 2},
    'Head_Right':  {'rad_z': -np.pi / 2},
    'Foot_Supine': {'rad_x': np.pi},
    'Foot_Prone':  {'rad_y': np.pi},
    'Foot_Left':   {'rad_y': np.pi, 'rad_z': -np.pi / 2},
    'Foot_Right':  {'rad_y': np.pi, 'rad_z': np.pi / 2},
}

# Bruker uses Tail_* as the quadruped spelling of Foot_*.
for _side in SUBJECT_POSE['side']:
    SUBJECT_POSE_ROTATION['Tail_{}'.format(_side)] = SUBJECT_POSE_ROTATION['Foot_{}'.format(_side)]
del _side


def normalize_subject_type(subj_type):
    """Map a raw subject type onto the ``VisuSubjectType`` vocabulary.

    Args:
        subj_type (str or None): value of ``VisuSubjectType`` (PV6+) or of the
            study-level ``SUBJECT_type`` (all versions).

    Returns:
        str or None: normalized type, or None if nothing was given.
    """
    if subj_type is None:
        return None
    return _TYPE_ALIASES.get(subj_type, subj_type)


def uses_quadruped_frame(subj_type):
    """Whether the rodent (quadruped) axis correction applies.

    ``VisuSubjectType`` only exists from ParaVision 6 onwards, so on PV5 data
    it is always absent.  The manual is explicit that an unknown specimen uses
    the Primate coordinate system, so an absent type must *not* select the
    rodent correction -- otherwise every PV5 dataset gets an animal-specific
    rotation applied on no evidence.

    Args:
        subj_type (str or None): raw or normalized subject type.

    Returns:
        bool: True only when the type is known and is not a biped.
    """
    subj_type = normalize_subject_type(subj_type)
    if subj_type is None:
        return False
    return subj_type != 'Biped'


def get_pose_rotation(subj_pose):
    """Rotation angles for a ``VisuSubjectPosition`` value.

    Args:
        subj_pose (str or None): e.g. ``'Head_Supine'``. None/empty yields no
            rotation.

    Returns:
        dict: kwargs for ``apply_rotate``/``rotate_affine``.

    Raises:
        KeyError: if the position is not one Bruker defines.
    """
    if not subj_pose:
        return {}
    return dict(SUBJECT_POSE_ROTATION[subj_pose])


def inspect_subject_info(subj_pose, subj_type):
    """Validate subject position/type strings.

    Raises:
        AssertionError: on a malformed position or an unknown type.
    """
    if subj_pose:
        part, side = subj_pose.split('_')
        assert part in SUBJECT_POSE['part'], 'Invalid subject position'
        assert side in SUBJECT_POSE['side'], 'Invalid subject position'
    if subj_type:
        assert normalize_subject_type(subj_type) in SUBJECT_TYPES, 'Invalid subject type'
