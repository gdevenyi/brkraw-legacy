"""Unit tests for the ScanInfo helper classes (api.helper).

Pure-unit (offline): a slice pack's distance must be one scalar per pack, even
when a derived reconstruction reports the frame thickness per frame.
"""
from brkraw_legacy.api.helper.slicepack import SlicePack


class _FakeAnal:
    """Minimal ScanInfoAnalyzer stand-in: a single-slice reconstruction whose
    frames are a non-spatial group (e.g. an ISA parametric map like an MGE
    T2* map), where VisuCoreFrameThickness may be stored per frame."""
    def __init__(self, thickness):
        self.method = {}
        self.visu_pars = {
            'VisuVersion': 5,
            'VisuCoreFrameThickness': thickness,
            'VisuCoreDiskSliceOrder': 'normal',
        }
        self._info = {
            'info_frame_group': {'type': 'FG_ISA', 'id': ['FG_ISA'], 'shape': [6]},
            'info_image': {'dim': 2},
        }

    def get(self, key):
        return self._info.get(key)


def test_slicepack_collapses_per_frame_thickness():
    """A per-frame thickness list collapses to one scalar distance per pack, so
    the affine's (x, y, z) resolution does not become ragged."""
    info = SlicePack(_FakeAnal(thickness=[1, 1, 1, 1, 1, 1])).get_info()
    assert info['slice_distances_each_pack'] == [1]


def test_slicepack_keeps_scalar_thickness():
    """A scalar thickness is left as one distance per pack, unchanged."""
    info = SlicePack(_FakeAnal(thickness=1)).get_info()
    assert info['slice_distances_each_pack'] == [1]
