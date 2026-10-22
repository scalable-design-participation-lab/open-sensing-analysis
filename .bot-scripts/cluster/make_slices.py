import json
import os
from pathlib import Path

import paths

SLICE_SIZE = 40

sites_dir = Path(paths.SITES_DIR)
slices = []

for site_path in sorted(sites_dir.iterdir()):
    jsonl_path = site_path/"Imagery"/"point_dictionaries.jsonl"
    if not jsonl_path.exists():
        continue
    with open(jsonl_path) as f:
        n_points = sum(1 for line in f if line.strip())
    for start in range(0, n_points, SLICE_SIZE):
        end = min(start + SLICE_SIZE, n_points)
        slices.append({"site_name": site_path.name, "start": start, "end": end})

out_path = Path(paths.RUN_DIR)/"data"/"slices.json"
out_path.parent.mkdir(parents = True, exist_ok = True)
with open(out_path, "w") as f:
    json.dump(slices, f, indent = 1)

print(f"sites: {len(set(s['site_name'] for s in slices))}")
print(f"points: {sum(s['end'] - s['start'] for s in slices)}")
print(f"slices: {len(slices)}")
print(f"array range: 0-{len(slices) - 1}")
