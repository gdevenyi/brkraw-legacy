# Datasets

Publicly available Bruker/ParaVision datasets used with **brkraw-legacy** — in the
automated test suite and/or for manual validation during development.

None of the raw data is committed to this repository. The test suite fetches what
it needs from public sources at runtime (see `tests/conftest.py`), and any locally
cached validation data lives under the git-ignored `resources/testdata/` directory.

> **Licensing:** always check each dataset's own license before redistributing or
> using it commercially. Where a restriction is known it is noted below; where it
> is blank, consult the source. brkraw-legacy does not re-host any of this data.

## Used by the test suite & tutorials

The `tests/conftest.py` fixtures fetch the phantom studies on demand (cached under
`$BRKRAW_TEST_DATA_DIR`; `data`-marked tests skip if the source is unreachable).
The tutorial notebooks (run via `nbmake`) clone the `brkraw-dataset` repo.

| Dataset | ParaVision | Source | Notes |
|---|---|---|---|
| `0.2H2` | PV5.1 | [zenodo.org/records/4048286](https://zenodo.org/records/4048286) (`0.2H2.zip`) | Multi-sequence phantom study, 32 experiments. `h2_study` fixture. |
| `lego_phantom` | PV6.0.1 | [zenodo.org/records/4048253](https://zenodo.org/records/4048253) (`20200612_094625_lego_phantom_3_1_2.zip`) | Multi-sequence phantom study, 45 experiments. `lego_study` fixture; also the loader↔API parity and handle-leak tests. |
| `LEGO_PHANTOM_API_TEST` | PV7.0.0 | [zenodo.org/records/4522220](https://zenodo.org/records/4522220) (`20210128_122257_LEGO_PHANTOM_API_TEST_1_1.zip`, 618 MB) | Multi-sequence phantom study, 39 experiments (B1Map, CPMG, CSI, DESS, FLASH, RARE, EPI, UTE, …). `pv7_study` fixture; also `dataset[2]` in the loader sweep. Converts cleanly through brkraw-legacy: **30 image scans → NIfTI, 12 spectroscopic rejected cleanly, 0 failures**. Notes: PV7.0.0 uses `VisuVersion=3` (same as PV6); adds a `pdata/*/pvmeta` JCAMP file; the `fid.npz` files are NumPy arrays added by the BrukerAPI project, not native Bruker. |
| `PV360_StdData` | PV360 v3.6 | [github.com/cecilyen/PV360_StdData](https://github.com/cecilyen/PV360_StdData) (git-LFS) | Loose scan collection (no `subject` file). `pv360_root` fixture; standalone-scan and non-PvDataset tests. |
| `brkraw-dataset` (UNC) | PV5.1, PV6.0.1 | [github.com/BrkRaw/brkraw-dataset](https://github.com/BrkRaw/brkraw-dataset) (git-LFS) | brkraw's own example data: `PV5.1/UNC_PV5.1_BOLD-EPI_TurboRARE.zip`, `PV6.0.1/UNC_PV6.0.1_FLASH_TurboRARE_EPI.zip`. Used by the tutorial notebooks (`tests/tutorials/`, via `nbmake`); also cloned to `testdata/brkraw-dataset/` — both zips convert cleanly in the full sweep. |

`0.2H2`, `lego_phantom` and `LEGO_PHANTOM_API_TEST` are the
[BrukerAPI](https://github.com/isi-nmr/brukerapi-python) project's public test data. The
consolidated record [zenodo.org/records/4522220](https://zenodo.org/records/4522220) bundles all
three (`0.2H2.zip` PV5.1, `20200612_..._lego_phantom_...zip` PV6.0.1, and the
`20210128_..._LEGO_PHANTOM_API_TEST_...zip` PV7.0.0 study); the PV5.1/PV6.0.1 studies are also
available as the standalone records 4048286 / 4048253 used by the older fixtures.

## Used for local validation (git-ignored `resources/testdata/`)

Public datasets pulled locally to develop or verify a change; not part of CI.

| Dataset | ParaVision | Source | License | Notes |
|---|---|---|---|---|
| `bruker2nifti_qa` | PV5/6 | [gitlab.com/naveau/bruker2nifti_qa](https://gitlab.com/naveau/bruker2nifti_qa) (git-LFS) | see repo | Materialized at `testdata/bruker2nifti_qa/` (~340 MB LFS): 4 studies — Cyceron_DWI, Cyceron_MultiEcho, McGill_Orientation (×2). Source of the `cyceron_*` header stubs in `pv6/headers/`. Converts in the full sweep; a couple of derived DWI reconstructions fail on a missing `VisuAcqGradEncoding`. |
| MRIReco.jl test data | PV6.0.1 + PV360 V3.4 | [media.tuhh.de/ibi/mrireco/MRIRecoTestData.tar.gz](http://media.tuhh.de/ibi/mrireco/MRIRecoTestData.tar.gz) (`sha256 c5a421aab7f3ea3fb20c469704db33c17b659861d9d77dbd29e353db2d5c8fc7`) | see MRIReco.jl | Bruker scans: 2D/3D FLASH, 2D RARE, 3D UTE (radial + traj), PV360 CS FLASH. Surfaced/validated the headerless-`2dseq`, single-slice→3D, per-reco-params, and handle-leak fixes. |
| Aswendt GFAP PT 4wks | PV6.0.1 | [gin.g-node.org/Aswendt_Lab/2021_Aswendt_GFAP_PT_4wks](https://gin.g-node.org/Aswendt_Lab/2021_Aswendt_GFAP_PT_4wks) — DOI [10.12751/g-node.yzjhz3](https://doi.gin.g-node.org/10.12751/g-node.yzjhz3) | **CC BY-NC-SA 4.0** | Longitudinal mouse stroke study (raw Bruker + processed NIfTI), 82 GiB total via git-annex. One study pulled via GIN `/raw/` for validation; exposed the dangling-symlink `_fetch_dir` crash. NonCommercial → not suitable as a CI fixture. |
| PCI Standard Datasets | PV360 3.5 / 3.6 / 3.7 | Bruker download table ([login-gated page](https://www.bruker.com/protected/en/services/communities/pci-community/paravision-versions/paravision-standard-datasets.html); forum thread [988](https://pci-community.com/t/standard-datasets-for-pv360-3-5-3-6/988)) | **Bruker login; NOT re-hostable** — Bruker legal has not approved public mirroring ("please refrain from uploading the data to other servers") | 35 datasets on an ex-vivo mouse-head phantom: FLASH 2D/3D/iso, RARE T1/T2, MSME, MGE (positive & all echoes), EPI, DTI (30-dir, single & multi-shell), 3D UTE, PRESS. Downloaded to git-ignored `testdata/bruker_pv360_standard/` (2.1 GB, one `.PvDatasets` each). All 35 convert; surfaced the single-slice ISA parametric-map affine bug (fixed in #31). |

> Local, non-public acquisitions under `resources/testdata/` — `pv6/full/mch_dev_022` and
> `new-orientation/` (CIC phantom / plantest studies) — are intentionally omitted:
> they have no public source.

## Candidate datasets (found in the PCI-Community forum; not yet used)

From [pci-community.com](https://pci-community.com/) (Bruker Preclinical Imaging
Community; membership/login required). Bruker sample data and community
reconstruction repos that could extend coverage — none verified against
brkraw-legacy yet.

| Dataset | ParaVision | Source | Access / license | Notes |
|---|---|---|---|---|
| `SEQ_BRUKER_a_MP2RAGE_CS_360` | PV360 | [github.com/CRMSB/SEQ_BRUKER_a_MP2RAGE_CS_360](https://github.com/CRMSB/SEQ_BRUKER_a_MP2RAGE_CS_360) | public (see repo) | MP2RAGE compressed-sensing sequence + Julia recon and example Bruker images (BIDS export). Verify it ships raw data. |
| `SEQ_BRUKER_A_MP2RAGE_CS_PUBLIC` | PV6.0.1 | [github.com/aTrotier/SEQ_BRUKER_A_MP2RAGE_CS_PUBLIC](https://github.com/aTrotier/SEQ_BRUKER_A_MP2RAGE_CS_PUBLIC) | public (see repo) | MP2RAGE CS reconstruction + `pdata/$N` example. |
| `acidoCEST_MRI_Matlab` | — | [github.com/CAMEL-MartyPagel/acidoCEST_MRI_Matlab](https://github.com/CAMEL-MartyPagel/acidoCEST_MRI_Matlab) | public (see repo) | AcidoCEST analysis code "includes example data". |
| `Bruker_EPI_Reco` | — | [github.com/maximeYon/Bruker_EPI_Reco](https://github.com/maximeYon/Bruker_EPI_Reco) | public (see repo) | Bruker EPI reconstruction (double-sampling); may include sample raw data. |
| DWwave diffusion | PV6.0.1 | [osf.io/t9vqn](https://osf.io/t9vqn) | public (see project) | Arbitrary-waveform diffusion (EPI / spin-echo) sequence project. |
