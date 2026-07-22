"""Scan information analysis module.

This module defines the ScanInfoAnalyzer, which is essential for parsing and interpreting
metadata from multiple parameter files, making it more human-readable and accessible
for further processing and analysis tasks.
"""

from __future__ import annotations
from collections import OrderedDict
from brkraw_legacy.api import helper
from .base import BaseAnalyzer
from typing import TYPE_CHECKING, Optional, Union
if TYPE_CHECKING:
    from ..pvobj import PvScan, PvReco, PvFiles


class ScanInfoAnalyzer(BaseAnalyzer):
    """Helps parse metadata from multiple parameter files to make it more human-readable.

    This analyzer is crucial for reconstructing and interpreting various scan parameters
    from raw dataset files, supporting enhanced data insights and accessibility.

    Args:
        pvobj (Union[PvScan, PvReco, PvFiles]): The PvObject containing various acquisition
            and method parameters.
        reco_id (int, optional): Specifies the reconstruction ID for targeted analysis.
            Defaults to None.
        debug (bool): Flag to enable debugging outputs for detailed tracing.

    Attributes:
        info_protocol (dict): Stores protocol-related information.
        info_fid (dict): Contains information extracted from FID files.
        visu_pars (OrderedDict): Visualization parameters extracted for analysis.
    """
    def __init__(self, 
                 pvobj: Union['PvScan', 'PvReco', 'PvFiles'], 
                 reco_id:Optional[int] = None, 
                 debug:bool = False):
        """Initialize the ScanInfoAnalyzer with specified parameters and optionally in debug mode.
        """
        self._set_pars(pvobj, reco_id)
        if not debug:
            self.info_protocol = helper.Protocol(self).get_info()
            self.info_fid = helper.FID(self).get_info()
            if self.visu_pars:
                self._parse_info()
    
    def _set_pars(self, pvobj: Union['PvScan', 'PvReco', 'PvFiles'], reco_id: Optional[int]):
        """Set parameters from the PvObject for internal use."""
        for p in ['acqp', 'method']:
            try:
                vals = getattr(pvobj, p)
            except AttributeError:
                vals = OrderedDict()
            setattr(self, p, vals)
        # The fid (raw k-space) is not read for scan info -- FID.get_info derives
        # the fid dtype from acqp -- so it is not opened here; opening it only
        # leaked the handle.
        try:
            visu_pars = pvobj.get_visu_pars(reco_id)
        except (FileNotFoundError, AttributeError):
            visu_pars = OrderedDict()
        self._inherit_acq_params(pvobj, reco_id, visu_pars)
        setattr(self, 'visu_pars', visu_pars)

    @staticmethod
    def _inherit_acq_params(pvobj, reco_id, visu_pars):
        """Complete a derived reconstruction's parameters with acquisition-level
        Visu parameters it omits.

        A scan has one acquisition but several reconstructions. Acquisition
        parameters (``VisuAcq*``) describe that shared acquisition, not a
        reconstruction's geometry, so an extra reco can leave them out (e.g.
        ``VisuAcqGradEncoding`` / ``VisuAcqImagePhaseEncDir`` on a computed
        T2/ADC map). Source only those from the primary (first) reconstruction,
        where they always live; reconstruction-specific parameters (``VisuCore*``,
        ``VisuFG*``, ...) are left to the reco itself so its own geometry is used.
        """
        try:
            recos = pvobj.avail
        except AttributeError:
            return
        if not recos or reco_id in (None, recos[0]):
            return
        try:
            primary = pvobj.get_visu_pars(recos[0])
        except (FileNotFoundError, AttributeError):
            return
        target = visu_pars.parameters if hasattr(visu_pars, 'parameters') else visu_pars
        have = set(visu_pars.keys())
        for key in primary.keys():
            if key.startswith('VisuAcq') and key not in have:
                target[key] = primary[key]
           
    def _parse_info(self):
        """Parse and process detailed information from the visualization parameters and other sources.
        """
        self.info_dataarray = helper.DataArray(self).get_info()
        self.info_frame_group = helper.FrameGroup(self).get_info()
        self.info_image = helper.Image(self).get_info()
        self.info_slicepack = helper.SlicePack(self).get_info()
        self.info_cycle = helper.Cycle(self).get_info()
        self.info_diffusion = helper.Diffusion(self).get_info()
        if self.info_image['dim'] > 1:
            self.info_orientation = helper.Orientation(self).get_info()
    
    def __dir__(self):
        """List dynamic attributes of the instance related to informational properties.
        """
        return [attr for attr in self.__dict__.keys() if 'info_' in attr]
    
    def get(self, key):
        """Retrieve information properties based on a specified key.
        """
        return getattr(self, key) if key in self.__dir__() else None