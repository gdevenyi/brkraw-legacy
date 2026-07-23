#!/usr/bin/env python3
"""NIfTI-conversion sweep over every Bruker unit under resources/testdata.

For each discovered unit (full study dir, .zip/.PvDatasets archive, or
standalone exported scan dir) run get_niftiobj() on every (scan, reco) and
classify: ok / skip-nonimage (clean rejection) / FAIL (a real conversion bug).
Writes a JSON report and prints a per-unit summary with every failure's message.
"""
import json
import logging
import sys
import traceback
import warnings
from pathlib import Path

logging.disable(logging.CRITICAL)  # silence brkraw's own logging noise

from brkraw_legacy import BrukerLoader  # noqa: E402

_REPO = Path(__file__).resolve().parent.parent
TESTDATA = Path(sys.argv[1]) if len(sys.argv) > 1 else _REPO / 'resources' / 'testdata'
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else 'sweep_nifti_results.json')

EXCLUDE_PARTS = {'_sources', '_cache', '.git'}


def excluded(p: Path) -> bool:
    # skip explicit dirs and any hidden file/dir (e.g. extraction markers)
    return any(part in EXCLUDE_PARTS or part.startswith('.') for part in p.parts
               if part not in ('.', '..'))


def discover(root: Path):
    """Return list of (label, path, kind)."""
    units = []
    # 1. archives brkraw reads directly
    for pat in ('*.zip', '*.PvDatasets'):
        for p in sorted(root.rglob(pat)):
            if p.is_file() and not excluded(p):
                units.append((str(p.relative_to(root)), p, 'archive'))
    # 2. full studies (a 'subject' file marks a PvStudy root)
    study_roots = set()
    for s in sorted(root.rglob('subject')):
        if s.is_file() and not excluded(s):
            study_roots.add(s.parent)
            units.append((str(s.parent.relative_to(root)), s.parent, 'study'))
    # 3. standalone exported scans: a dir with acqp whose ancestors hold no
    #    'subject' file (i.e. not part of a study) and that isn't excluded.
    for aq in sorted(root.rglob('acqp')):
        d = aq.parent
        if excluded(d):
            continue
        if any(str(d).startswith(str(sr) + '/') or d == sr for sr in study_roots):
            continue  # a scan inside a full study -- already covered
        # only treat as standalone if it's a bare scan dir (acqp at root)
        units.append((str(d.relative_to(root)), d, 'standalone'))
    return units


def convert_unit(path: Path):
    rec = {'loadable': True, 'is_pvdataset': None, 'error': None, 'scans': []}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            loader = BrukerLoader(str(path))
    except Exception as e:
        rec['loadable'] = False
        rec['error'] = '{}: {}'.format(type(e).__name__, e)
        return rec
    rec['is_pvdataset'] = bool(getattr(loader, 'is_pvdataset', False))
    if not rec['is_pvdataset']:
        return rec
    try:
        avail = dict(loader.pvobj.avail_reco_id)
    except Exception as e:
        rec['error'] = 'avail_reco_id failed: {}: {}'.format(type(e).__name__, e)
        return rec
    for sid in sorted(avail):
        for rid in avail[sid]:
            entry = {'scan': int(sid), 'reco': int(rid)}
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    obj = loader.get_niftiobj(sid, rid)
                objs = obj if isinstance(obj, list) else [obj]
                entry['status'] = 'ok'
                entry['n_images'] = len(objs)
                entry['shapes'] = [list(getattr(o, 'shape', ())) for o in objs]
            except Exception as e:
                msg = '{}: {}'.format(type(e).__name__, e)
                if 'non-image data' in str(e):
                    entry['status'] = 'skip-nonimage'
                    entry['msg'] = str(e)[:200]
                else:
                    entry['status'] = 'FAIL'
                    entry['msg'] = msg[:400]
                    entry['tb'] = traceback.format_exc()[-1200:]
            rec['scans'].append(entry)
    return rec


def main():
    units = discover(TESTDATA)
    print('Discovered %d units under %s\n' % (len(units), TESTDATA))
    report = []
    for label, path, kind in units:
        rec = convert_unit(path)
        rec.update(label=label, path=str(path), kind=kind)
        report.append(rec)
        n_ok = sum(s['status'] == 'ok' for s in rec['scans'])
        n_skip = sum(s['status'] == 'skip-nonimage' for s in rec['scans'])
        n_fail = sum(s['status'] == 'FAIL' for s in rec['scans'])
        flag = 'FAIL' if (n_fail or not rec['loadable']) else 'ok  '
        note = ''
        if not rec['loadable']:
            note = ' LOAD-ERROR: ' + str(rec['error'])[:150]
        elif not rec['is_pvdataset']:
            note = ' (not a PvDataset)'
        print('[%s] %-4s ok=%-3d skip=%-3d FAIL=%-3d  %s%s' % (
            flag, kind[:4], n_ok, n_skip, n_fail, label[:70], note))
        for s in rec['scans']:
            if s['status'] == 'FAIL':
                print('        scan %s reco %s: %s' % (s['scan'], s['reco'], s['msg']))
    OUT.write_text(json.dumps(report, indent=2))

    # aggregate
    tot_ok = sum(s['status'] == 'ok' for r in report for s in r['scans'])
    tot_skip = sum(s['status'] == 'skip-nonimage' for r in report for s in r['scans'])
    tot_fail = sum(s['status'] == 'FAIL' for r in report for s in r['scans'])
    load_err = [r for r in report if not r['loadable']]
    print('\n==== TOTAL: ok=%d  skip-nonimage=%d  FAIL=%d  load-errors=%d ====' % (
        tot_ok, tot_skip, tot_fail, len(load_err)))
    print('Report -> %s' % OUT)


if __name__ == '__main__':
    main()
