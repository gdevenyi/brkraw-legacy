# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BrkRaw-legacy is a Python library for accessing and converting raw MRI data from Bruker Biospin preclinical scanners. It provides a CLI (`brkraw-legacy`, `brk-legacy-backup`) and Python API for reading Bruker PvDatasets (directory or ZIP), reconstructing images, and exporting to NIfTI/BIDS formats.

This is a hard fork of the upstream [BrkRaw](https://github.com/BrkRaw/brkraw) 0.3.x/0.4 line, developed independently of upstream 0.5+. The distribution is `brkraw-legacy`, the import package is `brkraw_legacy`. Current version: 0.4.0.

## Build & Development Commands

```bash
uv sync                       # Runtime deps only (editable install)
uv sync --extra dev           # Also install pytest/ruff/bids-validator (needed to run tests)

# Testing
uv run pytest                       # All tests (sample data auto-fetched from the network)
uv run pytest -m "not data"         # Only the offline unit tests (no downloads)
uv run pytest tests/01_api_pvobj_test.py  # Run a single test file

# Linting
uv run ruff check .            # Uses ruff defaults
```

## Architecture

### Data flow

```
Raw Bruker Data (directory or ZIP)
  → BrukerLoader (lib/loader.py)     — main entry point, also exposed as brkraw_legacy.load()
    → PvStudy (api/pvobj/)           — represents a session with multiple scans
      → PvScan → PvReco             — individual scan and reconstruction data
        → NIfTI/BIDS export          — via app/tonifti/
```

### Key layers

- **`brkraw_legacy/lib/`** — Low-level: `BrukerLoader` (loader.py), parameter parsing (parser.py), orientation/affine math (orient.py), image reconstruction (recon.py, recoFunctions.py), BIDS entity/filename rules (bids.py), BIDS metadata references (reference.py), custom exceptions (errors.py)
- **`brkraw_legacy/api/pvobj/`** — Mid-level object model: `PvStudy`, `PvScan`, `PvReco`, `PvFiles`, `Parameter`. All inherit from `BaseMethods`/`BaseBufferHandler` for file/buffer handling
- **`brkraw_legacy/api/analyzer/`** — Data analysis utilities
- **`brkraw_legacy/api/data/`** — Data container classes
- **`brkraw_legacy/app/tonifti/`** — High-level NIfTI conversion: `StudyToNifti`, `ScanToNifti`, `ToNiftiPlugin`
- **`brkraw_legacy/scripts/`** — CLI entry points (`brkraw_legacy.py` with subcommands: info, tonii, tonii_all, bids_helper, bids_convert)

### External dependencies of note

- **xnippet** (PyPI) — configuration management framework, used for `XnippetManager` in `__init__.py`
- **reshipe** — data handling utilities
- **nibabel** — NIfTI format support (required, used in orientation math and conversion)
- **pybids** — BIDS entity/datatype definitions, used by `lib/bids.py`

## Testing

Tests are numbered by layer: `01_api_pvobj`, `02_api_analyzer`, `03_api_helper`, `04_api_data`, `05_app_tonifti`, `06_bids`, `07_conversion`, `08_orientation`. Data-dependent tests are marked `data` and fetch public sample data from the network (Zenodo / GitHub), cached under `$BRKRAW_TEST_DATA_DIR`; `pytest -m "not data"` runs only the offline unit tests. CI runs the unit suite on Python 3.11–3.14 across Ubuntu/Windows/macOS and the `data` suite once on Ubuntu.

## Linting

Ruff for linting. Type checking config in `mypy.ini`.

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`gdevenyi/brkraw-legacy`), via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical default labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
