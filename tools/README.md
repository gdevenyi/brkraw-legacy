# Conversion sweep tooling

Developer scripts that exercise **every** convertible unit under a test-data
tree, to surface conversion/BIDS bugs the targeted test suite doesn't reach
(it only touches a handful of scans/recos per fixture). These found the bugs
fixed in the accompanying PRs.

They are plain scripts (not part of the package or the pytest suite); run them
against a local data tree such as the git-ignored `resources/testdata/`.

## `sweep_nifti.py` — raw → NIfTI sweep

Discovers every unit (full study dir, `.zip`/`.PvDatasets` archive, or
standalone exported scan dir), runs `get_niftiobj()` on every `(scan, reco)`,
and classifies each as **ok** / **skip-nonimage** (clean rejection) / **FAIL**
(a real conversion bug). Writes a JSON report and prints a per-unit summary with
every failure's message.

```bash
uv run python tools/sweep_nifti.py [TESTDATA_DIR] [OUT.json]
# defaults: resources/testdata, ./sweep_nifti_results.json
```

## `sweep_bids.py` — BIDS conversion sweep

Runs the real `bids_helper` → `bids_convert` pipeline on every study/archive
unit (symlinked into a throwaway parent, using the auto-generated datasheet),
captures crashes, and validates each output with `bids-validator-deno` if
present.

```bash
uv run python tools/sweep_bids.py [TESTDATA_DIR] [OUT.json]
```

## Notes

- Both take the data dir as `argv[1]`; point them at a subtree to scope a run.
- `_sources`, `_cache`, `.git`, and hidden files are skipped during discovery.
- Study roots are found by a `subject` file; standalone scans by a bare `acqp`.
