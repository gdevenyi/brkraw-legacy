"""Unit tests for the Bruker->BIDS metadata reference tables (lib/reference.py)
and the equation resolver (lib/utils.meta_check_express).

Pure-unit (offline): resolve individual reference entries with stub parameter
objects (``.parameters`` dicts) via meta_get_value, asserting on the emitted
value rather than only its BIDS well-formedness.
"""
from types import SimpleNamespace

import numpy as np
import pytest

from brkraw_legacy.lib.reference import COMMON_META_REF
from brkraw_legacy.lib.utils import meta_get_value, meta_check_express


def _p(**params):
    """A stub acqp/method/visu_pars carrying a .parameters dict."""
    return SimpleNamespace(parameters=dict(params))


def _resolve(field, acqp=None, method=None, visu=None):
    return meta_get_value(COMMON_META_REF[field], acqp or _p(), method or _p(), visu or _p())


# --- equation resolver (meta_check_express) --------------------------------

def test_equation_fields_resolve():
    """Equation-based fields must actually compute (PEP 667 regression).

    The old exec()-into-locals() resolver silently returned None for every
    equation field on Python 3.13+. Cover several equation shapes: array math,
    scalar math, str(), and len().
    """
    visu = _p(VisuAcqEchoTime=[10.0, 20.0],       # array math: np.array(TE)/1000
              VisuAcqImagingFrequency=400.0,       # scalar math: Freq/42.576
              VisuSystemOrderNumber=12345,         # str(SN)
              VisuAcqGradEncoding=['read_enc', 'phase_enc', 'slice_enc'])  # len(EncSeq)

    assert np.allclose(_resolve('EchoTime', visu=visu), [0.010, 0.020])
    assert _resolve('MagneticFieldStrength', visu=visu) == pytest.approx(400.0 / 42.576)
    assert _resolve('DeviceSerialNumber', visu=visu) == '12345'
    # SliceEncodingDirection: 'slice_enc' index (2) OR len(EncSeq); either resolves
    assert _resolve('SliceEncodingDirection', visu=visu) in (2, 3)


def test_equation_field_omitted_when_input_missing():
    """A missing referenced parameter yields None (field omitted), not 'None'."""
    # VisuAcqImagingFrequency absent -> MagneticFieldStrength cannot be computed.
    assert _resolve('MagneticFieldStrength', visu=_p()) is None
    # str(SN) with SN absent must omit rather than emit the literal 'None'.
    assert _resolve('DeviceSerialNumber', visu=_p()) is None


def test_unused_declared_variable_does_not_suppress_field():
    """A declared-but-unused missing variable must not omit the field.

    Guards the resolver against fields like TotalReadoutTime that declare an
    extra variable (ETL) not referenced by the equation: the field must still
    compute when that variable is absent.
    """
    val = {'X': 'PresentParam', 'Unused': 'MissingParam', 'Equation': 'X * 2'}
    acqp = _p(PresentParam=5)      # MissingParam absent -> Unused resolves to None
    assert meta_check_express(val, acqp, _p(), _p()) == 10
