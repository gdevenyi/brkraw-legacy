"""Unit tests for the Bruker->BIDS metadata reference tables (lib/reference.py)
and the equation resolver (lib/utils.meta_check_express).

Pure-unit (offline): resolve individual reference entries with stub parameter
objects (``.parameters`` dicts) via meta_get_value, asserting on the emitted
value rather than only its BIDS well-formedness.
"""
from types import SimpleNamespace

import numpy as np
import pytest

from brkraw_legacy.lib.reference import COMMON_META_REF, FMRI_META_REF
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


# --- SliceTiming (H2) -------------------------------------------------------

def test_slicetiming_spans_full_tr_independent_of_volume_count():
    """SliceTiming must span [0, TR) per volume, not shrink with NR (H2 regression).

    Previously Num_of_Slice = VisuCoreFrameCount (= NI*NR), so a 100-volume fMRI
    collapsed the slice times into ~1/100 of TR.
    """
    n_slices, n_vol, tr_ms = 20, 100, 2000.0
    acqp = _p(ACQ_obj_order=list(range(n_slices)))
    visu = _p(VisuAcqRepetitionTime=tr_ms,
              VisuCoreFrameCount=n_slices * n_vol)   # the old (wrong) denominator
    st = np.asarray(_resolve('SliceTiming', acqp=acqp, visu=visu))

    assert st.shape == (n_slices,)
    assert st.min() == 0.0
    # sequential: last slice at (N-1)/N * TR, in seconds -- full span, not 1/NR of it
    assert np.isclose(st.max(), (tr_ms / 1000.0) * (n_slices - 1) / n_slices)


def test_slicetiming_follows_interleaved_order():
    """Interleaved acquisition produces distinct, TR-spanning slice times."""
    acqp = _p(ACQ_obj_order=[0, 2, 1, 3])          # 4-slice interleaved (from PV data)
    visu = _p(VisuAcqRepetitionTime=1000.0, VisuCoreFrameCount=4)
    st = np.asarray(_resolve('SliceTiming', acqp=acqp, visu=visu))
    assert st.shape == (4,)
    assert np.isclose(st.max(), 1.0 * 3 / 4)       # spans up to (N-1)/N * TR
    assert len(set(np.round(st, 6))) == 4          # all four slice times distinct


# --- readout timing (M3) ----------------------------------------------------

def test_effective_echo_spacing_uses_ppi_not_echo_train():
    """EES divides by the PPI acceleration (default 1), not ACQ_phase_factor.

    ACQ_phase_factor is the RARE/EPI echo-train factor; using it wrongly shrank
    EES by the echo-train length.
    """
    p = _p(VisuAcqPixelBandwidth=200.0, PVM_EncMatrix=[128, 64],
           VisuAcqGradEncoding=['read_enc', 'phase_enc'],   # phase_enc index 1 -> MatSizePE=64
           ACQ_phase_factor=8)                              # must be ignored now
    ees = _resolve('EffectiveEchoSpacing', visu=p)
    assert ees == pytest.approx(1 / (64 * 200))             # accel defaults to 1, not /8


def test_effective_echo_spacing_scales_with_ppi_accel():
    p = _p(VisuAcqPixelBandwidth=200.0, PVM_EncMatrix=[128, 64],
           VisuAcqGradEncoding=['read_enc', 'phase_enc'],
           PVM_EncPpiAccel1=2)
    ees = _resolve('EffectiveEchoSpacing', visu=p)
    assert ees == pytest.approx(1 / (64 * 200) / 2)


def test_total_readout_time_ignores_ppi_default_and_missing_etl():
    """TotalReadoutTime computes without VisuAcqEchoTrainLength (unused ETL dropped)
    and defaults the acceleration to 1 rather than dividing by ACQ_phase_factor."""
    p = _p(VisuAcqPixelBandwidth=200.0, ACQ_phase_factor=8)  # no ETL, no PPI accel
    trt = _resolve('TotalReadoutTime', visu=p)
    assert trt == pytest.approx(1 / 200)


# --- RepetitionTime for func (M5) -------------------------------------------

def test_repetition_time_emitted_for_every_scan():
    """RepetitionTime is in COMMON_META_REF so the one-shot path emits it (M5).

    It was func-only via FMRI_META_REF, so func sidecars from the one-shot
    conversion path were missing this BIDS-required field.
    """
    assert 'RepetitionTime' in COMMON_META_REF
    assert 'RepetitionTime' not in FMRI_META_REF
    rt = _resolve('RepetitionTime', visu=_p(VisuAcqRepetitionTime=2500.0))
    assert rt == pytest.approx(2.5)                 # ms -> s


def test_common_and_fmri_refs_do_not_share_keys():
    """get_bids_ref_obj raises on duplicate keys when merging 'common' and 'func',
    so the two tables must stay disjoint."""
    assert set(COMMON_META_REF) & set(FMRI_META_REF) == set()


# --- PhaseEncodingDirection axis (M2) ---------------------------------------

@pytest.mark.parametrize('grad_encoding, axis_index', [
    (['phase_enc', 'read_enc'], 0),                       # -> 'i' after loader conversion
    (['read_enc', 'phase_enc'], 1),                       # -> 'j'
    (['read_enc', 'phase_enc', 'slice_enc'], 1),          # -> 'j' (3D)
])
def test_phase_encoding_resolves_axis_index_only(grad_encoding, axis_index):
    """PhaseEncodingDirection resolves the PE axis index (loader maps it to i/j/k).

    The polarity sign (i-/j-/k-) is intentionally NOT emitted: it cannot be
    derived reliably from Bruker parameters and a wrong sign harms distortion
    correction (M2).
    """
    assert _resolve('PhaseEncodingDirection', visu=_p(VisuAcqGradEncoding=grad_encoding)) == axis_index
