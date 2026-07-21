"""BIDS path-builder and end-to-end conversion tests.

The unit tests exercise ``brkraw_legacy.lib.bids`` directly and need no sample
data. The end-to-end tests convert a public sample study (lego_phantom); the
validator check is skipped unless the ``bids-validator`` (Deno) binary is
available.
"""
import json
import shutil
import subprocess

import pytest

from brkraw_legacy.lib import bids
from brkraw_legacy.lib.errors import InvalidApproach


# --------------------------------------------------------------------------- #
# Unit tests: schema-driven path builder
# --------------------------------------------------------------------------- #

def test_entity_order_rec_before_dir():
    """Regression: the old code emitted dir- before rec-, violating the spec."""
    ents = dict(subject='01', task='t', acquisition='hi', ceagent='gd',
                reconstruction='x', direction='AP')
    _, stem = bids.build_path(ents, 'func', 'bold')
    assert stem == 'sub-01_task-t_acq-hi_ce-gd_rec-x_dir-AP_bold'
    assert stem.index('_rec-') < stem.index('_dir-')


def test_func_suffix_is_lowercase_bold():
    rel_dir, stem = bids.build_path(dict(subject='01', task='rest'), 'func', 'bold')
    assert rel_dir == 'sub-01/func'
    assert stem.endswith('_bold')


def test_session_in_path_and_name():
    rel_dir, stem = bids.build_path(dict(subject='01', session='pre', task='rest'),
                                    'func', 'bold')
    assert rel_dir == 'sub-01/ses-pre/func'
    assert stem.startswith('sub-01_ses-pre_')


def test_anat_and_dwi_and_fmap_paths():
    assert bids.build_path(dict(subject='01'), 'anat', 'T2w') == ('sub-01/anat', 'sub-01_T2w')
    assert bids.build_path(dict(subject='01'), 'dwi', 'dwi') == ('sub-01/dwi', 'sub-01_dwi')
    # bare `magnitude` is valid in the schema (pybids' bundled patterns wrongly reject it)
    assert bids.build_path(dict(subject='01'), 'fmap', 'magnitude') == ('sub-01/fmap', 'sub-01_magnitude')
    assert bids.build_path(dict(subject='01'), 'fmap', 'fieldmap') == ('sub-01/fmap', 'sub-01_fieldmap')


def test_invalid_suffix_rejected():
    with pytest.raises(InvalidApproach):
        bids.build_path(dict(subject='01'), 'func', 'EPI')        # method-derived junk
    with pytest.raises(InvalidApproach):
        bids.build_path(dict(subject='01'), 'etc', 'whatever')    # not a BIDS datatype


def test_default_suffix_mapping():
    assert bids.default_suffix('func', 'epi:EPI') == 'bold'
    assert bids.default_suffix('dwi', 'dti:DtiEpi') == 'dwi'
    assert bids.default_suffix('anat', 'x:FLASH') == 'FLASH'
    assert bids.default_suffix('anat', 'x:RARE') == 'T2w'
    assert bids.default_suffix('anat', 'x:MSME') == 'MESE'
    assert bids.default_suffix('etc', 'something') is None        # unknown -> no suffix


def test_build_prefix_excludes_run_echo_and_suffix():
    """FileName carries the prefix; run/echo/suffix are appended downstream."""
    rel_dir, prefix = bids.build_prefix(dict(subject='01', task='rest', run='02', echo='1'),
                                        'func')
    assert prefix == 'sub-01_task-rest'
    assert 'run-' not in prefix and 'echo-' not in prefix


def test_label_validation():
    assert bids.is_valid_label('abc123')
    assert not bids.is_valid_label('a_b')
    assert not bids.is_valid_label('a-b')


# --------------------------------------------------------------------------- #
# End-to-end: convert a public dataset and validate it
# --------------------------------------------------------------------------- #

def _validator_bin():
    return shutil.which('bids-validator-deno') or shutil.which('bids-validator')


def _prepare_anat_dataset(pvdir, tmp_path):
    """Run bids_helper, fill in a couple of valid anat rows, and convert.

    The sample scans have no auto-classifiable BIDS datatype, so we rewrite two
    single-volume 3D scans as anat/T2starw to exercise a real, validatable
    conversion (multi-slicepack scouts would split into several files and are
    skipped). Only the chosen study is exposed (via a symlinked parent) so the
    helper converts just it.
    """
    import pandas as pd
    from brkraw_legacy import BrukerLoader

    # Pick scans that convert to a single 3D image, so each yields one clean
    # anat file rather than a per-slicepack _T2starw-01/-02/... split.
    loader = BrukerLoader(str(pvdir))
    simple = []
    for sid in loader.pvobj.avail_scan_id:
        try:
            obj = loader.get_niftiobj(sid, 1)
        except Exception:
            continue
        if not isinstance(obj, list) and getattr(obj, 'ndim', 0) == 3:
            simple.append(sid)
        if len(simple) >= 2:
            break
    assert simple, 'no single-volume 3D scan available for anat conversion'

    sample_parent = tmp_path / 'sample'
    sample_parent.mkdir()
    (sample_parent / pvdir.name).symlink_to(pvdir.resolve())
    sheet = tmp_path / 'bids_map'
    out = tmp_path / 'raw'

    subprocess.check_call(['brkraw-legacy', 'bids_helper', str(sample_parent),
                           str(sheet), '-j'])
    df = pd.read_csv(str(sheet) + '.csv')

    # First reco of each chosen scan -> anat T2starw with a distinguishing acq.
    first_recos = df[df['RecoID'] == df.groupby('ScanID')['RecoID'].transform('min')]
    df = first_recos[first_recos['ScanID'].isin(simple)].drop_duplicates('ScanID').copy()
    assert len(df) >= 1, 'no scans available in dataset'
    df['SubjID'] = '001'
    df['SessID'] = ''
    df['DataType'] = 'anat'
    df['modality'] = 'T2starw'
    df['acq'] = ['scan{}'.format(i) for i in range(len(df))]
    df.to_csv(str(sheet) + '.csv', index=False)

    subprocess.check_call(['brkraw-legacy', 'bids_convert', str(sample_parent),
                           str(sheet) + '.csv', '-j', str(sheet) + '.json',
                           '--output', str(out)])
    return out


def test_end_to_end_bids_convert(lego_study, tmp_path):
    out = _prepare_anat_dataset(lego_study, tmp_path)

    # dataset_description.json: required keys, correct spelling, modern version
    desc = json.loads((out / 'dataset_description.json').read_text())
    assert desc['BIDSVersion'] == '1.10.0'
    assert desc['DatasetType'] == 'raw'
    assert any(g['Name'] == 'BrkRaw-legacy' for g in desc['GeneratedBy'])
    for typo in ('HowToAsknowledge', 'EthicApprovals', 'ReferenceAndLinks'):
        assert typo not in desc

    # At least one anat image + sidecar produced, in spec-correct location.
    niis = list(out.rglob('sub-001/anat/*_T2starw.nii.gz'))
    assert niis, 'expected anat NIfTI output'

    # No sidecar should contain placeholder junk, echoed parameter names or the
    # old invalid IntendedFor key/glob.
    for js in out.rglob('*.json'):
        text = js.read_text()
        assert 'Value was not specified' not in text
        assert 'IntendFor' not in text                 # old typo'd key
        assert '*_bold.nii.gz' not in text             # old invalid glob
        assert 'Visu' not in text                       # echoed Bruker param name


@pytest.mark.skipif(_validator_bin() is None, reason='bids-validator (deno) not available')
def test_end_to_end_passes_validator(lego_study, tmp_path):
    out = _prepare_anat_dataset(lego_study, tmp_path)

    proc = subprocess.run([_validator_bin(), str(out), '--json'],
                          capture_output=True, text=True)
    report = json.loads(proc.stdout or '{}')
    issues = report.get('issues', {})
    items = issues.get('issues', issues) if isinstance(issues, dict) else issues
    errors = [it for it in (items or []) if it.get('severity') == 'error']
    assert not errors, 'bids-validator reported errors: {}'.format(
        [(e.get('code'), e.get('subCode')) for e in errors])


def test_multiecho_gets_echo_entity(lego_study, tmp_path):
    """A multi-echo scan converts to one BIDS ``_echo-<n>_`` file per echo.

    Pins the BIDS naming now that image assembly is delegated to app.tonifti:
    ``is_multi_echo`` and the API's per-echo split must agree so build_bids_json
    emits ``_echo-1_``, ``_echo-2_``, ... rather than a generic ``-01`` suffix.
    """
    import types

    from brkraw_legacy import BrukerLoader
    from brkraw_legacy.lib.utils import build_bids_json

    d = BrukerLoader(str(lego_study))
    scan = next((s for s in d.pvobj.avail_scan_id if d.is_multi_echo(s, 1)), None)
    if scan is None:
        pytest.skip('no multi-echo scan in sample')
    n_echo = d.is_multi_echo(scan, 1)
    row = types.SimpleNamespace(ScanID=scan, RecoID=1, task=None, DataType='anat',
                                Start=None, End=None, modality='T2starw',
                                Dir=str(tmp_path), FileName='sub-001', run=None)
    build_bids_json(d, row, 'sub-001', None)
    niis = sorted(p.name for p in tmp_path.glob('*.nii.gz'))
    assert niis == ['sub-001_echo-{}_T2starw.nii.gz'.format(i + 1) for i in range(n_echo)]
