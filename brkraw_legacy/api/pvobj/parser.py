"""JCAMP-DX parameter parsing for the ``api.pvobj`` object model.

brkraw-legacy has exactly one JCAMP-DX parser: the functions in
:mod:`brkraw_legacy.lib.utils`. This module is a thin façade that exposes that
single implementation to the ``api.pvobj`` layer, so the object model, the
loader, and the BIDS conversion all parse parameters identically and cannot
diverge.

A second copy used to live here and mis-tokenised struct arrays whose ``<...>``
string literal contained parentheses or commas -- e.g. an ``FG_ISA`` frame group
commented ``<T2 relaxation: y=A+C*exp(-t/T2)>`` -- which corrupted
``VisuFGOrderDesc`` and broke conversion of derived (ISA/DTI) reconstructions on
the app.tonifti path. The lib parser masks the ``(``, ``)`` and ``,`` delimiters
inside ``<...>`` literals before tokenising; it is covered by
``tests/07_conversion_test.py``.
"""
from brkraw_legacy.lib.reference import HEADER, PARAMETER, ptrn_comment  # noqa: F401
from brkraw_legacy.lib.utils import (
    convert_data_to as _convert_data_to,
    convert_string_to as _convert_string_to,
    load_param as _load_param,
)


class Parser:
    """Façade over the single JCAMP-DX parser in :mod:`brkraw_legacy.lib.utils`."""

    @staticmethod
    def load_param(stringlist):
        return _load_param(stringlist)

    @staticmethod
    def convert_string_to(string):
        return _convert_string_to(string)

    @staticmethod
    def convert_data_to(data, shape):
        return _convert_data_to(data, shape)
