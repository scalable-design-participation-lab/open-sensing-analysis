import json
from pathlib import Path

import pandas as pd

import paths
from features_core import REQUIRED_FEATURES

COORDINATE_TOLERANCE = 1e-9
FEATURES_FILE_NAME = "built_environment_features.csv"

slice_paths = sorted(Path(paths.SLICES_DIR).glob("*.json"))
print(f"slice files: {len(slice_paths)}")

records = []
for slice_path in slice_paths:
    with open(slice_path) as f:
        records.extend(json.load(f))

print(f"records: {len(records)}")

all_features_data = pd.DataFrame(records)
leading_columns = ["site_name", "point_index"]
ordered_columns = leading_columns + [c for c in all_features_data.columns if c not in leading_columns]
all_features_data = all_features_data[ordered_columns]

failures = []
for site_name, site_features in all_features_data.groupby("site_name"):
    jsonl_path = Path(paths.SITES_DIR)/site_name/"Imagery"/"point_dictionaries.jsonl"
    with open(jsonl_path) as f:
        point_dictionaries = [json.loads(line) for line in f if line.strip()]

    site_features = site_features.sort_values("point_index")
    indices = list(site_features["point_index"])
    expected = list(range(len(point_dictionaries)))

    if indices != expected:
        failures.append(f"{site_name}: point_index set is {len(indices)} rows, expected {len(expected)} contiguous")
        continue

    for (_, row), point_dictionary in zip(site_features.iterrows(), point_dictionaries):
        if abs(row["latitude"] - point_dictionary["latitude"]) > COORDINATE_TOLERANCE:
            failures.append(f"{site_name}: latitude mismatch at point {row['point_index']}")
            break
        if abs(row["longitude"] - point_dictionary["longitude"]) > COORDINATE_TOLERANCE:
            failures.append(f"{site_name}: longitude mismatch at point {row['point_index']}")
            break

    missing = [f for f in REQUIRED_FEATURES if f not in site_features.columns]
    if missing:
        failures.append(f"{site_name}: missing columns {missing}")
        continue

    null_counts = site_features[REQUIRED_FEATURES].isna().sum()
    if null_counts.sum() > 0:
        failures.append(f"{site_name}: null feature values {dict(null_counts[null_counts > 0])}")

    zero_views = int((site_features["n_views"] == 0).sum())
    print(f"{site_name}: {len(site_features)} points, {zero_views} points with no usable view")

    site_output = Path(paths.SITES_DIR)/site_name/FEATURES_FILE_NAME
    site_features.to_csv(site_output, index = False)

if failures:
    for failure in failures:
        print(f"FAIL {failure}")
    raise SystemExit("merge validation failed")

combined_path = Path(paths.RUN_DIR)/"data"/FEATURES_FILE_NAME
all_features_data.sort_values(["site_name", "point_index"]).to_csv(combined_path, index = False)

print()
print(f"columns: {list(all_features_data.columns)}")
print(f"combined rows: {len(all_features_data)}")
print(f"written: {combined_path}")
print("MERGE VALIDATED")
