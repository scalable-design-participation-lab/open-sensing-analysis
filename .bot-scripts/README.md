# .bot-scripts

Informal experiments. Nothing in here is part of the formal pipeline.

The formal pipeline is three notebooks in `notebooks/2026_09_16_site_built_environment_comparison/`:

| Notebook | Role |
|---|---|
| `svi_retrieval.ipynb` | image retrieval |
| `built_environment_features.ipynb` | feature calculation |
| `visual_features.ipynb` | tagged street visualization |

## cluster/

The Explorer run that recomputed the features with instance counts, 2026-09-17.
Run folder on the cluster: `/projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17/`

| File | Role |
|---|---|
| `features_core.py` | per-view and per-point feature functions. Kept identical to the notebook so a local re-run reproduces the cluster numbers |
| `paths.py` | cluster paths and the local prefix used to remap `view_paths` |
| `make_slices.py` | builds `slices.json`, 120 slices of 40 points |
| `run_slice.py` | one array task. Idempotent, writes `.tmp` then renames |
| `merge.py` | merges slices, validates point-index contiguity and lat/lon alignment per site |
| `build_env.sbatch` | bootstraps uv, standalone Python 3.12, torch 2.6.0 pinned to the laptop |
| `run_array.sbatch` | the 120-task array |
| `merge.sbatch` | merge as a batch job, never on the login node |
| `progress.sh` | read-only progress check |
| `stage_to_cluster.sh` | rsync imagery up, with retries |
| `stage_to_cluster_resume.sh` | resume loop, exits when all 9250 images are present |
| `verify_against_local.py` | computes reference points locally to check a cluster slice |

## exploration/

| File | Role |
|---|---|
| `_common.py` | shared loading. Canonical RMSE pairing follows `notebooks/2026_08_26_sensor_comparisons/comparison_with_all_sensors_pm25.ipynb` |
| `explore_humidity_and_error.py` | humidity against error, GVI against humidity, GVI against error |
| `explore_footprint_radius.py` | 100 m against 300 m footprint, Carter Field radar animations, continuity check |
| `wheel_sensors.py` | imageable wheel, one slice per sensor, nearest view as the image |

Figures land in `data/2026_09_16_site_built_environment_comparison/`, which is gitignored for `*.png`.
