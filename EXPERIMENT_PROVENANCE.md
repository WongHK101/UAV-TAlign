# Journal Experiment Provenance

This note records the accepted execution lineage without embedding machine
credentials or dataset contents in the repository.

## Official Input

- Dataset: `UAV-TAlign-12K`
- Candidate collection: 6,039 pairs / 12,078 images
- Official evaluation split: 6,037 pairs / 12,074 images
- Scenes: 15
- Canonical manifest SHA256:
  `a092f7ad00c6e02ead3bd39de5c246001f1d4bebbc4105ba715ef37bbb202c6c`

## Execution Snapshot

The June 2026 Windows main run records Git base commit
`c55e39e49cda508bae68520f718894bb0c761cec`. Compatibility output writers,
Windows launchers, semantic validation, and protocol-enrichment code present
on the execution host were subsequently frozen together in snapshot commit
`70f8160b09a5520397c105cfa75ed36245881ac3`.

The recovered execution-tree file hashes are:

| File | SHA256 |
|---|---|
| `run_prcv_main_experiment.py` | `f436e15f04656917408d0d71bb6fe267d75c01cea5bddc61a2cc3e8a842c28ec` |
| `scripts/build_ipt_p0d_protocol_artifacts.py` | `a4a6da4b83f8f174df69166d9c416cc6737198a83d394ce7f9de30f1e8c0b1d7` |
| `scripts/server_run_prcv_main_12k_windows.ps1` | `f2d62faf14d4f72eeb50ebf5a7911b6ef1b54c610e5431a65e176d72ba4ce990` |
| `scripts/server_run_prcv_protocol_artifacts_windows.ps1` | `feb4ce8b17f87c3ed2cbc627b676de8d4e03365c500158601920b1b157ced702` |
| `scripts/server_run_prcv_supplement_bundle_windows.ps1` | `8b31cb983ca8148bda9f1051d8c2274ad7fca86375dd7b30bdcfdb2126ca47f0` |

These hashes identify the recovered execution snapshot. Later safety and
documentation refinements receive new commits and must not be presented as the
historical run commit.

## Accepted Evidence Composition

- Main batch: SIFT, AKAZE, RoMa, XoFTR, raw MINIMA, and UAV-TAlign scene output.
- LoFTR: isolated resize-aware replacement (`max_dim=1200`, AMP enabled).
- RIFT2: independent Python 3.11 run using the declared resize-aware setting
  and USAC-MAGSAC with reprojection threshold 5.0.
- Protocol artifacts: generated read-only from the accepted UAV-TAlign scene
  records and fixed manifest.
- Ablation and multi-seed outputs: fixed eight-scene 1K-Lite supplement.

The original unbounded LoFTR attempt remains immutable historical evidence and
is not used for the paper-facing LoFTR row. The composite validator records the
replacement source explicitly; result files are not copied over the original
batch.
