# ADR 0001: One affine/orientation implementation (`AffineAnalyzer`)

- Status: Accepted
- Date: 2026-07-21

## Context

Two independent implementations computed the same NIfTI affine from the same
Bruker parameters:

- **Loader path** — `BrukerLoader._get_affine` → `_get_orient_info`
  (`lib/loader.py`) → `lib/orient.py` (`build_affine_from_orient_info`,
  `get_origin`, `reversed_pose_correction`, `calc_eulerangle`).
- **app.tonifti path** — `AffineAnalyzer` (`api/analyzer/affine.py`) →
  `Orientation` (`api/helper/orientation.py`).

Both consume the same ground-truth parameters (see `FILE_FORMAT.md`):
`VisuCoreOrientation` (patient→image, `i = M·p`, §7.2/§12), `VisuCorePosition`
(first-voxel-center in the DICOM patient frame, §7.2), `VisuCoreDiskSliceOrder`
(§7.3), `VisuCoreSlicePacksSlices` (per-package slice counts, §7.10), and
`VisuSubjectType`/`VisuSubjectPosition` (§7.5/§7.7). They reimplemented the same
spec twice — the slice-orientation map, the reverse-slice correction, the
Euler-angle origin selection, the pose rotation, and the quadruped-frame
rotation each existed in two copies.

Duplication cost real correctness. The copies drifted: `lib/orient.get_origin`
carried live bugs in untested branches (`.argmaxs()`, an inverted axial
`argmax`/`argmin`) that the `AffineAnalyzer` path had already fixed. A whole
regression test (`08_orientation_test.py`) existed only to pin the two paths
together, and six commits churned it keeping them in sync. Every orientation fix
had to land in both places or silently desync.

The `app.tonifti` path was already the canonical, spec-faithful one, and image
assembly (`get_niftiobj`) had already been routed through it.

## Decision

There is **one** affine/orientation implementation: `AffineAnalyzer` (with
`Orientation`), reached through the `app.tonifti` API.

- `BrukerLoader.get_affine`, `get_niftiobj`, and `get_sitkimg` delegate through
  a single `_scan_bridge` helper to a `ScanToNifti`, so the loader/CLI path, the
  BIDS conversion, and the `app.tonifti` API share one affine and one header.
- Subject-type/position overrides ride through as explicit
  `subj_type`/`subj_position` arguments; `None` lets the analyzer read them
  per-scan from `VisuSubjectType`/`VisuSubjectPosition` (never the study
  `subject` file — PV5 writes `SUBJECT_type=Human` unconditionally, §7.5).
- Standalone (individually-exported) scan directories route through the
  scan-level `ScanToNifti`, which constructs a `PvScan` directly from an
  `acqp`/`method`/`pdata` directory (§1.2).
- `lib/orient.py` and the loader's `_get_affine` / `_get_orient_info` /
  `_assemble_standalone` / `_set_nifti_header` are deleted.

The loader keeps the non-affine parameter helpers it still needs
(`_get_slice_info`, `_get_spatial_info`, `_get_matrix_size`).

## Consequences

- **Locality:** an orientation fix lands in exactly one module. The two-path
  pinning test and its maintenance churn are gone.
- **Behaviour change (intended):** any dataset outside the test fixtures whose
  loader-path affine differed from the analyzer path now gets the analyzer's
  (bug-fixed) affine. This was not pinned with golden values; it is the intended
  correctness improvement.
- Standalone conversion now shares the same header/scale handling as every other
  scan (the tonifti `Header`), rather than a bespoke `_set_nifti_header`.

## Do not re-litigate

Do not reintroduce a loader-side affine or a second orientation module. If a new
entry point needs an affine, feed a `ScanToNifti`/`AffineAnalyzer` — do not
recompute it from `visu_pars`. The deletion of `lib/orient.py` was deliberate.
