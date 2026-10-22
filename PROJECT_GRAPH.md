# open-sensing-analysis — Project Graph

Sensor calibration and spatial interpolation (kriging) of environmental variables (temperature,
PM2.5, humidity) using satellite- and street-view-derived built-environment features, plus a
building-attribute/street-imagery pipeline that depends on an external sibling package. No paper
exists yet ("probably soon" per the user) — there are no `paper-section`/`paper-figure` nodes;
add them here when a manuscript starts, and expect this graph to be the fastest way to find out
which numbers are still trustworthy to cite.

**Before citing anything below, run `python scripts/graph_check.py`.** The user edits this repo
directly between sessions; a clean run is what makes the nodes below fact rather than a stale guess.
Run `python scripts/graph_view.py --open` to render this file as an interactive network diagram
(`project_graph.html`, gitignored-by-convention build output, not tracked as a node here).

## Read this first — known reproducibility issues (found while building this graph, 2026-08-23)

At least **8 notebooks/library files currently cannot be re-run top-to-bottom as saved.** All were
confirmed by reading actual source vs. actual stored cell outputs/execution_count sequences, not
inferred:

- **Broken relative imports (crashes on import), verified by actually importing the module:**
  `src/data_extraction/{census_population_density_extractor,nei_emissions_extractor,tiger_road_density_extractor,tree_canopy_extractor}.py`
  all do `from data_extract import ...` instead of `from .data_extract import ...` →
  `ModuleNotFoundError`. [nb/kriging-layers-extraction](#) imports 3 of these 4 — **that notebook's
  extractor cell cannot currently finish running**, which is almost certainly why its cached cell
  outputs still show pre-migration Google-Drive paths (see its node).
- Same bug, different file: `notebooks/kriging_street_view/{predictors_export,predictors_Export_2}.ipynb`
  both do `from utils import get_area_grid, get_square_dimensions` instead of
  `from src.kriging.utils import ...` → `ModuleNotFoundError`.
- **Missing intermediate files:** `data/kriging_street_view/bounding_box.geojson` and
  `.../grid_rectangles.geojson` (written by `predictors_export.ipynb`, read by both predictors
  notebooks) do not exist on disk and have no git history — `predictors_Export_2.ipynb` cannot be
  rerun from a clean checkout even if the import bug above were fixed.
- **Undefined names consistent with shared-kernel execution, not top-to-bottom runs:**
  `predictors_Export_2.ipynb` uses `box`, `StreetSampler`, and `data_points` without defining or
  importing any of them — strongly suggests it was run sharing a live kernel/namespace with
  `predictors_export.ipynb` rather than standalone.
- **Stale outputs from edited-after-run source** (cell source changed after the execution that
  produced the saved output, so the notebook now contradicts its own results):
  `01_Obtaining_Wind_Speed_And_Direction.ipynb` (GVI imports commented out after the run that
  produced cells 9-11 → `NameError` on rerun), `02_Comparison_With_Reference_Sensor.ipynb`
  (`figures_path` referenced but never assigned), `demo_sensor_data.ipynb` (cell 11 plots column
  `"n"`, which doesn't exist in the current schema → `KeyError` on rerun), and
  `K_Means.ipynb` (`predictor_cols_kmeans` needs `*_log1p` columns no visible cell creates).
- `03_Bland_Altman_And_Deming.ipynb` has **never been executed at all** (every cell
  `execution_count: None`, zero stored outputs).

None of this is a reason to distrust the *design* of the pipelines — the bugs are shallow (an
import path, an undefined variable) — but it means **none of these specific numbers should be
re-quoted without first re-running the notebook and confirming it still produces them.**

## Security & privacy — separate from reproducibility

- **Hardcoded Google Maps API key** (`""`) appears in 3
  untracked notebooks: `imagery_exploration.ipynb`, `imagery_exploration_2.ipynb`,
  `imagery_quality_assessment.ipynb`. Not in git history yet (files are untracked) — rotate the key
  and strip it before ever committing these.
- `data/monterrey_data/participants.json` holds **name + home neighborhood + lat/lon for 18
  people** (a human-subjects participant roster). It's already covered by `.gitignore`'s
  `data/**/*.json` rule, and this graph does not reproduce its contents. Treat as sensitive if this
  project becomes a paper — the values feed `nb/monterrey-kriging-2`'s per-participant maps.

## Structural note

The Monterrey pipeline (`notebooks/monterrey_temp_hum/`) keeps its **own parallel data tree**
inside `notebooks/` (`data/{raw,processed}/`, `monterrey_data/`, `images_maps_monterrey/`) instead
of using the top-level `data/` directory every other pipeline uses. Not a bug, but "where's the
data" has two different answers depending which pipeline you're reading.

---

## 1. Satellite kriging pipeline

Node(
  id:      nb/kriging-layers-extraction
  type:    notebook-pipeline
  file:    notebooks/kriging_layers/extraction.ipynb
  to:      [data/kriging-satellite-layers, data/kriging-satellite-nei, data/kriging-satellite-census]
  from:    [data/spatial, data/kriging-satellite-nlcd, data/kriging-satellite-nei, data/kriging-satellite-census, ext/epa-nei, ext/census-tiger, lib/data-extraction]
  purpose: Runs 6 extractors (NDVI, NDBI, NLCD impervious, TIGER road density, EPA NEI emissions, Census population density) over the Boston bbox/grid and saves each as a standalone GeoJSON layer under data/kriging_satellite/layers/.
  what_follows: Feeds both kriging_layers regression notebooks and, via the same layer files, both kriging_combined regression notebooks. Two "one-time" prep cells (24, 31) are manual/idempotent downloads that must succeed before their extractor cells (26, 33).
  nuances: CURRENTLY BROKEN — 3 of its imports (TIGERRoadDensityExtractor, NEIEmissionsExtractor, CensusPopulationDensityExtractor) hit the bad-relative-import bug in lib/data-extraction and raise ModuleNotFoundError; this cell cannot finish running as the repo stands (see top-of-file callout). Its cached cell outputs (cells 6,9,11,14,16,21,28,35) print paths under a Google-Drive "Interpolation_Std_Layers" folder that predates the repo's move out of Drive and the later data/ reorg (kriging_satellite subdir) — confirmed the current repo path is not a symlink into that Drive folder, so these are leftover pre-migration outputs, not current behavior. NEI extraction (cell 26) shows all-NaN emissions columns in .head() even before the import bug — worth checking once the import is fixed. TIGER_LOCAL_PATH=None (cell 18) means road density always fetches remotely rather than using a local cache like the other extractors. Trailing empty cell 36.
  evidence: purpose/outputs cells 1,4,6,9,11,14,16,19,21,24,26,28,31,33,35; inputs cells 3,13,18,24,26,31,33; Drive-staleness cells 3,6,9,14,16,21,28,35.
  status:  current
  last_modified: 2026-03-30
  checked: 2026-08-23 code_sha=1e1fd29d
)

Node(
  id:      nb/kriging-layers-regression-pm25
  type:    notebook-pipeline
  file:    notebooks/kriging_layers/kriging_regression_pm25.ipynb
  to:      [data/kriging-satellite-layers]
  from:    [data/kriging-satellite-layers, data/sensors, data/spatial, lib/kriging, lib/time-series]
  purpose: PM2.5 across the Boston grid via PCA (2 components) of 4 satellite-only layers (ndvi, ndbi, impervious, road_density_log1p) feeding a log-space ridge regression, then ordinary-kriges sensor residuals and adds them back for a final map.
  what_follows: Requires nb/kriging-layers-extraction's 4 layers to already exist; leaf pipeline, its own outputs aren't read by anything else reviewed.
  nuances: NEI emissions and population-density layers are explicitly commented out of both the required-layers dict (cell 2) and the PCA feature list (cell 5) — 2 of the 6 layers extraction.ipynb produces are deliberately unused here. Only 5 sensor points used (n_samples=5), ridge alpha=100, score_r2 very low (0.0548) — sat_pc1/sat_pc2 barely explain sensor PM2.5. Sensor-averaging window hardcoded 15:00-16:00 (cell 3). Ridge alpha (100) differs from the temperature sibling's alpha (1.0) with no documented rationale despite identical predictor structure — see kriging-satellite-layers node for the full set of alpha/NaN-handling inconsistencies across all 4 regression notebooks.
  evidence: inputs cells 2,3; model cell 5 (predictor_cols_pca, alpha=100, score_r2 0.0548); outputs cells 9 (PNGs), 10 (geojson); commented-out layers cells 2,4,5.
  status:  current
  last_modified: 2026-04-24
  checked: 2026-08-23 code_sha=29e11dda
)

Node(
  id:      nb/kriging-layers-regression-temperature
  type:    notebook-pipeline
  file:    notebooks/kriging_layers/kriging_regression_temperature.ipynb
  to:      [data/kriging-satellite-layers]
  from:    [data/kriging-satellite-layers, data/sensors, data/spatial, lib/kriging, lib/time-series]
  purpose: Temperature across the Boston grid via PCA (2 components) of the same 4 satellite-only layers feeding a LINEAR-space ridge regression (not log), then krige sensor residuals for a final map. Structurally near-identical sibling of the PM2.5 layers notebook.
  what_follows: Requires nb/kriging-layers-extraction's output first.
  nuances: Also checks for an optional tree_canopy_grid.geojson layer (cell 2); cached output shows "Loaded optional layers: []" and the file is confirmed absent from data/kriging_satellite/layers/ — extraction.ipynb never produces it, so this optional path is currently dead. Emissions/population-density commented out same as the PM2.5 sibling. Ridge alpha=1.0 (vs. 100 in the PM2.5 sibling) with score_r2=0.283 — regularization strength is inconsistent between the two "layers" notebooks with no documented rationale despite identical n_samples=5 and predictor structure. Trailing empty cell 11.
  evidence: optional tree_canopy check cell 2; model cell 5 (alpha=1.0, score_r2 0.283); outputs cell 9 (PNGs), cell 10 (geojson).
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=cc53c0b9
)

Node(
  id:      nb/kriging-combined-regression-pm25
  type:    notebook-pipeline
  file:    notebooks/kriging_combined/kriging_regression_pm25.ipynb
  to:      [data/kriging-combined]
  from:    [data/kriging-satellite-layers, data/kriging-street-view, data/sensors, data/spatial, lib/kriging, lib/time-series]
  purpose: PM2.5 via a joint PCA over a mixed satellite + street-view feature subset (ndvi, ndbi, road_density_log1p, gvi, cars_log1p) feeding a log-space ridge regression, then krige sensor residuals; saves under data/kriging_combined/.
  what_follows: Depends on nb/kriging-layers-extraction (satellite layers) AND the street-view predictor-export pair (data/kriging-street-view) — a 4-notebook fan-in.
  nuances: Markdown header claims "Joint PCA across all satellite and street-view predictors," but cell 5's predictor_cols_pca uses only 5 of 9 loaded columns — impervious, facades, sky_ratio, road_ratio are loaded into grid_features (cell 4) but never entered into the model, contradicting the "all" claim. Cell 4 shows 43/900 grid cells with NaN street-view features and explicitly zero-fills missing road_density (`.fillna(0.0)`) before that NaN-count print — contrast with the temperature-combined sibling, which median-fills the same gap instead (see cross-cutting note below). n_samples=5, alpha=10, score_r2=0.355 (the highest of the 4 regression notebooks).
  evidence: inputs cell 2 (sat_layer_paths, sv_layer_paths); feature build + zero-fill cell 4; PCA subset actually used cell 5; outputs cell 9 (OUT_DIR=DATA_DIR/'kriging_combined').
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=83cacb96
)

Node(
  id:      nb/kriging-combined-regression-temperature
  type:    notebook-pipeline
  file:    notebooks/kriging_combined/kriging_regression_temperature.ipynb
  to:      [data/kriging-combined]
  from:    [data/kriging-satellite-layers, data/kriging-street-view, data/sensors, data/spatial, lib/kriging, lib/time-series]
  purpose: Temperature via the same joint-PCA mixed sat+street-view feature subset feeding a LINEAR-space ridge regression, then krige sensor residuals; saves under data/kriging_combined/.
  what_follows: Same upstream dependencies as the PM2.5 combined notebook.
  nuances: Same "all predictors" markdown/code mismatch as the PM2.5 sibling (cell 5 uses only 5/9 loaded columns). GENUINE METHODOLOGICAL INCONSISTENCY vs. the PM2.5-combined sibling: this notebook's cell 4 shows road_density NaN count = 136/900 with NO fillna(0.0) anywhere in the file — instead those 136 NaNs are caught by a generic per-column MEDIAN-fill loop in cell 5. So missing road density = "no road" (0) in the PM2.5-combined version but = median road density in the temperature-combined version, between two notebooks whose markdown claims to be doing the same thing. Ridge alpha=1 (vs. 10 in the PM2.5-combined sibling), score_r2=0.308; combined_pc2's coefficient (0.710) is far larger in magnitude than the PM2.5 model's (-0.050) — the second PC matters much more for temperature. Two trailing empty cells (10, 11).
  evidence: NaN count without fill cell 4 ("road_density 136" vs. pm25-combined's "road_density 0"); median-fill catch-all cell 5; PCA subset cell 5; outputs cell 9.
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=9a56b2b6
)

Node(
  id:      nb/kriging-cluster-separation-experiment
  type:    notebook-pipeline
  file:    notebooks/kriging_cluster_separation_experiment/kriging_cluster_separation_experiment.ipynb
  to:      []
  from:    [data/kriging-satellite-layers, data/kriging-street-view, data/sensors, data/spatial, lib/kriging, lib/time-series, lib/tools]
  purpose: Tests whether adding a K-Means cluster label (fit on PCA of combined sat+street-view features) as a ridge-regression predictor improves temperature prediction vs. a no-cluster baseline (R2 0.583 vs 0.458, RMSE 1.446 vs 1.649). Matches commit 5fd54787.
  what_follows: NOTHING PERSISTED — a comment cell (22) reads "### export labelled_lattice_cluster.geojson" but no code anywhere in the notebook calls to_file/savefig; every result is plt.show() only. A completed, self-contained investigation, not a pipeline stage anything else depends on.
  nuances: Cell 1 hardcodes sys.path.append + PROJECT_ROOT as a literal machine-specific absolute path (unlike the other 5 kriging notebooks' dynamic find_project_root()), so its imports are bare module paths (`from kriging.ridge_regression import ...`, `from tools.kmeans import apply_kmeans`) rather than the `src.X.Y` convention used elsewhere. Cell 2 reads sensor locations from data/spatial/data-1775857265051.csv (a different file than sensor_locations.json, used nowhere else in this notebook set) with a manual sensor_name_map; the resulting inner-merge drops Boston World Series Way to 4 rows and is never used again — dead code, since cell 9 separately re-reads sensor_locations.json to recover all 5 sensors for the real spatial join. Cell 4's comment ("The intern's notebook referenced these log columns but did not create them in a clean run") is an explicit workaround for a bug in nb/k-means-root. Non-standard cell ids (e.g. 'prepare-kmeans-features', 'compare-cases') mixed with nbformat's random-hex ids suggest AI-assisted editing concentrated around the comparison section. Final cell 22 is comment-only dead code; cell 23 is an empty markdown heading — notebook ends mid-intention.
  evidence: hardcoded paths/bare imports cell 1; dropped-sensor dead merge cell 2, recovery cell 9; intern-notebook workaround cell 4; comparison stats cells 11,16,19; no persisted output cells 14,17,20,21 (plt.show only), 22 (comment-only, confirmed no to_file/savefig anywhere in file).
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=fc67b600
)

## 2. Street-view kriging pipeline

Node(
  id:      nb/kriging-street-view-predictors-export
  type:    notebook-pipeline
  file:    notebooks/kriging_street_view/predictors_export.ipynb
  to:      [data/kriging-street-view, data/kriging-street-view-network]
  from:    [data/spatial, data/kriging-street-view, lib/kriging, ext/alivestreets-package, manual/street-view-image-collection]
  purpose: Builds the Boston street-view AOI scaffolding (bounding box, 30-cell grid, walkable street network, 1000-point sampler) and computes+exports ONLY the Green View Index (GVI) grid — not the other 4 street-view predictors.
  what_follows: bounding_box.geojson, grid_rectangles.geojson and network/network.geojson are read by predictors_Export_2.ipynb to continue on the same AOI. grid_aggregated_gvi.geojson is 1 of the 5 grids both kriging_regression_*.ipynb notebooks require.
  nuances: BROKEN IMPORT (cell 2): bare `from utils import get_area_grid, get_square_dimensions` — no `utils` module exists in this repo outside .venv; should be `from src.kriging.utils import ...` (used correctly one cell earlier for get_bounding_box). Raises ModuleNotFoundError on a clean run — the "Each cell is 63.5m..." stored output is stale from an environment where bare `utils` was importable. Cell 11's stored output (a segmentation-model load message + a 54-minute progress bar) does not match its own visible source (which only loads a .jsonl and prints its length) — the real GVI-computation cell was almost certainly deleted/edited after execution; cell 12 references `gvi_values`, which no visible cell defines. Cell 8's stored stdout contains a stale absolute Google-Drive path from a prior version of the code. **data/kriging_street_view/bounding_box.geojson and grid_rectangles.geojson — written by cell 3, read back by cells 4/17/18 in this same notebook, required by predictors_Export_2.ipynb — do not exist on disk and have no git history; re-running either predictors notebook from a clean checkout fails at these reads** (see top-of-file callout). facades_model.pt sits at notebooks/kriging_street_view/facades_model.pt (cwd-relative, not under data/) — almost certainly cached weights from predictors_Export_2.ipynb's download_model() call.
  evidence: cell 0 (scope), cell 1 (correct src.kriging.utils import), cell 2 (bare utils import), cell 3 (export_bounding_box/export_grid_geojson), cell 4 (bbox read back), cell 8 (get_graph_from_point, stale Drive stdout), cell 9 (StreetSampler, 6231 points), cell 10 (commented-out StreetViewNetworkCollector — manual step), cell 11 (mismatched stale output), cell 12 (orphaned gvi_values.append(None)×4), cells 14-15 (tag_streets, export tagged_streets_gvi.geojson), cells 17-20 (grid overlay, export grid_aggregated_gvi.geojson).
  status:  current
  last_modified: 2026-03-30
  checked: 2026-08-23 code_sha=a6f0a2b1
)

Node(
  id:      nb/kriging-street-view-predictors-export-2
  type:    notebook-pipeline
  file:    notebooks/kriging_street_view/predictors_Export_2.ipynb
  to:      [data/kriging-street-view]
  from:    [data/kriging-street-view, data/kriging-street-view-network, lib/kriging, ext/alivestreets-package]
  purpose: Continues predictors_export.ipynb on the identical Boston AOI — runs a FacadeFeatureExtractor segmentation model over the collected sidewalk images to derive n_cars/sky_ratio/road_ratio/facade_area per sampling point, tags the street network, exports the 4 corresponding grid-aggregated predictor GeoJSONs (the 4 predictors_export.ipynb does not produce).
  what_follows: Its 4 outputs are the other 4 of the 5 predictor grids both kriging_regression_*.ipynb notebooks require.
  nuances: NOT RUNNABLE STANDALONE AS SAVED — `box` (cell 1), `StreetSampler` (cell 6), and `data_points` (cell 8) are all used without being defined or imported anywhere in this file; cell 0's own stored bbox-dict output doesn't match its visible source either. Strongly suggests this notebook was actually run sharing a live kernel/namespace with predictors_export.ipynb rather than top-to-bottom on its own. Same bare `from utils import ...` bug as predictors_export.ipynb (cell 1). get_bounding_box is imported from src.kriging.utils (cell 0) but never called — dead import. Cell 10 has empty source but a stale "6231\n6228" stdout left over from deleted code (consistent with a 6231-sampled-vs-6228-processed discrepancy). The segmentation cell (cell 8) took ~1h52m for 6228 points, confidence_threshold=0.2 (vehicle/road/facade)/0.0 (sky), runs 4-way threaded, each thread lazily loading its own FacadeFeatureExtractor via threading.local. Depends on bounding_box.geojson/grid_rectangles.geojson, which are currently absent from disk (see predictors_export.ipynb node) — cannot be rerun from a clean checkout without regenerating them first.
  evidence: cell 0 (mismatched stale bbox output), cell 1 (bare import, undefined box), cell 2 (bounding_box.geojson read), cell 5 (network.geojson read), cell 6 (undefined StreetSampler), cell 7 (point_dictionaries.jsonl -> point_dicts, unused), cell 8 (FacadeFeatureExtractor, undefined data_points, 1:52:18 stdout), cell 9 (export tagged_streets_4_features.geojson), cell 12 (grid overlay, export ×4 grid_aggregated_*.geojson).
  status:  current
  last_modified: 2026-03-30
  checked: 2026-08-23 code_sha=815da8c0
)

Node(
  id:      nb/kriging-street-view-regression-pm25
  type:    notebook-pipeline
  file:    notebooks/kriging_street_view/kriging_regression_pm25.ipynb
  to:      [data/kriging-street-view]
  from:    [data/kriging-street-view, data/sensors, data/spatial, lib/kriging, lib/time-series]
  purpose: Regression-kriging of PM2.5 for the 5 Boston sensors — PCA-reduced street-view predictors feed a ridge trend, log-space sensor residuals are ordinary-kriged and added back, producing pm25_sv_kriging_grid.geojson.
  what_follows: Terminal artifact for this slice; not read back by any other reviewed notebook.
  nuances: Cell 2 raises FileNotFoundError naming "predictors_export.ipynb" if the grid_aggregated_*.geojson files are missing, but 4 of those 5 files are actually produced by predictors_Export_2.ipynb — the error message points at the wrong notebook to rerun. Ridge trained on only 5 points; reported score_r2 ~0.0001 (essentially no fit). data/spatial/grid_rectangles.geojson is used here only as a project-root sentinel, never loaded as data.
  evidence: cell 1 (PROJECT_ROOT), cell 2 (grid reads + misleading error text), cell 3 (sensor CSVs, align_sensor_series, sensor_locations.json), cell 5 (PCA + train_ridge alpha=100, log1p target, r2=0.00012), cell 9 (fit_variogram_model, ordinary_kriging_predict, to_file).
  status:  current
  last_modified: 2026-04-24
  checked: 2026-08-23 code_sha=e2b08c4e
)

Node(
  id:      nb/kriging-street-view-regression-temperature
  type:    notebook-pipeline
  file:    notebooks/kriging_street_view/kriging_regression_temperature.ipynb
  to:      [data/kriging-street-view]
  from:    [data/kriging-street-view, data/sensors, data/spatial, lib/kriging, lib/time-series]
  purpose: Same regression-kriging pipeline as the PM2.5 street-view notebook but for temperature — PCA street-view predictors, ridge trend (no log transform, alpha=5), percentile-clipped final grid.
  what_follows: Terminal artifact; not read back by any other reviewed notebook.
  nuances: Cell 10 creates LAYERS_DIR=data/kriging_satellite/layers via mkdir but never writes anything there — vestigial dead code, likely copy-pasted from a satellite-kriging notebook. Cell 11 contains stray plain text in a code cell ("x: [gvi, road_ratio, sky_ratio, facade_ara, n_cars] y: temperature", note the typo "facade_ara") whose stored output is a SyntaxError — dead, not executable. Ridge fit is much better than the PM2.5 sibling (r2~0.86 on the same n=5, so treat with caution). Same misleading FileNotFoundError-message issue pointing at predictors_export.ipynb (cell 2).
  evidence: cell 2 (grid reads + error text), cell 5 (PCA + train_ridge alpha=5, r2=0.862), cell 10 (dead LAYERS_DIR mkdir, ordinary_kriging_predict, percentile clip, to_file), cell 11 (SyntaxError text cell).
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=38e130d4
)

Node(
  id:      nb/kriging-street-view-test
  type:    exploratory
  file:    notebooks/kriging_street_view/kriging_test.ipynb
  to:      []
  from:    [data/sensors, data/spatial, lib/kriging, lib/time-series]
  purpose: Scratch test of the core ordinary-kriging machinery — aligns the 5 raw Boston sensor series, fits a variogram directly on the 5 sensors' raw values at one arbitrary timestamp (no predictors, no regression trend), krige-interpolates onto the general data/spatial/grid_rectangles.geojson grid.
  what_follows: None — writes no files (grep-confirmed no to_file/to_csv/savefig/dump anywhere); not a dependency of any other reviewed notebook. Reads data/spatial/grid_rectangles.geojson as actual data, unlike the regression notebooks where the same path is only a root sentinel.
  nuances: Cell 5 is entirely dead — fails on its own first line (`parent_path` undefined, NameError per stored traceback) before reaching its own pre-refactor bare imports (`from variogram_training import ...`); duplicates and is superseded by the working logic already in cell 4 (correct src.kriging.variogram_training import). Only a single, arbitrarily-chosen timestamp (index=10 into a 39,886-row aligned series) is ever kriged.
  evidence: cell 2 (align_sensor_series, 39886 rows), cell 4 (sensor_locations.json, EPSG:26986, index=10, fit_variogram_model on raw values), cell 5 (dead, NameError), cell 6 (grid_rectangles.geojson read, ordinary_kriging_predict).
  status:  current
  last_modified: 2026-04-24
  checked: 2026-08-23 code_sha=f7baa01f
)

## 3. Sensor calibration & time series

Node(
  id:      nb/time-series-wind-speed-direction
  type:    notebook-pipeline
  file:    notebooks/time_series/01_Obtaining_Wind_Speed_And_Direction.ipynb
  to:      [data/kriging-street-view-built-environment]
  from:    [data/spatial, data/sensors, ext/open-meteo, lib/wind-data, lib/visualization, data/kriging-street-view-built-environment, ext/alivestreets-package, manual/street-view-image-collection]
  purpose: Builds hourly PM2.5 + wind pollution-rose comparisons (src.visualization.bivariate_plot) between Oakland Farm Station and "Monterrey 2", then separately computes street-view greenness (GVI) for both sites via the external alivestreets library.
  what_follows: Writes into data/kriging_street_view/built_environment/{oakland_farm_station,monterrey_2}/Images/ — the closest thing to a confirmed producer found for that directory (see its node) — though as saved this half of the notebook cannot currently run (see nuances).
  nuances: Only ever touches "Monterrey 2" (data/sensors/monterrey_2/) — never data/sensors/monterrey/. Cell 8's alivestreets imports are commented out with a "uncomment the code below" note, yet cells 9-12 call those classes directly; cell 8's execution_count is None while 9/10/11 show 15/16/24 — the saved outputs are stale from a run before the imports were commented out, so a fresh run raises NameError at cell 9. Cell 9 hardcodes `api_key = "YOUR_API_KEY"`. No tabular outputs anywhere, only images and inline plots.
  evidence: cell 0 (sensor_locations.json), cell 3 (monterrey_2 CSV path), cell 5 (get_wind_data + Open-Meteo URL, confirmed against src/wind_data/wind_data_retrieval.py), cell 8 (commented imports, exec=None), cells 9-10 (exec=15/16, image outputs), cell 11 (point_dictionaries.jsonl reads).
  status:  current
  last_modified: 2026-03-30
  checked: 2026-08-23 code_sha=d3a845df
)

Node(
  id:      nb/time-series-reference-sensor-comparison
  type:    notebook-pipeline
  file:    notebooks/time_series/02_Comparison_With_Reference_Sensor.ipynb
  to:      []
  from:    [data/sensors, lib/time-series]
  purpose: Compares the lab's Boston Carter Field sensor against its co-located MOD-00157 reference for PM2.5, temperature and relative humidity using src.time_series.time_series_sampler.resample_and_align and time_series_comparison_metrics.
  what_follows: Intended to write 2 PNGs but currently cannot (see nuances) — no output edge recorded since the code as saved never successfully reaches plt.savefig.
  nuances: NOT RUNNABLE AS SAVED — `figures_path`, used in `plt.savefig(figures_path/...)` at cells 4 and 7, is never assigned anywhere (only project_root/SENSORS_DIR are defined, cell 1). Cell 1 has execution_count=None while cells 2,4,5,7,8 show sequential counts 2-6 — cell 1's source was edited after the run that produced the current outputs, i.e. whatever previously defined figures_path was removed.
  evidence: cell 1 (exec=None, defines project_root/SENSORS_DIR only), cells 4 & 7 (figures_path referenced, undefined), execution_count sequence 1=None,2=2,4=3,5=4,7=5,8=6.
  status:  current
  last_modified: 2026-03-30
  checked: 2026-08-23 code_sha=a60401c5
)

Node(
  id:      nb/time-series-bland-altman-deming
  type:    notebook-pipeline
  file:    notebooks/time_series/03_Bland_Altman_And_Deming.ipynb
  to:      [data/docs-reports]
  from:    [data/sensors, lib/visualization, lib/time-series]
  purpose: Bland-Altman agreement plots (src.visualization.bland_altmant_plot.plot_bland_altman) and Deming regression (src.time_series.time_series_comparison_metrics.compute_deming_regression) between the same Boston Carter Field sensor/reference pair, for temperature, PM2.5 and humidity.
  what_follows: Would populate data/docs_reports/ with 6 new PNGs alongside the two pre-existing sensor_comparison_*.pdf reports (same directory, otherwise unrelated) — if run.
  nuances: Unlike notebook 02, FIGURES_DIR is correctly defined here (project_root/"data"/"docs_reports", cell 2, with mkdir). However every single cell has execution_count=None and there is not one stored output in the whole file — this notebook has never been run, and none of its 6 target PNGs exist on disk yet.
  evidence: cell 2 (FIGURES_DIR + mkdir); cells 4,5,7,8,10,11 (savefig paths); full-notebook scan confirming zero outputs, all execution_count=None.
  status:  current
  last_modified: 2026-03-30
  checked: 2026-08-23 code_sha=47f4fc6c
)

## 4. Monterrey pipeline

Node(
  id:      nb/monterrey-layers
  type:    notebook-pipeline
  file:    notebooks/monterrey_temp_hum/monterrey_layers.ipynb
  to:      [data/monterrey-grid-layers]
  from:    [ext/google-earth-engine, lib/data-extraction]
  purpose: Builds a ~500m grid over the Monterrey metro area (bbox -100.55,25.45,-100.05,25.90) and populates it with ~28 satellite/meteorology/terrain/land-cover layers pulled from Google Earth Engine via src.data_extraction extractors (MODIS LST/vegetation/albedo/AOD, Sentinel-2 NDVI/NDBI/MNDWI, WorldCover impervious, SRTM terrain, Dynamic World, GHSL, ERA5-Land, CFSV2, VIIRS nighttime lights).
  what_follows: TRUE upstream/preprocessing step. Must run before both nb/monterrey-kriging (needs grid_lst_celsius.geojson) and nb/monterrey-kriging-2 (needs nearly every layer it writes). Requires a live, authenticated Earth Engine session scoped to GCP project "new-project-484416" — fails without access to that specific project.
  nuances: Uses the project's proper `from src.data_extraction.X import Y` package-style imports (cell 0) — unlike either Monterrey kriging notebook, which use bare imports (see their nodes). Never reads any local sensor CSV — purely a satellite/EE layer builder. Cells 10, 14, 25, 33 are empty placeholders.
  evidence: cell 0 (imports + project-root logic keyed on src/data_extraction/landsat_extractor.py); cell 1 (grid build, grid_rectangles.geojson); cell 2 (ee.Initialize project id, first extractor); cells 15/17/22/24/28/31 (multi-file extractor loops).
  status:  current
  last_modified: 2026-06-25
  checked: 2026-08-23 code_sha=871d86e1
)

Node(
  id:      nb/monterrey-kriging
  type:    notebook-pipeline
  file:    notebooks/monterrey_temp_hum/kriging_monterrey.ipynb
  to:      [data/monterrey-processed]
  from:    [data/monterrey-citizen-sensor-raw, data/monterrey-grid-layers, lib/kriging, lib/time-series, lib/visualization]
  purpose: Aggregates a 63-sensor Monterrey citizen-science air-quality/temperature network into morning/afternoon/night series, then does single-covariate (MODIS/Landsat LST) ridge-regression + ordinary-kriging correction of TEMPERATURE ONLY.
  what_follows: Needs notebooks/monterrey_temp_hum/monterrey_data/grid_lst_celsius.geojson from nb/monterrey-layers first. Its 2 outputs feed nb/monterrey-demo-sensor-data's sensor-series sections and nb/monterrey-data-mod's cleanup cells.
  nuances: Title cell is just "### A" — uninformative. Never reads data/sensors/monterrey/ or monterrey_2/ despite living in the "monterrey_temp_hum" folder — it reads the 63-sensor citizen-science CSVs instead (see data/monterrey-citizen-sensor-raw). Imports via `sys.path.append("<hardcoded absolute path>/src/...")` plus bare `from variogram_training import ...` / `from ridge_regression import ...` (not the `src.kriging.X` package convention used in nb/monterrey-layers) — fragile and machine-specific. Cell 13 MONKEY-PATCHES vt.MODEL_FUNCS to drop the Gaussian variogram model, with an explicit inline comment: "gaussian variograms made the kriging matrix unstable for this Monterrey dataset" — a genuinely useful gotcha for reuse elsewhere.
  evidence: cell 1 (data paths), cell 7 (xlsx export), cell 8 (geojson dump), cell 10 (grid_lst_celsius.geojson read), cell 13 (MODEL_FUNCS patch + comment), cell 15 (geojson export).
  status:  current
  last_modified: 2026-06-25
  checked: 2026-08-23 code_sha=3ba4a001
)

Node(
  id:      nb/monterrey-kriging-2
  type:    notebook-pipeline
  file:    notebooks/monterrey_temp_hum/kriging_monterrey_2.ipynb
  to:      [data/monterrey-processed]
  from:    [data/monterrey-citizen-sensor-raw, data/monterrey-grid-layers, data/monterrey-participants, lib/kriging, lib/time-series]
  purpose: A SECOND, more elaborate kriging pass over the same 63-sensor network — per-day XGBoost regression against ~28 satellite/meteorology/terrain predictors plus k-NN local residual correction — for temperature, humidity and PM2.5, mapped onto both the grid and named student participants. The "_2" names a more elaborate KRIGING METHOD, not the data/sensors/monterrey_2/ sensor folder (verified — this notebook never reads that folder either).
  what_follows: Needs essentially all ~28 grid_*.geojson layers from nb/monterrey-layers and the separately-maintained data/monterrey_data/participants.json roster. Its participant xlsx/geojson feed nb/monterrey-demo-sensor-data's student-map section; its combined maps geojson feeds nb/monterrey-data-mod.
  nuances: Same non-package sys.path + bare-import style as nb/monterrey-kriging. Uses "monterrey_data" to mean TWO DIFFERENT DIRECTORIES — notebooks/monterrey_temp_hum/monterrey_data/ (grid layers, cell 2) vs. data/monterrey_data/ (participants.json, cell 9) — easy to conflate, a real naming collision in the repo. Cells 8/10 write intermediate files that cell 11 then deletes via path.unlink(); that same cleanup list also names humidity/PM2.5 variants this notebook's visible code never writes — leftover defensive cleanup from an earlier version. PARTICIPANTS_PATH (cell 9) is a hardcoded absolute path. The images_maps_monterrey output directory has an unexplained duplicate "images_maps_monterrey 2" folder and an images_maps_monterrey.zip next to it on disk, produced by neither this notebook nor any code found — manual backup copies (see data/monterrey-processed nuances).
  evidence: cell 1 (data paths), cell 2 (PREDICTOR_FILES + GRID_DIR), cell 9 (PARTICIPANTS_PATH), cells 8/10 (intermediate writes), cell 11 (exports + unlink loop), cell 12 (9 PNG saves).
  status:  current
  last_modified: 2026-06-26
  checked: 2026-08-23 code_sha=299d8f74
)

Node(
  id:      nb/monterrey-data-mod
  type:    notebook-pipeline
  file:    notebooks/monterrey_temp_hum/monterrey_data_mod.ipynb
  to:      [data/monterrey-processed]
  from:    [data/monterrey-processed]
  purpose: Post-processing/format-normalization — fixes date/timestamp string formats in place, converts grid polygons to point-centroid GeoJSONs, and exports parquet and lat/lon CSV variants of both Monterrey kriging notebooks' output products.
  what_follows: Pure downstream housekeeping — its point/parquet/csv variants aren't read by any other notebook in this set. **This directly contradicts the filename-order assumption: it is POST-processing DOWNSTREAM of both kriging notebooks, not a preprocessing step they depend on.** Must run after both nb/monterrey-kriging and nb/monterrey-kriging-2.
  nuances: Self-referential by design — reads and extends the same data/processed/ directory both kriging notebooks populate (324,000-row point conversions for the daily-maps product, 2,250-row for the temperature-only product). Uses relative paths (PROCESSED_DIR=Path(".")/"data"/"processed", cell 0) unlike most other monterrey_temp_hum notebooks, which hardcode absolute paths (though cells 14/15 do hardcode absolute paths for verification reads). data/processed/ on disk also contains manually created .zip archives and " 2"-suffixed duplicate files (e.g. monterrey_maps_daily_period_regressed_corrected_points.geojson.zip, "...points 2.csv.zip") that no cell here creates — filesystem-only manual artifacts, not notebook output.
  evidence: cell 0 (PROCESSED_DIR), cell 2 (geojson_paths + to_file), cell 4 (excel_paths), cell 6 (polygon->centroid, 324000/2250-row exports), cell 13 (to_parquet), cell 19 (to_csv).
  status:  current
  last_modified: 2026-06-26
  checked: 2026-08-23 code_sha=e7d42a04
)

Node(
  id:      nb/monterrey-demo-sensor-data
  type:    notebook-pipeline
  file:    notebooks/monterrey_temp_hum/demo_sensor_data.ipynb
  to:      []
  from:    [data/monterrey-processed]
  purpose: Exploratory/demo notebook plotting and mapping the processed Monterrey sensor-network ("Sensors series"/"Sensor spatial") and student-participant ("Student series"/"Students map") temperature data by time-of-day.
  what_follows: Depends on both nb/monterrey-kriging and nb/monterrey-kriging-2 having already run, and on nb/monterrey-data-mod if its date-format fix is wanted.
  nuances: All 4 input paths are hardcoded absolute paths to one machine — breaks elsewhere. Does not touch data/sensors/monterrey/ or monterrey_2/ at all despite living in the "monterrey_temp_hum" folder. No file outputs anywhere (plt.show()/inline display only). Cell 11 (`gdf.plot(column="n")`) has execution_count=None but a stored output that is actually a stale DataFrame text-repr, not a plot — the cell's source was edited after the run that produced that output, and "n" is not a column in the current schema (name/neighborhood/date/period/pm25/pm10/temperature/humidity/geometry per cells 8/12) — rerunning raises KeyError.
  evidence: cells 1,3,5,8 (hardcoded absolute paths); cell 11 (exec=None + mismatched stale output, verified via raw JSON).
  status:  current
  last_modified: 2026-06-26
  checked: 2026-08-23 code_sha=f376bdea
)

Node(
  id:      nb/monterrey-temp-humidity-limits
  type:    notebook-pipeline
  file:    notebooks/monterrey_temp_hum/monterrey_temp_humidity_limits.ipynb
  to:      []
  from:    [data/sensors]
  purpose: Loads the two raw single-sensor Monterrey deployments (data/sensors/monterrey/ and monterrey_2/) directly, filters to a shared time-of-day/date window, and compares their temperature/humidity distributions (histograms + 5th/95th percentiles) to sanity-check plausible value ranges.
  what_follows: Standalone diagnostic; percentile bounds are only printed, not saved or fed into any other notebook.
  nuances: **This is the ONLY one of the 9 time_series/monterrey_temp_hum notebooks that reads data/sensors/monterrey/ or monterrey_2/ at all** (grep-confirmed) — every other Monterrey notebook instead reads the 63-sensor citizen-science CSVs under notebooks/monterrey_temp_hum/data/raw/ (see data/monterrey-citizen-sensor-raw). Both paths hardcoded absolute. No src.* imports; no file outputs.
  evidence: cell 0 (both literal CSV paths, filter window 2025-05-01 to 2025-08-30, hours 9:00-22:00), cell 1 (percentile computation + histograms).
  status:  current
  last_modified: 2026-06-11
  checked: 2026-08-23 code_sha=5e522cd3
)

## 5. Imagery & building-attributes pipeline (external `imageable` dependency)

Node(
  id:      nb/imagery-exploration
  type:    notebook-pipeline
  file:    notebooks/2026_07_21_imagery_and_weather_station_data_exploration/imagery_exploration.ipynb
  to:      [data/imagery-weather-exploration]
  from:    [data/spatial, ext/google-street-view, ext/alivestreets-package]
  purpose: Builds a street network (OSMnX via the external `alivestreets` package) over a bounding box, samples points along it (1000 requested, 3167 actual), and checks Street View metadata coverage at those generic street-sample points (99.3%).
  what_follows: nb/imagery-exploration-2 reads this notebook's street_network.geojson to compute building-specific observation points.
  nuances: SECURITY — hardcoded live-looking Google Maps API key "" (cell 6), reused identically in nb/imagery-exploration-2 and nb/imagery-quality-assessment (see top-of-file callout). Coverage map (cell 9) is inline-only, no savefig. Last cell empty.
  evidence: cells 2,3,4,6,7,8 (street network build, sampling, coverage check, API key).
  status:  current
  last_modified: 2026-07-22
  checked: 2026-08-23 code_sha=25461308
)

Node(
  id:      nb/imagery-exploration-2
  type:    notebook-pipeline
  file:    notebooks/2026_07_21_imagery_and_weather_station_data_exploration/imagery_exploration_2.ipynb
  to:      [data/imagery-weather-exploration]
  from:    [data/spatial, data/imagery-weather-exploration, ext/boston-footprints-drive, ext/google-street-view, ext/imageable-package]
  purpose: Filters the full external Boston building-footprint dataset to the 2456 buildings fully inside the study area, estimates a street-facing observation point/heading per building via `imageable`'s ObservationPointEstimator, and checks per-building Street View coverage (99.96%).
  what_follows: Its boston_buildings_study_area.geojson output is manually copied (not by any code) into data/2026_08_03_imagery_quality_assessment/ and used by nb/imagery-quality-assessment and nb/building-attributes-extraction (same 2456-building count) — see manual/imagery-quality-study-area-copy.
  nuances: Cell 7 crashes at building 2429/2456 with `AttributeError: 'MultiPolygon' object has no attribute 'exterior'` (captured traceback in the saved notebook); cell 8 adds a MultiPolygon->Polygon fix and resumes from `start_index=len(results)` in the same kernel session — a captured crash-and-recover, not a clean single pass. None of the enriched per-building results (observation point, heading, distance, image availability) are ever written to disk — the notebook stops at an inline plot and a printed statistic. Same hardcoded Google Maps API key as nb/imagery-exploration (cell 9).
  evidence: cell "filter-footprints" (2456 buildings), cell 7 (crash), cell 8 (recovery), cell 9 (API key), cell 13 (printed stat); MD5 match confirmed between the two boston_buildings_study_area.geojson copies (3de8baa3a3d20382b1557f7e0960d29a).
  status:  current
  last_modified: 2026-07-22
  checked: 2026-08-23 code_sha=03290a73
)

Node(
  id:      nb/weather-data-exploration
  type:    exploratory
  file:    notebooks/2026_07_21_imagery_and_weather_station_data_exploration/weather_data_exploration.ipynb
  to:      []
  from:    []
  purpose: Indeterminate — the file is 0 bytes and contains no cells; despite the filename, no weather-related code exists anywhere in it.
  what_follows: -
  nuances: File is empty (0 bytes), fails JSON parsing entirely ("Expecting value: line 1 column 1"), untracked with no git history at all. Looks like a stub created but never saved with content, not a truncated former version.
  evidence: ls -la (0 bytes); json.load failure; git log/status (untracked, no history).
  status:  current
  last_modified: 2026-07-21
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      nb/imagery-quality-assessment
  type:    notebook-pipeline
  file:    notebooks/2026_08_03_imagery_quality_assessment/imagery_quality_assessment.ipynb
  to:      [data/imagery-quality-assessment]
  from:    [data/imagery-quality-assessment, manual/imagery-quality-study-area-copy, ext/google-street-view, ext/imageable-package]
  purpose: Downloads one Google Street View image plus capture metadata per building footprint in the study area (`imageable`'s camera-refinement image acquisition), populating data/2026_08_03_imagery_quality_assessment/images/building_{0..2455}/.
  what_follows: nb/imagery-quality-assessment-part-2 reads these images/metadata next to compute quality metrics. Explicitly framed in its own markdown as day 1 of a 2-day session ("Collecting imagery (today)... quality indicators (tomorrow)").
  nuances: Same hardcoded Google Maps API key as both imagery_exploration notebooks (cell 2). Reads its footprint/street-network files from data/2026_08_03_imagery_quality_assessment/, but no code anywhere writes those 2 files into that directory — see manual/imagery-quality-study-area-copy. Cells 4-6 are leftover interactive scratch (bare `?get_dataset`/`?get_image` IPython help lookups), not analysis logic. The download loop (cell 3) silently `continue`s past exceptions with no per-building failure logging — part 2 later finds 8 images missing; this notebook never reports that count.
  evidence: cell 0 (markdown framing), cell 2 (API key), cell 3 (download loop, silent continue), cells 4-6 (scratch cells).
  status:  current
  last_modified: 2026-08-03
  checked: 2026-08-23 code_sha=cad657a4
)

Node(
  id:      nb/imagery-quality-assessment-part-2
  type:    notebook-pipeline
  file:    notebooks/2026_08_03_imagery_quality_assessment/imagery_quality_assessment_part_2.ipynb
  to:      [data/imagery-quality-assessment]
  from:    [data/imagery-quality-assessment, ext/imageable-package]
  purpose: Computes per-image quality indicators (entropy, sharpness, sky/ground/facade ratios, camera-refinement success) for every downloaded image, exports quality_metrics.json, and plots each metric's distribution against thresholds from the Imageable paper's validation set.
  what_follows: Terminal analysis artifacts — nothing among these notebooks reads quality_metrics.json or the quality_plots/*.png back in. nb/building-attributes-extraction separately RECOMPUTES its own image attributes from the same images/ folder rather than reusing these numbers.
  nuances: Explicitly framed as day 2 ("Yesterday I collected the imagery, today I want to know if it is any good") and explicitly leaves LCNN/vanishing-point indicators as None "for now" — n_lines/scores/vanishing_points are never populated anywhere. The "Camera refinement outcome" bar chart (cell 16) has no savepath — inline only, confirmed absent from quality_plots/ (exactly 6 files on disk, matching the 6 plots that do pass a savepath). Same "mps"-hardcoded-device + absolute-IMAGEABLE_PATH pattern as nb/building-attributes-extraction. 8 of 2456 images are missing and get an all-None placeholder rather than exclusion, silently filtered downstream.
  evidence: cell 0 (day-2 framing), cell 3 (missing-image placeholder), cell 16 (unsaved plot), ls of quality_plots/ (exactly 6 files).
  status:  current
  last_modified: 2026-08-04
  checked: 2026-08-23 code_sha=67c6cc75
)

Node(
  id:      nb/building-attributes-extraction
  type:    notebook-pipeline
  file:    notebooks/2026_08_04_building_attributes/building_attributes_extraction.ipynb
  to:      [data/building-attributes]
  from:    [data/imagery-quality-assessment, ext/boston-footprints-sampling, ext/imageable-package]
  purpose: Runs the external `imageable` library over study-area building footprints and their Street View images to extract footprint/neighborhood/height/facade-material/image-quality attributes, saved as resumable per-50 batch parquet files then merged into one table.
  what_follows: nb/material-visualization-3d reads the merged building_attributes.parquet next. Rerunning is expected/safe — existing batch files are skipped (markdown cell 11).
  nuances: ALL_BOSTON_PATH hardcoded to an external path outside both this repo and the imageable sibling project (cell 4) — not reproducible elsewhere; see ext/boston-footprints-sampling. IMAGEABLE_PATH hardcoded absolute (cell 2); Segformer model hardcoded device="mps" (Apple-Silicon only, cell 8). Post-hoc validation finds only weak correlation (0.225) between estimated and city-reference building heights (cell 16). 8 attributes are entirely empty/zero this run (average_window/door_x/y, number_of_windows/doors, material_pct/area_water — cell 17). No src.* imports anywhere — entirely dependent on the external `imageable` package. BATCH PRODUCER CONFIRMED: cell 12, `batch_path = BATCHES_PATH/("batch_"+str(start)+"_"+str(end)+".parquet")`, BATCH_SIZE=50 over 2456 buildings — produces exactly the 50 files on disk.
  evidence: cells 2,4,8,12,16,17 (paths, device, batch pattern, validation, empty columns).
  status:  current
  last_modified: 2026-08-05
  checked: 2026-08-23 code_sha=52c566fe
)

Node(
  id:      nb/material-visualization-3d
  type:    notebook-pipeline
  file:    notebooks/2026_08_04_building_attributes/material_visualization_3d.ipynb
  to:      [data/building-attributes]
  from:    [data/building-attributes, data/imagery-quality-assessment, ext/imageable-package]
  purpose: Loads the merged building-attributes table and renders two interactive 3D maps (height-extruded, colored by dominant facade material; height-extruded) plus a static bar chart of dominant-material frequency.
  what_follows: Terminal visual deliverable; nothing downstream reads these back.
  nuances: Reads gpd.read_parquet(building_attributes.parquet) — the MERGED table, not the batches/ files and not anything from visualizations/ (cell 2). Reuses the variable name `ATTRIBUTES_PATH` for a directory here, whereas the extraction notebook uses the same name for a geojson FILE — same name, different meaning across the two notebooks. materials_3d.html is **276 MB on disk** (verified) — likely embeds all 2053 building thumbnails; the repo already has a "remove large files" cleanup commit (3aac0e20), so this untracked 276 MB file is a bloat risk if ever committed. No src.* imports — only imageable.visualization.*.
  evidence: cell 2 (read source), ls -la on visualizations/materials_3d.html (276 MB).
  status:  current
  last_modified: 2026-08-20
  checked: 2026-08-23 code_sha=fed149c2
)

## 6. Misc / exploratory notebooks & scripts

Node(
  id:      nb/layers-exploration
  type:    exploratory
  file:    notebooks/layers_exploration.ipynb
  to:      []
  from:    [data/labelled-lattice]
  purpose: Loads the already-assembled per-grid-cell "labelled lattice" table (36 columns, 900 rows — satellite indices, street-view aggregates, kriging-predicted temperature/PM2.5, emissions, density) and produces exploratory choropleths and column dumps to inspect it. Computes and saves nothing new.
  what_follows: -
  nuances: The only one of the 9 imagery/building/misc notebooks that is git-tracked and clean (already committed), unlike the other 8, which are untracked. None of the 36 inspected columns are computed here — labelled_lattice.geojson's actual producer is script/build-labelled-lattice.
  evidence: ls -la data/labelled_lattice.geojson (1.6 MB); git status comparison.
  status:  current
  last_modified: 2026-04-01
  checked: 2026-08-23 code_sha=494c5afc
)

Node(
  id:      nb/k-means-root
  type:    exploratory
  file:    K_Means.ipynb
  to:      []
  from:    [data/kriging-satellite-layers, data/kriging-street-view, data/sensors, data/spatial, lib/time-series]
  purpose: Builds a 900-cell feature grid from satellite/street-view layers, clusters it with scikit-learn KMeans (auto-selected K=2 by silhouette score) on 5 predictors, joins 4 PM2.5 sensor readings to grid cells, reports per-cluster mean PM2.5 as a naive cluster-based predictor.
  what_follows: -
  nuances: COLAB ORIGIN — sits at repo root (not notebooks/), untracked, 205,794 bytes; every data path is Colab-style `/content/data/...` (cell 0), which doesn't exist on this machine, yet saved outputs show real successful results — the individual filenames it expects all exist locally under this repo's own data/, just not under /content/data. Ran in Colab against an uploaded/mounted copy of this repo's data, then was saved back into the repo root unedited; will not run locally without changing DATA_DIR. Imports train_ridge/ridge_predict/fit_variogram_model/plot_variogram_fit/ordinary_kriging_predict from src.kriging but never calls any of them — dead imports; only align_sensor_series is actually used. **Confirmed does NOT import src.tools.kmeans.apply_kmeans (the repo's own k-means wrapper, same KMeans+silhouette_score pair) — instead reimplements the identical clustering+silhouette logic inline (cells 6-7), duplicating rather than reusing src/tools/kmeans.py.** `predictor_cols_kmeans` (cell 4) requires `*_log1p` columns that no visible cell creates — the feature-merge cell (cell 3) only creates plain road_density/cars — yet cells 6-7's saved outputs show the clustering succeeded; a transformation cell was likely deleted after the run that produced these outputs. As saved, rerunning top-to-bottom raises KeyError at cell 5. kmeans_clusters_pca.png (cell 11) saves to a bare relative filename outside any data/ convention and does not exist anywhere in the repo today. This notebook's bug is the explicit subject of a workaround comment in nb/kriging-cluster-separation-experiment's cell 4 ("the intern's notebook").
  evidence: cell 0 (Colab paths, dead kriging imports), cells 3-4 (missing log1p columns), cells 6-7 (inline KMeans reimplementation), cell 11 (orphaned output filename); Read of src/tools/kmeans.py confirming unused apply_kmeans() signature.
  status:  current
  last_modified: 2026-05-25
  checked: 2026-08-23 code_sha=eb22fa5f
)

Node(
  id:      script/main
  type:    script
  file:    main.py
  to:      []
  from:    []
  purpose: Default project-scaffold entry point — main() prints "Hello from open-sensing-analysis!" under if __name__=="__main__"; running python main.py does nothing else.
  what_follows: -
  nuances: Untouched scaffold stub (full 7-line content read directly), last touched in commit 007bf447 under an unrelated commit message — just carried along. Not wired to any notebook, src module, or data path anywhere in the project.
  evidence: full-file read (99 bytes); git log --oneline -- main.py -> single commit 007bf447.
  status:  current
  last_modified: 2026-04-24
  checked: 2026-08-23 code_sha=2c558b69
)

Node(
  id:      script/build-labelled-lattice
  type:    script
  file:    src/build_labelled_lattice.py
  to:      [data/labelled-lattice]
  from:    [data/spatial, data/kriging-satellite-layers, data/kriging-street-view, data/kriging-combined]
  purpose: Standalone build script that left-joins all extracted satellite/street-view predictor layers and kriging outputs onto the shared 900-cell grid lattice and writes the single consolidated data/labelled_lattice.geojson.
  what_follows: -
  nuances: Typed `script`, not `library-module` — has `if __name__=="__main__": build()` (lines 183-184), its docstring instructs running it directly from repo root, and grep across the whole repo (including inside .ipynb JSON) finds zero external references — nothing imports it. Defines its OWN local find_project_root() (lines 22-26); this is the file the now-corrected stale memory misattributed to src/__init__.py (which is actually a 0-byte empty stub — see lib/kriging's sibling nodes for the pattern of every notebook instead copy-pasting its own inline root-finder). Optional-layer handling is inconsistent: satellite layers (lines 55-76, 90-109) are joined unconditionally and raise if missing; street-view and combined-kriging outputs (lines 112-171) are guarded with .exists() checks that fill NaN and warn instead of failing. Docstring promises 2 output files (also data/labelled_lattice_metadata.json) but the code writes only labelled_lattice.geojson — the metadata JSON is out-of-band/static per an inline comment, not a bug, but a doc/code mismatch worth knowing about.
  evidence: lines 1-12 (docstring), 22-26 (find_project_root), 29-34 (path constants), 37-47 (_join helper), 50-180 (build()), 183-184 (__main__ guard).
  status:  current
  last_modified: 2026-04-24
  checked: 2026-08-23 code_sha=4d842e33
)

## 7. Library modules (src/)

Node(
  id:      lib/kriging
  type:    library-module
  file:    src/kriging/*.py
  to:      []
  from:    []
  purpose: Custom (non-sklearn) ridge regression, variogram fitting, and ordinary-kriging prediction, plus bounding-box/grid geometry helpers for building GeoJSON prediction grids.
  what_follows: -
  nuances: __init__.py is empty (0 bytes) — no re-exports; every caller must import the submodule directly, and none do so consistently (see the "duplicated find_project_root" pattern under script/build-labelled-lattice, and the bare vs. package-style import split across kriging_monterrey*.ipynb vs. monterrey_layers.ipynb). train_ridge is a from-scratch closed-form ridge solver (mean-centering + normal equations), NOT sklearn.linear_model.Ridge. variogram_training.py has a duplicated `import numpy as np` (lines 6 and 164) and a commented-out MODEL_FUNCS override left in place (line 35). ordinary_kriging_predict (line 166) annotates a parameter with `List[...]` but only `Callable` is imported from typing — safe only because `from __future__ import annotations` makes annotations lazy strings; would NameError under runtime type introspection. utils.py's export_bounding_box/export_grid_geojson take a caller-supplied output_path, no hardcoded default.
  evidence: ridge_regression.py:50-121 train_ridge(X,y,alpha=1.0,fit_intercept=True); :124-161 ridge_predict. variogram_training.py:39-134 fit_variogram_model (brute-force grid search over spherical/exponential/gaussian, MODEL_FUNCS lines 9-33); :137-160 plot_variogram_fit; :165-205 ordinary_kriging_predict. utils.py:6-44 get_bounding_box; :49-77 get_area_grid; :93-143 export_bounding_box; :146-177 export_grid_geojson.
  status:  current
  last_modified: 2026-06-25
  checked: 2026-08-23 code_sha=19902102,41c8af5e,46c31b13,d41d8cd9
)

Node(
  id:      lib/time-series
  type:    library-module
  file:    src/time_series/*.py
  to:      []
  from:    []
  purpose: Two independent time-series alignment strategies (multi-sensor common-timestamp alignment vs. two-series cross-correlation lag alignment) plus comparison metrics (RMSE/MAE/bias/correlation/linear fit/Deming regression).
  what_follows: -
  nuances: __init__.py empty. series_aligner.py and time_series_sampler.py look redundant by name but are not: align_sensor_series explicitly does NOT lag-shift (2+ sensors, matches on common/nearest timestamps), while resample_and_align DOES lag-shift via np.correlate cross-correlation between exactly 2 series — a reader relying on filenames alone would not guess which module does lag alignment. time_series_comparison_metrics.py mixes concerns: compute_linear_fit and compute_deming_regression have inline matplotlib plotting, while RMSE/MAE/bias/correlation are plot-free. compute_deming_regression is type-hinted `-> None` (line 142) but always returns a (beta_0, beta_1) tuple — wrong annotation.
  evidence: series_aligner.py:26-120 align_sensor_series(sensor_dataframes, variable_name, time_column, sampling_interval="1min", min_sensors=None, timestamp_tolerance=None); requires >=2 sensors (48-49). time_series_sampler.py:4-46 resample_and_align(ts1, ts2, ...) -> DataFrame with lag_steps/lag_timedelta columns; best lag via np.correlate(mode="full") on demeaned series (31-36). time_series_comparison_metrics.py:4-83 (rmse/correlation/mae/bias), :87-127 compute_linear_fit via np.linalg.lstsq, :131-168 compute_deming_regression (orthogonal regression closed form, line 152).
  status:  current
  last_modified: 2026-02-12
  checked: 2026-08-23 code_sha=0084a44a,b2e15782,d41d8cd9,f0bfe901
)

Node(
  id:      lib/visualization
  type:    library-module
  file:    src/visualization/*.py
  to:      []
  from:    []
  purpose: Matplotlib/seaborn plotting utilities — bivariate polar wind-rose plots, Bland-Altman agreement plots, generic distribution/bar plots (class-based), and multi-panel time-series plots (class-based).
  what_follows: -
  nuances: bland_altmant_plot.py's filename is confirmed a typo of "bland_altman" (the function itself is correctly named plot_bland_altman). __init__.py empty. plot_bland_altman's docstring is mixed-language: series1 documented in English, series2 in Spanish. It returns None and PRINTS an error (not raise) on length mismatch. distribution_plotter.py/time_series_plotter.py are classes with no real __init__ state besides a seaborn palette, while bivariate_plot.py/bland_altmant_plot.py are free functions — inconsistent style within the same subpackage. TimeSeriesPlotter.plot()'s default `colors` argument evaluates sns.color_palette("tab10") once at def time rather than per-call — a mutable-default-like smell, currently benign but fragile.
  evidence: bivariate_plot.py:52-136 bivariate_polar_plot_xy (config dataclass lines 16-30, polar pcolormesh). bland_altmant_plot.py:4-63 plot_bland_altman. distribution_plotter.py:6 class DistributionPlotter (5 plot methods, lines 8-409). time_series_plotter.py:9-91 class TimeSeriesPlotter.plot(arrangement="vertical"|other, max_plots_per_row=3, show_in_same_plot=False).
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=257c9df0,331cbef0,8d05c2d7,d41d8cd9,d64f20b5
)

Node(
  id:      lib/wind-data
  type:    library-module
  file:    src/wind_data/*.py
  to:      [ext/open-meteo]
  from:    []
  purpose: Fetches hourly historical wind speed/direction for a lat/lon and date range from the Open-Meteo archive API.
  what_follows: -
  nuances: __init__.py empty. Single function, no file I/O of its own — returns a DataFrame; persistence happens in the calling notebook. No retry/backoff logic; fixed 30s timeout plus requests.raise_for_status().
  evidence: wind_data_retrieval.py:1-41 get_wind_data(latitude, longitude, start_date, end_date); line 22 url="https://archive-api.open-meteo.com/v1/archive"; lines 23-30 hourly=wind_speed_10m,wind_direction_10m params.
  status:  current
  last_modified: 2026-01-05
  checked: 2026-08-23 code_sha=5cd047a8,d41d8cd9
)

Node(
  id:      lib/tools
  type:    library-module
  file:    src/tools/*.py
  to:      []
  from:    []
  purpose: Thin sklearn wrappers for K-means clustering (with silhouette score) and PCA dimensionality reduction.
  what_follows: -
  nuances: Both are thin sklearn wrappers (sklearn.cluster.KMeans + silhouette_score; sklearn.decomposition.PCA), not custom implementations. pca_transform_data returns only the transformed array, not the fitted PCA object — a caller can't retrieve explained_variance_ratio_ without modification. **Usage confirmed via repo-wide grep: the ONLY consumer is nb/kriging-cluster-separation-experiment** (`from tools.pca import pca_transform_data`, `from tools.kmeans import apply_kmeans`, via a hardcoded sys.path append rather than the `src.tools` package path). nb/k-means-root does NOT use this module despite the name match — see that node's nuances for the duplication this causes.
  evidence: kmeans.py:5-43 apply_kmeans(data, n_clusters=2, n_runs=10, random_state=42) -> (cluster_labels, centroids, score). pca.py:4-26 pca_transform_data(data, n_components=2, random_state=42) -> ndarray.
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=079b79e9,4371d105,d41d8cd9
)

Node(
  id:      lib/data-extraction
  type:    library-module
  file:    src/data_extraction/*.py
  to:      []
  from:    [ext/google-earth-engine, ext/planetary-computer-stac, ext/usgs-nlcd-s3, ext/census-tiger]
  purpose: DataExtractor (data_extract.py) is an ABC — get_data(bbox), align_to_grid(data, grid), orchestrated by extract_for_grid(). RasterExtractor (raster_extractor.py) is a second-level base implementing align_to_grid via rasterstats.zonal_stats for anything that can produce a local GeoTIFF. 13 of 20 extractor files are thin RasterExtractor subclasses pulling from Google Earth Engine; the rest bypass RasterExtractor for non-raster or non-GEE sources. Grid-aligned results are returned in memory — writing the final grid_*.geojson is done by the calling notebook, not this package.
  what_follows: All GEE-backed extractors assume the caller already ran ee.Initialize(...) — nothing here authenticates. data/raw/ (the implied GeoTIFF cache directory for 13 of the 20 extractors) does not exist anywhere in the repo — these extractors' raw caches are either cleaned up after use or have never completed a run in this environment.
  nuances: **VERIFIED BROKEN IMPORT (confirmed by actually importing the module, not just reading):** census_population_density_extractor.py:10, nei_emissions_extractor.py:13, tiger_road_density_extractor.py:10, and tree_canopy_extractor.py:12 all use `from data_extract import BBox, DataExtractor` (no leading dot) instead of the `from .data_extract import ...` every other file uses — raises ModuleNotFoundError. These 4 files are also the 4 oldest by mtime, consistent with predating a relative-import cleanup that missed them. nb/kriging-layers-extraction imports 3 of these 4 — see top-of-file callout. Layer-name collisions across independently-written extractors: "ndvi" is produced by three unrelated classes (MODIS MOD13Q1, Sentinel-2 via GEE, Sentinel-2 via Planetary Computer STAC); "ndbi" by two genuinely different satellites (Sentinel-2 GEE vs. Landsat/Planetary-Computer — confirmed these are NOT duplicates); "lst_celsius" by two (Landsat, MODIS); "impervious" by two (NLCD, WorldCover) — nothing in the base class enforces uniqueness if two were ever combined into one table. tree_canopy/census_population/nei_emissions extractors have no coded network fetch at all (local-file-only), unlike tiger_road_density, which does auto-fetch from Census TIGER with local fallback — "non-satellite sources mixed into this directory" is true but not uniform. DataExtractor.DEFAULT_GRID_PATH (data_extract.py:22) is the bare "data/grid_rectangles.geojson", stale relative to the current data/spatial/ layout; every actual caller passes grid_path explicitly instead. LandsatTemperatureExtractor and TreeCanopyExtractor are unused by any notebook found (grep-confirmed, including a false-positive check: a landsat_extractor string match in monterrey_layers.ipynb turned out to be only a root-finder path-existence check, not an import).
  evidence: data_extract.py:13-78 (ABC contract, extract_for_grid); raster_extractor.py:9-54 (value_columns pattern, zonal_stats). Full 20-extractor roster with per-file source/output/line citations verified in the construction session (GEE collections: MODIS/061/{MCD19A2_GRANULES,MCD43A3,MOD13Q1,MOD11A1,MYD11A1}, NOAA/CFSV2/FOR6H_HARMONIZED, GOOGLE/DYNAMICWORLD/V1, LANDSAT/{LC08,LC09}/C02/T1_L2, ECMWF/ERA5_LAND/HOURLY, JRC/GHSL/P2023A/GHS_BUILT_S, USGS/SRTMGL1_003, ESA/WorldCover/v200, COPERNICUS/S2_SR_HARMONIZED, NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG; Planetary Computer STAC collections landsat-c2-l2 and sentinel-2-l2a; direct S3/HTTP for USGS NLCD and Census TIGER).
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=0327a97d,173135d3,18099d69,1b4695d1,2559cecd,27763f31,2734ceb7,36442589,433054c9,6d731b6d,84d3db1b,8d96e94e,8dd3f144,9d9d8369,ad94bbed,bd5091ef,bdf6d84c,ce648867,d41d8cd9,d47582d6,d5ff9a8f,efe5a29c,fa50981c
)

## 8. Data artifacts

Node(
  id:      data/sensors
  type:    data-artifact
  file:    data/sensors/{boston_carter_field,boston_carter_field_reference,boston_gainsborough_parking,boston_robinson_hall,boston_west_village_b,boston_world_series_way,monterrey,monterrey_2,oakland_farm_station,oakland_library}/*.csv
  to:      [nb/kriging-layers-regression-pm25, nb/kriging-layers-regression-temperature, nb/kriging-combined-regression-pm25, nb/kriging-combined-regression-temperature, nb/kriging-cluster-separation-experiment, nb/kriging-street-view-regression-pm25, nb/kriging-street-view-regression-temperature, nb/kriging-street-view-test, nb/k-means-root, nb/time-series-wind-speed-direction, nb/time-series-reference-sensor-comparison, nb/time-series-bland-altman-deming, nb/monterrey-temp-humidity-limits]
  from:    []
  purpose: Raw per-deployment sensor CSVs — 5 Boston low-cost sensors + 1 co-located reference instrument (MOD-00157), 2 Monterrey single-sensor deployments, 2 Oakland deployments. The highest fan-out data node in the repo (13 direct consumers).
  what_follows: -
  nuances: No producer found in this repo for any of these files — raw hardware/vendor exports, presumably downloaded directly from sensor dashboards. Status unverified accordingly, not because the data is doubted, but because nothing here documents how these get from hardware to this folder.
  evidence: directory listing (10 subfolders, 1 CSV each); consumer list built from all 6 mapping passes across notebooks/.
  status:  unverified
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/spatial
  type:    data-artifact
  file:    data/spatial/{bounding_box.geojson,grid_rectangles.geojson,sensor_locations.json,data-1775857265051.csv}
  to:      [nb/kriging-layers-extraction, nb/kriging-layers-regression-pm25, nb/kriging-layers-regression-temperature, nb/kriging-combined-regression-pm25, nb/kriging-combined-regression-temperature, nb/kriging-cluster-separation-experiment, nb/kriging-street-view-regression-pm25, nb/kriging-street-view-regression-temperature, nb/kriging-street-view-test, nb/kriging-street-view-predictors-export, nb/k-means-root, nb/time-series-wind-speed-direction, nb/imagery-exploration, nb/imagery-exploration-2]
  from:    [manual/sensor-location-export]
  purpose: Shared spatial reference data used across nearly every pipeline — the project's bounding box, base prediction grid, and the 5 sensors' lat/lon.
  what_follows: -
  nuances: bounding_box.geojson, grid_rectangles.geojson and sensor_locations.json have NO confirmed producer anywhere in this repo — every notebook that touches them treats them as a pre-existing input (many only check grid_rectangles.geojson's *existence* as a project-root sentinel, never load its contents). Only data-1775857265051.csv has a plausible origin: its filename (a millisecond Unix timestamp) and its moduleid/ecohub_location/ecohub_id/lat/lon/timestamp schema strongly suggest an auto-named export from a sensor-siting dashboard (column names suggest a platform called "EcoHub") — see manual/sensor-location-export. No notebook was found that converts this CSV into sensor_locations.json, so even that link is inferred from content, not confirmed by code.
  evidence: 10-row CSV header "moduleid,ecohub_location,ecohub_id,lat,lon,timestamp" matching Boston sensor site names (Robinson Hall, West Village B, ...); repo-wide grep for writers of the other 3 files returned nothing across all 6 mapping passes.
  status:  unverified
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/labelled-lattice
  type:    data-artifact
  file:    data/labelled_lattice{,_wgs84}.geojson · data/labelled_lattice_metadata.json
  to:      [nb/layers-exploration]
  from:    [script/build-labelled-lattice]
  purpose: The single consolidated 900-cell table joining every extracted predictor layer plus kriging outputs — the project's closest thing to an analysis-ready dataset today.
  what_follows: -
  nuances: labelled_lattice_metadata.json is explicitly NOT produced by script/build-labelled-lattice (its docstring claims it, the code doesn't write it) — maintained by hand or some other untracked process; treat its contents as possibly stale relative to the geojson.
  evidence: see script/build-labelled-lattice.
  status:  current
  last_modified: 2026-04-24
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/kriging-satellite-layers
  type:    data-artifact
  file:    data/kriging_satellite/layers/*.geojson · data/kriging_satellite/layers/*.png
  to:      [nb/kriging-layers-regression-pm25, nb/kriging-layers-regression-temperature, nb/kriging-combined-regression-pm25, nb/kriging-combined-regression-temperature, nb/kriging-cluster-separation-experiment, nb/k-means-root, script/build-labelled-lattice]
  from:    [nb/kriging-layers-extraction, nb/kriging-layers-regression-pm25, nb/kriging-layers-regression-temperature]
  purpose: 8 satellite/administrative predictor-layer GeoJSONs (ndvi, ndbi, nlcd_impervious, road_density, nei_emissions, population_density, plus the 2 ridge-kriging output grids) and 4 before/after map PNGs, all sharing one directory.
  what_follows: -
  nuances: A `tree_canopy_grid.geojson` is checked for optionally by nb/kriging-layers-regression-temperature but is never produced by anything — confirmed absent, that code path is dead. Directory mixes true inputs (the 6 raw extractor layers) with outputs of the two "layers" regression notebooks (the ridge/kriging grids and maps) — same folder serves both roles.
  evidence: directory listing (12 files); see nb/kriging-layers-extraction and both kriging-layers-regression nodes.
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/kriging-satellite-census
  type:    data-artifact
  file:    data/kriging_satellite/census/*
  to:      [nb/kriging-layers-extraction]
  from:    [nb/kriging-layers-extraction, ext/census-tiger]
  purpose: Census TIGER block-group/tract boundary shapefiles (zipped) plus population geopackages and an ACS 2023 population CSV, used to build the population-density predictor layer.
  what_follows: -
  nuances: Currently unreachable end-to-end — CensusPopulationDensityExtractor is one of the 4 files with the broken-relative-import bug (see lib/data-extraction), so nb/kriging-layers-extraction's population-density cell cannot finish running as the repo stands.
  evidence: directory listing (5 files: 2 .gpkg, 1 .csv, 2 .zip).
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/kriging-satellite-nei
  type:    data-artifact
  file:    data/kriging_satellite/nei/*.zip
  to:      [nb/kriging-layers-extraction, manual/nei-zip-extraction]
  from:    [ext/epa-nei]
  purpose: Raw EPA National Emissions Inventory (2020) facility/process-by-region archive, the source for the NEI emissions predictor layer.
  what_follows: If the host's `unzip` binary is unavailable, nei_emissions_extractor.py raises and instructs the user to extract this zip manually first — see manual/nei-zip-extraction.
  nuances: Same broken-import bug as the census extractor blocks this pipeline currently — see lib/data-extraction.
  evidence: src/data_extraction/nei_emissions_extractor.py:347-350 (manual-extraction error message).
  status:  current
  last_modified: 2026-03-13
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/kriging-satellite-nlcd
  type:    data-artifact
  file:    data/kriging_satellite/nlcd/*.zip
  to:      [nb/kriging-layers-extraction]
  from:    [ext/usgs-nlcd-s3]
  purpose: Raw Annual NLCD Fractional Impervious Surface (2024) product, the local input extraction.ipynb reads for the NLCD impervious layer.
  what_follows: -
  nuances: Not confirmed whether this specific zip was manually pre-downloaded or produced by an earlier run of nlcd_impervious_extractor.py with local caching — genuinely unresolved, flagging rather than guessing.
  evidence: single file Annual_NLCD_FctImp_2024_CU_C1V1.zip; nlcd_impervious_extractor.py fetches the same USGS S3 product live per lib/data-extraction's roster.
  status:  unverified
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/kriging-satellite-network
  type:    data-artifact
  file:    data/kriging_satellite/network/network.geojson
  to:      []
  from:    []
  purpose: A road-network GeoJSON sitting in the satellite-kriging data tree.
  what_follows: -
  nuances: No confirmed producer OR consumer among any of the ~30 notebooks read for this graph — road_density_grid.geojson (under kriging_satellite/layers/, produced by TIGERRoadDensityExtractor) is what the regression notebooks actually use for road density. Distinct from, and not to be confused with, data/kriging_street_view/network/network.geojson (data/kriging-street-view-network), which DOES have a confirmed producer.
  evidence: directory listing; absence from every `from:`/`to:` list found across all 6 mapping passes.
  status:  unverified
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/kriging-street-view
  type:    data-artifact
  file:    data/kriging_street_view/{grid_aggregated_facade_area,grid_aggregated_gvi,grid_aggregated_n_cars,grid_aggregated_road_ratio,grid_aggregated_sky_ratio,pm25_sv_kriging_grid,tagged_streets_4_features,tagged_streets_gvi,temperature_sv_kriging_grid}.geojson · data/kriging_street_view/streetview_images/point_dictionaries.jsonl
  to:      [nb/kriging-street-view-regression-pm25, nb/kriging-street-view-regression-temperature, nb/kriging-combined-regression-pm25, nb/kriging-combined-regression-temperature, nb/kriging-cluster-separation-experiment, nb/k-means-root, script/build-labelled-lattice, nb/kriging-street-view-predictors-export-2]
  from:    [nb/kriging-street-view-predictors-export, nb/kriging-street-view-predictors-export-2, nb/kriging-street-view-regression-pm25, nb/kriging-street-view-regression-temperature]
  purpose: The 5 street-view predictor grids (gvi, facade_area, n_cars, sky_ratio, road_ratio), 2 tagged-street intermediate products, and the 2 street-view-only kriging outputs for the Boston AOI.
  what_follows: -
  nuances: **data/kriging_street_view/bounding_box.geojson and grid_rectangles.geojson — nominally part of this same directory per the code that writes and reads them (predictors_export.ipynb cell 3; read back by cells 4/17/18 and by predictors_Export_2.ipynb) — do NOT currently exist on disk and have no git history.** Deliberately excluded from the `file:` glob above (which only lists what's actually present) rather than listed as if they exist; see the top-of-file reproducibility callout. streetview_images/ holds hundreds of point_NNNN/ subdirectories of raw imagery (gitignored) alongside the one .jsonl this graph tracks as an input.
  evidence: directory listing (9 geojson files present); predictors_export.ipynb/predictors_Export_2.ipynb nodes for the missing-file finding.
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/kriging-street-view-network
  type:    data-artifact
  file:    data/kriging_street_view/network/network.geojson
  to:      [nb/kriging-street-view-predictors-export-2]
  from:    [nb/kriging-street-view-predictors-export]
  purpose: The walkable street network built for the Boston street-view AOI.
  what_follows: -
  nuances: Confirmed present on disk (unlike its sibling bounding_box.geojson/grid_rectangles.geojson in the same producing notebook) — this specific output survived even though the other two AOI-setup files from the same notebook cell did not.
  evidence: predictors_export.ipynb cell 8 (get_graph_from_point, export_graph_geojson); predictors_Export_2.ipynb cell 5 (read back).
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/kriging-street-view-built-environment
  type:    data-artifact
  file:    data/kriging_street_view/built_environment/{monterrey_2,oakland_farm_station}/street_network.geojson
  to:      [nb/time-series-wind-speed-direction]
  from:    [nb/time-series-wind-speed-direction]
  purpose: Per-city street network + raw Street View imagery (Images/, gitignored) for the Oakland Farm Station and "Monterrey 2" sites, used for a GVI comparison alongside their wind/PM2.5 data.
  what_follows: -
  nuances: Producer is only PARTIALLY resolved. nb/time-series-wind-speed-direction writes into this tree's Images/ subdirectories (cells 9-10) — but that half of the notebook is currently broken as saved (NameError, see that node), and street_network.geojson itself is only ever READ by that notebook, never written by it or by anything else found across all 6 mapping passes (predictors_export.ipynb/predictors_Export_2.ipynb, which build the analogous Boston-AOI network, explicitly do not touch this directory — grep-confirmed zero mentions of "monterrey"/"oakland"/"built_environment" in either file).
  evidence: notebooks/time_series/01_Obtaining_Wind_Speed_And_Direction.ipynb cells 9-11; absence confirmed via grep across kriging_street_view/predictors_export*.ipynb.
  status:  unverified
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/kriging-combined
  type:    data-artifact
  file:    data/kriging_combined/{pm25_combined_kriging_grid,temperature_combined_kriging_grid}.geojson · data/kriging_combined/{pm25_combined_map,temperature_combined_map}.png
  to:      [script/build-labelled-lattice]
  from:    [nb/kriging-combined-regression-pm25, nb/kriging-combined-regression-temperature]
  purpose: Final kriged PM2.5/temperature grids and maps from the joint satellite+street-view regression notebooks.
  what_follows: -
  nuances: See the two kriging-combined regression notebook nodes for the road_density NaN-handling inconsistency between the PM2.5 and temperature versions producing these files.
  evidence: directory listing (4 files).
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/monterrey-participants
  type:    data-artifact
  file:    data/monterrey_data/participants.json
  to:      [nb/monterrey-kriging-2]
  from:    []
  purpose: A roster of 18 named participants (name, neighborhood, latitude, longitude) used to map daily temperature/humidity/PM2.5 predictions onto specific individuals' locations in nb/monterrey-kriging-2.
  what_follows: -
  nuances: SENSITIVE — human-subjects data with home coordinates. No code in this repo produces this file; already covered by .gitignore's `data/**/*.json` rule. This graph deliberately does not reproduce its contents. If this project becomes a paper, this file's role needs explicit privacy review before any map derived from it is published.
  evidence: schema read directly (keys only, no values reproduced): list of 18 objects with keys name/neighborhood/longitude/latitude; consumer confirmed at kriging_monterrey_2.ipynb cell 9.
  status:  unverified
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/building-attributes
  type:    data-artifact
  file:    data/2026_08_04_building_attributes/*.geojson · data/2026_08_04_building_attributes/*.parquet · data/2026_08_04_building_attributes/batches/batch_{lo}_{hi}.parquet · data/2026_08_04_building_attributes/visualizations/*
  to:      [nb/material-visualization-3d]
  from:    [nb/building-attributes-extraction]
  purpose: Per-building attribute extraction results (footprint/height/material/quality) for 2456 Boston buildings — 50 resumable batch files, a merged parquet+geojson table, and 3 visualization deliverables (2 interactive 3D HTML maps, 1 static PNG).
  what_follows: -
  nuances: materials_3d.html is 276 MB — see nb/material-visualization-3d's bloat-risk nuance.
  evidence: directory listing (3 top-level files, 50 batch files, 3 visualization files).
  status:  current
  last_modified: 2026-08-20
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/imagery-weather-exploration
  type:    data-artifact
  file:    data/2026_07_21_imagery_and_weather_station_data_exploration/*
  to:      [nb/imagery-exploration-2]
  from:    [nb/imagery-exploration, nb/imagery-exploration-2]
  purpose: First-pass street network, filtered building-footprint study area, and metadata dictionaries from the July 21 imagery/weather exploration session.
  what_follows: Its boston_buildings_study_area.geojson and street_network.geojson are the source of a manual copy into data/2026_08_03_imagery_quality_assessment/ — see manual/imagery-quality-study-area-copy.
  nuances: -
  evidence: directory listing (3 files); MD5 match against the 2026_08_03_imagery_quality_assessment copies.
  status:  current
  last_modified: 2026-07-22
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/imagery-quality-assessment
  type:    data-artifact
  file:    data/2026_08_03_imagery_quality_assessment/*.geojson · data/2026_08_03_imagery_quality_assessment/quality_metrics.json · data/2026_08_03_imagery_quality_assessment/images/building_{i}/{image.jpg,metadata.json} · data/2026_08_03_imagery_quality_assessment/quality_plots/*.png
  to:      [nb/imagery-quality-assessment, nb/imagery-quality-assessment-part-2, nb/building-attributes-extraction, nb/material-visualization-3d]
  from:    [manual/imagery-quality-study-area-copy, nb/imagery-quality-assessment]
  purpose: The study-area definition, 2456×2 downloaded Street View images/metadata, computed quality metrics, and 6 quality-distribution plots for the August 3 imagery-quality assessment session. Reused as the building-footprint/image source for the entire building-attributes pipeline in section 5.
  what_follows: -
  nuances: boston_buildings_study_area.geojson and street_network.geojson here are MD5-identical to, but later-mtime than, the copies in data/imagery-weather-exploration — confirmed manually copied between directories, not produced by any notebook (see manual/imagery-quality-study-area-copy). 8 of 2456 building image/metadata pairs are missing.
  evidence: 2457 subdirectories under images/ (2456 buildings + the parent), directory listing of quality_plots/ (exactly 6 files).
  status:  current
  last_modified: 2026-08-04
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/docs-reports
  type:    data-artifact
  file:    data/docs_reports/*.pdf
  to:      []
  from:    [nb/time-series-bland-altman-deming]
  purpose: Two pre-existing sensor-comparison PDF reports (sensor_comparison_1.pdf, sensor_comparison_2_with_questions.pdf), plus the target directory for 6 Bland-Altman/Deming PNGs nb/time-series-bland-altman-deming would write if run.
  what_follows: -
  nuances: The 2 PDFs have no producer or consumer anywhere in this codebase — grep across all 3 time_series notebooks for "sensor_comparison" returns zero matches; they appear to be externally-authored reports someone placed here for reference, not pipeline output.
  evidence: directory listing (2 PDFs); grep confirmation across notebooks/time_series/*.ipynb.
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/monterrey-citizen-sensor-raw
  type:    data-artifact
  file:    notebooks/monterrey_temp_hum/data/raw/landsat/sensors_2026-06-24.csv · notebooks/monterrey_temp_hum/data/air_quality_readings_2026-06-24 1.csv · notebooks/monterrey_temp_hum/data/air_readings.csv
  to:      [nb/monterrey-kriging, nb/monterrey-kriging-2]
  from:    []
  purpose: Raw exports from a 63-sensor Monterrey citizen-science air-quality/temperature network — the actual input to both Monterrey kriging notebooks (neither of which reads data/sensors/monterrey/ or monterrey_2/, despite the folder name — see monterrey-kriging nodes).
  what_follows: -
  nuances: No collection/export script for this data exists in the repo — external or manual origin, consistent with a citizen-science network. `air_readings.csv` sits alongside the cited "air_quality_readings_2026-06-24 1.csv" input with no notebook found referencing it directly — possibly an older or alternate export; not confirmed either way.
  evidence: directory listing; grep confirmation that kriging_monterrey.ipynb and kriging_monterrey_2.ipynb both read the same 2 named files (cell 1 in each).
  status:  unverified
  last_modified: 2026-06-26
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/monterrey-grid-layers
  type:    data-artifact
  file:    notebooks/monterrey_temp_hum/monterrey_data/*.geojson · notebooks/monterrey_temp_hum/monterrey_data/raw/*
  to:      [nb/monterrey-kriging, nb/monterrey-kriging-2]
  from:    [nb/monterrey-layers]
  purpose: ~28 satellite/meteorology/terrain/land-cover predictor layers for the Monterrey grid, plus raw per-extractor intermediates, produced by nb/monterrey-layers.
  what_follows: -
  nuances: Lives inside notebooks/monterrey_temp_hum/ rather than the top-level data/ directory — part of the Monterrey pipeline's parallel data-storage convention (see top-of-file structural note). Name collision risk: nb/monterrey-kriging-2 also uses the string "monterrey_data" to refer to the unrelated data/monterrey_data/ directory (participants.json) — see that node's nuances.
  evidence: directory listing (37 top-level + 39 raw/ files, matching ~28 named layers plus per-extractor raw intermediates).
  status:  current
  last_modified: 2026-06-25
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      data/monterrey-processed
  type:    data-artifact
  file:    notebooks/monterrey_temp_hum/data/processed/* · notebooks/monterrey_temp_hum/images_maps_monterrey/* · notebooks/monterrey_temp_hum/images_maps_monterrey.zip · notebooks/monterrey_temp_hum/monterrey_morning_afternoon_night.geojson
  to:      [nb/monterrey-data-mod, nb/monterrey-demo-sensor-data]
  from:    [nb/monterrey-kriging, nb/monterrey-kriging-2, nb/monterrey-data-mod]
  purpose: All Monterrey kriging outputs and their post-processed point/parquet/csv variants — the sensor-series and student-participant products both kriging notebooks and monterrey_data_mod.ipynb read and write.
  what_follows: -
  nuances: Contains multiple manually created .zip archives and " 2"-suffixed duplicate files (e.g. monterrey_maps_daily_period_regressed_corrected_points.geojson.zip, "...points 2.csv.zip") that no notebook in this set creates — ad hoc human backups, not pipeline output. `notebooks/monterrey_temp_hum/da/` (0 files) also exists alongside this tree — looks like a stray/incomplete directory, possibly a typo for "data", not referenced by any code.
  evidence: directory listing (18 files in data/processed/, 9 in images_maps_monterrey/, a matching 9-file "images_maps_monterrey 2/" duplicate, plus the stray "da" directory).
  status:  current
  last_modified: 2026-06-26
  checked: 2026-08-23 code_sha=n/a
)

## 9. External sources

Node(
  id:      ext/google-earth-engine
  type:    external-source
  file:    URL:https://earthengine.google.com
  to:      [lib/data-extraction, nb/monterrey-layers]
  from:    []
  purpose: Source for 13 of lib/data-extraction's 20 extractors (MODIS ×5 products, Sentinel-2, Landsat, ERA5-Land, CFSV2, Dynamic World, GHSL, SRTM terrain, WorldCover, VIIRS) and for nb/monterrey-layers' ~28-layer Monterrey grid build.
  what_follows: -
  nuances: nb/monterrey-layers requires a live session scoped to GCP project "new-project-484416" specifically — will fail for anyone without access to that project.
  evidence: collection ids listed on lib/data-extraction's node.
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      ext/planetary-computer-stac
  type:    external-source
  file:    URL:https://planetarycomputer.microsoft.com/api/stac/v1
  to:      [lib/data-extraction]
  from:    []
  purpose: Microsoft Planetary Computer STAC API — source for ndbi_extractor.py (collection landsat-c2-l2) and ndvi_extractor.py (collection sentinel-2-l2a), the two extractors that bypass Earth Engine entirely.
  what_follows: -
  nuances: -
  evidence: src/data_extraction/{ndbi,ndvi}_extractor.py, lines 20-22 (collection ids).
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      ext/census-tiger
  type:    external-source
  file:    URL:https://www2.census.gov/geo/tiger · URL:https://api.census.gov/data/2023/acs/acs5
  to:      [lib/data-extraction, nb/kriging-layers-extraction]
  from:    []
  purpose: US Census TIGER/Line road and block-group/tract boundary shapefiles, plus the ACS5 population estimates API, used for road-density and population-density predictor layers.
  what_follows: -
  nuances: tiger_road_density_extractor.py auto-fetches live with local fallback; census_population_density_extractor.py is local-file-only (no coded fetch) despite living in the same "vector API" family. census_population_density_extractor.py also carries the broken-import bug — see lib/data-extraction.
  evidence: src/data_extraction/tiger_road_density_extractor.py:22,141-143; census_population_density_extractor.py:17-19 (docstring: ACS B01003_001E / Decennial P1_001N).
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      ext/epa-nei
  type:    external-source
  file:    URL:https://gaftp.epa.gov/air/nei/2020/data_summaries/2020nei_facility_process_byregions.zip
  to:      [lib/data-extraction, nb/kriging-layers-extraction, manual/nei-zip-extraction]
  from:    []
  purpose: EPA National Emissions Inventory (2020) facility/process data, the source for the NEI emissions predictor layer.
  what_follows: -
  nuances: nei_emissions_extractor.py is local-file-only (no coded fetch) and carries the broken-import bug — see lib/data-extraction. Its manual-unzip fallback is manual/nei-zip-extraction.
  evidence: nb/kriging-layers-extraction cell 24/26 (download + extractor cells).
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      ext/usgs-nlcd-s3
  type:    external-source
  file:    URL:https://usgs-landcover.s3.us-west-2.amazonaws.com
  to:      [lib/data-extraction]
  from:    []
  purpose: AWS S3-hosted USGS NLCD Fractional Impervious Surface product, fetched by nlcd_impervious_extractor.py.
  what_follows: -
  nuances: Relationship to the pre-downloaded data/kriging_satellite/nlcd/Annual_NLCD_FctImp_2024_CU_C1V1.zip is unresolved — see data/kriging-satellite-nlcd.
  evidence: src/data_extraction/nlcd_impervious_extractor.py:20-21,173-178 (product code "FctImp", windowed rasterio read).
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      ext/open-meteo
  type:    external-source
  file:    URL:https://archive-api.open-meteo.com/v1/archive
  to:      [lib/wind-data]
  from:    []
  purpose: Historical hourly wind speed/direction archive API, the sole external dependency of lib/wind-data.
  what_follows: -
  nuances: -
  evidence: src/wind_data/wind_data_retrieval.py:22.
  status:  current
  last_modified: 2026-01-05
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      ext/google-street-view
  type:    external-source
  file:    URL:https://maps.googleapis.com/maps/api/streetview
  to:      [nb/imagery-exploration, nb/imagery-exploration-2, nb/imagery-quality-assessment, nb/time-series-wind-speed-direction]
  from:    []
  purpose: Google Street View Static/Metadata APIs — image acquisition and coverage checks across the imagery-quality and building-attributes pipeline, plus the (currently broken) GVI section of nb/time-series-wind-speed-direction.
  what_follows: -
  nuances: SECURITY — a single live-looking API key is hardcoded identically in 3 of these 4 notebooks (see top-of-file callout); nb/time-series-wind-speed-direction instead hardcodes the placeholder "YOUR_API_KEY", consistent with that section never having successfully run.
  evidence: see the 4 consuming notebooks' nuances for exact cell citations.
  status:  current
  last_modified: 2026-08-04
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      ext/imageable-package
  type:    external-source
  file:    EXTERNAL:~/Documents/imageable-2026/imageable
  to:      [nb/building-attributes-extraction, nb/material-visualization-3d, nb/imagery-exploration-2, nb/imagery-quality-assessment, nb/imagery-quality-assessment-part-2]
  from:    []
  purpose: Sibling package (own repo, own uv venv, dist name urban_imageable — see [[imageable-sibling-project]] memory) providing building-footprint camera/observation-point estimation, Street View acquisition, Segformer-based facade-material segmentation, and 3D visualization — the whole of section 5 depends on it and has no src.* imports of its own.
  what_follows: -
  nuances: building_attributes_extraction.ipynb and imagery_quality_assessment_part_2.ipynb both reference specific asset/result files inside this sibling repo (ade20k_palette.json; framework-imageable/results/preparation_experiment_3.json) — a version mismatch between the two repos would silently change results in this pipeline with no error here.
  evidence: nb/building-attributes-extraction, nb/material-visualization-3d, nb/imagery-exploration-2, nb/imagery-quality-assessment, nb/imagery-quality-assessment-part-2 nodes (no src.* imports found in any of them).
  status:  current
  last_modified: 2026-08-20
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      ext/alivestreets-package
  type:    external-source
  file:    EXTERNAL:pip package "alivestreets", not vendored in src/
  to:      [nb/kriging-street-view-predictors-export, nb/kriging-street-view-predictors-export-2, nb/imagery-exploration, nb/time-series-wind-speed-direction]
  from:    []
  purpose: OSMnX-based street-network sampling and Street View collection package used across the street-view predictor pipeline and the wind/GVI comparison notebook.
  what_follows: -
  nuances: -
  evidence: see the 4 consuming notebooks' import cells.
  status:  current
  last_modified: 2026-08-19
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      ext/boston-footprints-sampling
  type:    external-source
  file:    EXTERNAL:~/Documents/sampling/boston_buildings.geojson
  to:      [nb/building-attributes-extraction]
  from:    []
  purpose: The primary Boston building-footprint source for the building-attributes pipeline (ALL_BOSTON_PATH).
  what_follows: -
  nuances: External to both this repo and the imageable sibling repo — not reproducible on another machine as saved. NOT confirmed to be the same dataset as ext/boston-footprints-drive (a different absolute path used by a different notebook) — do not assume they're identical without checking.
  evidence: notebooks/2026_08_04_building_attributes/building_attributes_extraction.ipynb cell 4.
  status:  current
  last_modified: 2026-08-05
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      ext/boston-footprints-drive
  type:    external-source
  file:    DRIVE:Shared drives/Cool and Carbon Free Africa/Building Image Datasets/data/boston/footprints/boston_buildings.geojson
  to:      [nb/imagery-exploration-2]
  from:    []
  purpose: The full external Boston building-footprint dataset nb/imagery-exploration-2 filters down to the 2456-building study area.
  what_follows: -
  nuances: A personal Google Drive shared-drive path — machine/account-specific, not reproducible elsewhere. Not confirmed to be the same dataset as ext/boston-footprints-sampling.
  evidence: notebooks/2026_07_21_imagery_and_weather_station_data_exploration/imagery_exploration_2.ipynb, cell "paths".
  status:  current
  last_modified: 2026-07-22
  checked: 2026-08-23 code_sha=n/a
)

## 10. Manual steps

Node(
  id:      manual/sensor-location-export
  type:    manual-step
  file:    n/a
  to:      [data/spatial]
  from:    []
  purpose: A human exports sensor site metadata (moduleid, site name, lat/lon, timestamp) from what its column names suggest is a platform called "EcoHub", producing the auto-named data/spatial/data-1775857265051.csv.
  what_follows: No code was found that turns this export into data/spatial/sensor_locations.json — if that link exists, it's another manual step not captured here.
  nuances: Inferred from the filename pattern (a millisecond Unix timestamp, typical of a dashboard "export" button) and column schema, not from any documentation — flagged as inference, not confirmed fact.
  evidence: data/spatial/data-1775857265051.csv header + row content.
  status:  current
  review_date: 2026-08-23
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      manual/nei-zip-extraction
  type:    manual-step
  file:    n/a
  to:      [nb/kriging-layers-extraction]
  from:    [ext/epa-nei, data/kriging-satellite-nei]
  purpose: If the host has no system `unzip` binary, a human must manually extract data/kriging_satellite/nei/2020nei_facility_process_byregions.zip before nei_emissions_extractor.py can proceed — it raises with this exact instruction rather than failing silently.
  what_follows: -
  nuances: This is currently moot in practice — the extractor can't be reached at all today because of the broken-import bug documented on lib/data-extraction, which fails before this code path would ever run.
  evidence: src/data_extraction/nei_emissions_extractor.py:347-350.
  status:  current
  review_date: 2026-08-23
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      manual/street-view-image-collection
  type:    manual-step
  file:    n/a
  to:      [data/kriging-street-view, nb/kriging-street-view-predictors-export, nb/time-series-wind-speed-direction]
  from:    [ext/google-street-view]
  purpose: A human runs Street View image collection (StreetViewNetworkCollector, gated on a real GOOGLE_MAPS_API_KEY) separately from the notebooks, producing the point_dictionaries.jsonl and per-point image folders both predictors_export.ipynb and 01_Obtaining_Wind_Speed_And_Direction.ipynb expect as pre-existing input.
  what_follows: -
  nuances: The collector call itself is commented out in-place in predictors_export.ipynb (cell 10) with a markdown note describing it as a step to run separately — this is documented in the notebook, not just inferred.
  evidence: notebooks/kriging_street_view/predictors_export.ipynb cell 10.
  status:  current
  review_date: 2026-08-23
  checked: 2026-08-23 code_sha=n/a
)

Node(
  id:      manual/imagery-quality-study-area-copy
  type:    manual-step
  file:    n/a
  to:      [data/imagery-quality-assessment]
  from:    [data/imagery-weather-exploration]
  purpose: A human copies boston_buildings_study_area.geojson and street_network.geojson from data/2026_07_21_imagery_and_weather_station_data_exploration/ into data/2026_08_03_imagery_quality_assessment/, verbatim.
  what_follows: -
  nuances: Confirmed by MD5 match between the two locations' copies (3de8baa3a3d20382b1557f7e0960d29a) combined with a later mtime (Aug 3) than the originals (Jul 22) and the absence of any writing code in either directory's producing notebooks — not an inference, a direct forensic finding.
  evidence: md5 comparison; nb/imagery-exploration-2 and nb/imagery-quality-assessment nodes.
  status:  current
  review_date: 2026-08-23
  checked: 2026-08-23 code_sha=n/a
)
