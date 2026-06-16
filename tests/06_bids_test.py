"""BIDS path-builder and end-to-end conversion tests.

The unit tests exercise ``brkraw.lib.bids`` directly and need no sample data.
The end-to-end test is skipped unless a local Bruker dataset and the
``bids-validator`` (Deno) binary are both available.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from brkraw.lib import bids
from brkraw.lib.errors import InvalidApproach


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
# End-to-end: convert a local dataset and validate it
# --------------------------------------------------------------------------- #

_TESTDATA = Path(__file__).parents[1] / 'testdata'


# Prefer a clean PV6 study with real (non-truncated) image data for the e2e test.
_PREFERRED = _TESTDATA / 'pv6' / 'full' / 'mch_dev_022'


def _find_local_pvdataset():
    if not _TESTDATA.exists():
        return None
    if _PREFERRED.is_dir() and (_PREFERRED / 'subject').exists():
        return _PREFERRED
    # fall back to any full study under testdata/<pv>/full/
    for child in sorted(_TESTDATA.glob('*/full/*')):
        if child.is_dir() and (child / 'subject').exists():
            return child
    return None


def _validator_bin():
    return shutil.which('bids-validator-deno') or shutil.which('bids-validator')


def _prepare_anat_dataset(pvdir, tmp_path):
    """Run bids_helper, fill in a couple of valid anat rows, and convert.

    The local sample (Bruker FISP) has no auto-classifiable BIDS datatype, so we
    rewrite two scans as anat/T2starw to exercise a real, validatable conversion.
    Only the chosen study is exposed (via a symlinked parent) so the helper does
    not pick up other datasets that share testdata/.
    """
    import pandas as pd

    sample_parent = tmp_path / 'sample'
    sample_parent.mkdir()
    (sample_parent / pvdir.name).symlink_to(pvdir.resolve())
    sheet = tmp_path / 'bids_map'
    out = tmp_path / 'raw'

    subprocess.check_call(['brkraw', 'bids_helper', str(sample_parent),
                           str(sheet), '-j'])
    df = pd.read_csv(str(sheet) + '.csv')

    # First reco of the first two scans -> anat T2starw with distinguishing acq.
    first_recos = df[df['RecoID'] == df.groupby('ScanID')['RecoID'].transform('min')]
    picks = first_recos.drop_duplicates('ScanID').head(2).index
    assert len(picks) >= 1, 'no scans available in local dataset'
    df = df.loc[picks].copy()
    df['SubjID'] = '001'
    df['SessID'] = ''
    df['DataType'] = 'anat'
    df['modality'] = 'T2starw'
    df['acq'] = ['scan{}'.format(i) for i in range(len(df))]
    df.to_csv(str(sheet) + '.csv', index=False)

    subprocess.check_call(['brkraw', 'bids_convert', str(sample_parent),
                           str(sheet) + '.csv', '-j', str(sheet) + '.json',
                           '--output', str(out)])
    return out


@pytest.mark.skipif(_find_local_pvdataset() is None,
                    reason='no local Bruker dataset under ./testdata')
def test_end_to_end_bids_convert(tmp_path):
    out = _prepare_anat_dataset(_find_local_pvdataset(), tmp_path)

    # dataset_description.json: required keys, correct spelling, modern version
    desc = json.loads((out / 'dataset_description.json').read_text())
    assert desc['BIDSVersion'] == '1.10.0'
    assert desc['DatasetType'] == 'raw'
    assert any(g['Name'] == 'BrkRaw' for g in desc['GeneratedBy'])
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


@pytest.mark.skipif(_validator_bin() is None or _find_local_pvdataset() is None,
                    reason='bids-validator (deno) or local dataset not available')
def test_end_to_end_passes_validator(tmp_path):
    out = _prepare_anat_dataset(_find_local_pvdataset(), tmp_path)

    proc = subprocess.run([_validator_bin(), str(out), '--json'],
                          capture_output=True, text=True)
    report = json.loads(proc.stdout or '{}')
    issues = report.get('issues', {})
    items = issues.get('issues', issues) if isinstance(issues, dict) else issues
    errors = [it for it in (items or []) if it.get('severity') == 'error']
    assert not errors, 'bids-validator reported errors: {}'.format(
        [(e.get('code'), e.get('subCode')) for e in errors])
