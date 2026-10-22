import json
import os
import sys
import time
from pathlib import Path

import torch

import paths
from features_core import compute_point_features, REQUIRED_FEATURES

sys.path.insert(0, str(Path(paths.RUN_DIR)/"src"))

from alivestreets.features.facade_features import FacadeFeatureExtractor
from alivestreets.features.gvi_feature import GVIFeatureExtractor


def slice_output_path(entry):
    safe_site = entry["site_name"].strip().replace(" ", "_").replace("—", "-")
    return Path(paths.SLICES_DIR)/f"{safe_site}__{entry['start']:05d}_{entry['end']:05d}.json"


def remap_view_paths(point_dictionary, site_name):
    view_paths = point_dictionary.get("view_paths") or []
    remapped = []
    for path in view_paths:
        if path.startswith(paths.LOCAL_PREFIX):
            path = paths.SITES_DIR + path[len(paths.LOCAL_PREFIX):]
        remapped.append(path)
    return remapped


def main():
    task_id = int(sys.argv[1])

    with open(Path(paths.RUN_DIR)/"data"/"slices.json") as f:
        slices = json.load(f)

    entry = slices[task_id]
    output_path = slice_output_path(entry)
    output_path.parent.mkdir(parents = True, exist_ok = True)

    if output_path.exists():
        print(f"slice already done: {output_path.name}")
        return

    n_threads = int(os.environ.get("SLURM_CPUS_PER_TASK", "8"))
    torch.set_num_threads(n_threads)

    facade_extractor = FacadeFeatureExtractor()
    facade_extractor.download_model(save_path = paths.MODEL_PATH, verbose = False)
    facade_extractor.model.to("cpu")

    gvi_extractor = GVIFeatureExtractor()
    gvi_extractor.download_model(save_path = paths.MODEL_PATH, verbose = False)
    gvi_extractor.model.to("cpu")

    site_name = entry["site_name"]
    jsonl_path = Path(paths.SITES_DIR)/site_name/"Imagery"/"point_dictionaries.jsonl"
    with open(jsonl_path) as f:
        point_dictionaries = [json.loads(line) for line in f if line.strip()]

    records = []
    started = time.time()
    for point_index in range(entry["start"], entry["end"]):
        point_dictionary = point_dictionaries[point_index]
        view_paths = remap_view_paths(point_dictionary, site_name)
        point_features = compute_point_features(
            point_dictionary,
            facade_extractor,
            gvi_extractor,
            view_paths = view_paths
        )
        point_features["site_name"] = site_name
        point_features["point_index"] = point_index
        records.append(point_features)

    elapsed = time.time() - started
    n_points = len(records)
    print(f"{site_name} [{entry['start']}:{entry['end']}] {n_points} points in {elapsed:.1f}s "
          f"({elapsed / max(n_points, 1):.2f}s/point)")

    temporary_path = output_path.with_suffix(".tmp")
    with open(temporary_path, "w") as f:
        json.dump(records, f)
    os.replace(temporary_path, output_path)
    print(f"written: {output_path}")


if __name__ == "__main__":
    main()
