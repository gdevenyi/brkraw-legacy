# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BrkRaw is a Python library for accessing and converting raw MRI data from Bruker Biospin preclinical scanners. It provides a CLI (`brkraw`, `brk-backup`) and Python API for reading Bruker PvDatasets (directory or ZIP), reconstructing images, and exporting to NIfTI/BIDS formats.

Currently on `legacy` branch (v0.4.0 WIP).

## Build & Development Commands

```bash
uv sync                       # Install project with dev dependencies (editable)
uv pip install .              # Base install (non-editable)
uv pip install .[all]         # All optional features (nibabel, SimpleITK, legacy)

# Testing
make tests/tutorials         # Clone tutorial data (required before running tests)
uv run pytest                # Run all tests (debug logging enabled by default)
uv run pytest tests/01_api_pvobj_test.py  # Run a single test file

# Linting
uv run ruff check .            # Uses ruff defaults

# Demo / smoke test
make demo
```

## Architecture

### Data flow

```
Raw Bruker Data (directory or ZIP)
  → BrukerLoader (lib/loader.py)     — main entry point, also exposed as brkraw.load()
    → PvStudy (api/pvobj/)           — represents a session with multiple scans
      → PvScan → PvReco             — individual scan and reconstruction data
        → NIfTI/BIDS export          — via app/tonifti/
```

### Key layers

- **`brkraw/lib/`** — Low-level: `BrukerLoader` (loader.py), parameter parsing (parser.py), orientation/affine math (orient.py), image reconstruction (recon.py, recoFunctions.py), BIDS metadata references (reference.py), custom exceptions (errors.py)
- **`brkraw/api/pvobj/`** — Mid-level object model: `PvStudy`, `PvScan`, `PvReco`, `PvFiles`, `Parameter`. All inherit from `BaseMethods`/`BaseBufferHandler` for file/buffer handling
- **`brkraw/api/analyzer/`** — Data analysis utilities
- **`brkraw/api/data/`** — Data container classes
- **`brkraw/app/tonifti/`** — High-level NIfTI conversion: `StudyToNifti`, `ScanToNifti`, `ToNiftiPlugin`
- **`brkraw/scripts/`** — CLI entry points (`brkraw.py` with subcommands: info, tonii, tonii_all, bids_helper, bids_convert)

### External dependencies of note

- **xnippet** (PyPI) — configuration management framework, used for `XnippetManager` in `__init__.py`
- **reshipe** — data handling utilities
- **nibabel** — NIfTI format support (optional)

## Testing

Tests are numbered by layer: `01_api_pvobj`, `02_api_analyzer`, `03_api_helper`, `04_api_data`, `05_app_tonifti`. They require tutorial sample data — run `make tests/tutorials` first. CI runs on Python 3.11–3.14 across Ubuntu/Windows/macOS.

## Linting

Ruff for linting. Type checking config in `mypy.ini`.
