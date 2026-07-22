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
        self._set_slice_extent()
        self._set_time_step()
        self._set_sform_qform()
        self._set_cal_and_descrip()
        
    def _set_sliceorder(self):
        # Bruker PVM_ObjOrderScheme -> NIfTI slice_code. Enum spellings are taken
        # verbatim from the ParaVision installs: PV5.1 emits Sequential /
        # Reverse_sequential / Interlaced, PV6.0.1 emits Sequential /
        # Reverse_interlaced / Interlaced. Interlaced maps to NIFTI_SLICE_ALT_INC
        # (even-first); the scheme name alone cannot distinguish ALT_INC from
        # ALT_INC2 (odd-first), so slice-timing consumers should still cross-check
        # the acquisition order. Anything unmapped (e.g. User_defined_slice_scheme)
        # stays 0 = NIFTI_SLICE_UNKNOWN.
        slice_code = {
            'Sequential':         1,   # NIFTI_SLICE_SEQ_INC
            'Reverse_sequential': 2,   # NIFTI_SLICE_SEQ_DEC
            'Interlaced':         3,   # NIFTI_SLICE_ALT_INC
            'Reverse_interlaced': 4,   # NIFTI_SLICE_ALT_DEC
        }.get(self.info.slicepack['slice_order_scheme'], 0)

        if slice_code == 0:
            warnings.warn(
                "Failed to identify compatible 'slice_code'. "
                "Please use this header information with care in case slice timing correction is needed."
            )
        self.nifti1image.header['slice_code'] = slice_code

    def _set_slice_extent(self):
        # A slice_code is inert without the slice axis and the slice range it
        # applies to. The assembly pipeline always places the slice axis third
        # (k), spanning the whole volume, so record that. The freq/phase entries
        # of dim_info are left unset here: mapping them onto the reoriented image
        # axes belongs with PhaseEncodingDirection, not this field.
        if self.nifti1image.ndim >= 3:
            self.nifti1image.header.set_dim_info(slice=2)
            self.nifti1image.header['slice_start'] = 0
            self.nifti1image.header['slice_end'] = self.nifti1image.shape[2] - 1

    def _set_time_step(self):
        # Bruker voxel geometry is always in mm; label the spatial units
        # unconditionally so they are not left NIFTI_UNITS_UNKNOWN. A 4D series
        # additionally carries a per-volume time step (seconds) on pixdim[4].
        #
        # The step is the sequence repetition time (VisuAcqRepetitionTime), the
        # same source BIDS RepetitionTime is derived from, so the NIfTI header and
        # the JSON sidecar always agree (avoids BIDS REPETITION_TIME_MISMATCH). The
        # old cycle time_step (VisuAcqScanTime/num_cycles) is a per-cycle interval
        # that disagrees with RepetitionTime whenever a cycle spans more than one
        # volume (e.g. tag/control ASL), and it was only applied when a cycle frame
        # group was detected -- leaving other 4D series with unset time units.
        if self.nifti1image.ndim >= 4:
            tr_ms = self.info.cycle.get('repetition_time')
            # VisuAcqRepetitionTime is a list for variable-TR sequences (e.g. RARE-VTR);
            # a single pixdim[4] cannot represent that, and the BIDS RepetitionTime
            # sidecar is likewise omitted, so set the step only for a scalar TR.
            if isinstance(tr_ms, (int, float, np.integer, np.floating)) and not isinstance(tr_ms, bool):
                time_step = tr_ms / 1000
                self.nifti1image.header['pixdim'][4] = time_step
                num_slices = self.info.slicepack['num_slices_each_pack'][0]
                if num_slices:
                    self.nifti1image.header['slice_duration'] = time_step / num_slices
            self.nifti1image.header.set_xyzt_units('mm', 'sec')
        else:
            self.nifti1image.header.set_xyzt_units('mm')
            
    def _set_sform_qform(self):
        # A Nifti1Image built from an affine defaults to sform_code=2 (ALIGNED)
        # with the qform left unset (code 0). This data comes straight off the
        # scanner, so tag both forms with the same affine and code 1
        # (NIFTI_XFORM_SCANNER_ANAT): sform-first tools are unaffected, and tools
        # that honor only the qform now get the correct orientation too.
        affine = self.nifti1image.affine
        self.nifti1image.header.set_qform(affine, code=1)
        self.nifti1image.header.set_sform(affine, code=1)

    def _set_cal_and_descrip(self):
        # cal_min/cal_max give viewers a default display window; NIfTI expects
        # them in true (post-scaling) units. With scalar scl_slope/scl_inter in
        # the header the stored data is raw, so scale the min/max to true units
        # (a negative slope flips the ordering). When scaling is baked into the
        # data ('apply') or is per-frame, the array already holds true values.
        self.nifti1image.header['descrip'] = b'brkraw-legacy'
        data = np.asarray(self.nifti1image.dataobj)
        if not data.size:
            return
        lo, hi = float(np.nanmin(data)), float(np.nanmax(data))
        if self.scale_mode:
            slope = self.info.dataarray['slope']
            inter = self.info.dataarray['offset']
            if not (np.ndim(slope) or np.ndim(inter)):
                lo, hi = slope * lo + inter, slope * hi + inter
                lo, hi = min(lo, hi), max(lo, hi)
        self.nifti1image.header['cal_min'] = lo
        self.nifti1image.header['cal_max'] = hi

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