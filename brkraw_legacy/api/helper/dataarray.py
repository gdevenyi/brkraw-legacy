from __future__ import annotations
import numpy as np
from typing import TYPE_CHECKING
from .base import BaseHelper, is_all_element_same, BYTEORDER, WORDTYPE
if TYPE_CHECKING:
    from ..analyzer import ScanInfoAnalyzer


class DataArray(BaseHelper):
    """requires visu_pars and aqcp to pars parameter related to the dtype of binary files

    Dependencies:
        acqp
        visu_pars

    Args:
        BaseHelper (_type_): _description_
    """
    def __init__(self, analobj: 'ScanInfoAnalyzer'):
        super().__init__()
        visu_pars = analobj.visu_pars

        # An empty or unreadable visu_pars parses to a raw line list (not a
        # Parameter), e.g. an empty reconstruction whose pdata files are all
        # zero bytes. It carries no image metadata, so reject it with a clear
        # message instead of crashing on ``list["VisuCoreByteOrder"]``.
        if not hasattr(visu_pars, 'keys') or 'VisuCoreByteOrder' not in visu_pars.keys():
            raise ValueError('reconstruction has no image metadata (empty or '
                             'unreadable visu_pars); cannot convert to NIfTI')

        byte_order = visu_pars["VisuCoreByteOrder"]
        word_type = visu_pars["VisuCoreWordType"]
        self.data_dtype = np.dtype(f'{BYTEORDER[byte_order]}{WORDTYPE[word_type]}')
        
        data_slope = visu_pars["VisuCoreDataSlope"]
        data_offset = visu_pars["VisuCoreDataOffs"]
        self.data_slope = data_slope[0] \
            if isinstance(data_slope, list) and is_all_element_same(data_slope) else data_slope
        self.data_offset = data_offset[0] \
            if isinstance(data_offset, list) and is_all_element_same(data_offset) else data_offset
            
        if isinstance(self.data_slope, list) or isinstance(self.data_offset, list):
            self._warn("Data slope and data offset values are unusual. "
                    "They are expected to be either a list containing the same elements or a single float value.")


    def get_info(self):
        return {
            'dtype': self.data_dtype,
            'slope': self.data_slope,
            'offset': self.data_offset,
            'warns': self.warns
        }