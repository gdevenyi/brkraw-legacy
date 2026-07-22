import types

from brkraw_legacy.api.data import Study
from brkraw_legacy.api.data import scan as scan_mod
from brkraw_legacy.api.data.scan import Scan


def test_data_init(dataset):
    """The high-level Study container builds from each study and lists its scans."""
    for pvobj in dataset.values():
        studyobj = Study(pvobj.path)
        assert studyobj.avail, 'Study should enumerate available scans'


# --------------------------------------------------------------------------- #
# get_datarray_analyzer must read the *requested* reco's parameters
# --------------------------------------------------------------------------- #

def _fake_scan(monkeypatch, captured):
    """A Scan stand-in recording what DataArrayAnalyzer is built from.

    ``get_scaninfo`` and ``get_2dseq`` tag their return with the reco they were
    asked for, so a test can tell which reconstruction's info/data was used.
    """
    monkeypatch.setattr(scan_mod, 'DataArrayAnalyzer',
                        lambda info, fileobj: captured.update(info=info, fileobj=fileobj))
    pvobj = types.SimpleNamespace(get_2dseq=lambda reco_id=None: f'2dseq-r{reco_id}')
    return types.SimpleNamespace(
        reco_id=1,
        info='info-default(r1)',            # cached info for the scan's default reco
        _buffers=[],
        retrieve_pvobj=lambda: pvobj,
        get_scaninfo=lambda reco_id=None, get_analyzer=False: f'info-fetched(r{reco_id})')


def test_datarray_analyzer_reads_requested_reco_params(monkeypatch):
    """A derived reconstruction is decoded with its own parameters (word type,
    matrix, frame count), not the scan's default reco. Regression: reco 4+ of a
    multi-reco scan crashed reshaping because the default reco's info was reused.
    """
    captured = {}
    Scan.get_datarray_analyzer(_fake_scan(monkeypatch, captured), reco_id=4)
    assert captured['fileobj'] == '2dseq-r4'        # the requested reco's data ...
    assert captured['info'] == 'info-fetched(r4)'   # ... and the requested reco's info


def test_datarray_analyzer_defaults_to_cached_info(monkeypatch):
    """With no reco_id the scan's default reconstruction and cached info are used."""
    captured = {}
    Scan.get_datarray_analyzer(_fake_scan(monkeypatch, captured))
    assert captured['fileobj'] == '2dseq-r1'        # falls back to self.reco_id
    assert captured['info'] == 'info-default(r1)'   # cached info reused
