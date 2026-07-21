"""This module create header
currently not functioning as expected, need to work more
"""

from __future__ import annotations
import warnings
import numpy as np
from nibabel.nifti1 import Nifti1Image
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Optional, Literal
    from brkraw_legacy.api.data import ScanInfo


class Header:
    info: ScanInfo
    scale_mode: int
    nifti1image: 'Nifti1Image'
    
    def __init__(self, 
                 scaninfo: 'ScanInfo',
                 nifti1image: 'Nifti1Image',
                 scale_mode: Optional[Literal['header', 'apply']] = None):
        self.info = scaninfo
        self.scale_mode = 1 if scale_mode == 'header' else 0
        self.nifti1image = nifti1image
        self.nifti1image.header.default_x_flip = False
        self._set_scale_params()
        self._set_sliceorder()
        self._set_time_step()
        
    def _set_sliceorder(self):
        slice_order_scheme = self.info.slicepack['slice_order_scheme']
        if slice_order_scheme == 'User_defined_slice_scheme' or slice_order_scheme:
            slice_code = 0
        elif slice_order_scheme == 'Sequential':
            slice_code = 1
        elif slice_order_scheme == 'Reverse_sequential':
            slice_code = 2
        elif slice_order_scheme == 'Interlaced':
            slice_code = 3
        elif slice_order_scheme == 'Reverse_interlacesd':
            slice_code = 4
        elif slice_order_scheme == 'Angiopraphy':
            slice_code = 5
        else:
            slice_code = 0
        
        if slice_code == 0:
            warnings.warn(
                "Failed to identify compatible 'slice_code'. "
                "Please use this header information with care in case slice timing correction is needed."
            )
        self.nifti1image.header['slice_code'] = slice_code

    def _set_time_step(self):
        xyzt_unit = {'cycle':('mm', 'sec')}
        if self.info.cycle['num_cycles'] > 1:
            time_step = self.info.cycle['time_step'] / 1000
            self.nifti1image.header['pixdim'][4] = time_step
            num_slices = self.info.slicepack['num_slices_each_pack'][0]
            self.nifti1image.header['slice_duration'] = time_step / num_slices
            self.nifti1image.header.set_xyzt_units(*xyzt_unit['cycle'])
            
    def _set_scale_params(self):
        if self.scale_mode:
            slope = self.info.dataarray['slope']
            inter = self.info.dataarray['offset']
            if np.ndim(slope) or np.ndim(inter):
                # Per-volume slope/offset (e.g. fMRI) cannot be stored in NIfTI's
                # scalar scl_slope/scl_inter; leave them at the header default
                # rather than crashing. Baking per-volume scaling into the data
                # is a separate concern (the BrukerLoader path does this).
                warnings.warn(
                    "Per-volume scale factors are not representable in the NIfTI "
                    "header; scl_slope/scl_inter left at default.", UserWarning)
            else:
                self.nifti1image.header.set_slope_inter(slope=slope, inter=inter)
        self._update_dtype()

    def _update_dtype(self):
        self.nifti1image.header.set_data_dtype(self.nifti1image.dataobj.dtype)

    def get(self):
        return self.nifti1image