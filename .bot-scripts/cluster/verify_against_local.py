import json, sys, os
sys.path.insert(0, "/private/tmp/claude-504/-Users-legariapena-j-Documents-open-sensing-analysis-open-sensing-analysis/7485ff47-57c1-4428-b571-58a8162afd0f/scratchpad/clusrc")
import torch
torch.set_num_threads(8)
from features_core import compute_point_features
from alivestreets.features.facade_features import FacadeFeatureExtractor
from alivestreets.features.gvi_feature import GVIFeatureExtractor

MODEL = "/Users/legariapena.j/Documents/open-sensing-analysis/open-sensing-analysis/notebooks/2026_09_16_site_built_environment_comparison/facades_model.pt"
PARENT = "/Users/legariapena.j/Documents/open-sensing-analysis/open-sensing-analysis/data/2026_09_16_site_built_environment_comparison"

fx = FacadeFeatureExtractor(); fx.download_model(save_path=MODEL, verbose=False); fx.model.to("cpu")
gx = GVIFeatureExtractor(); gx.download_model(save_path=MODEL, verbose=False); gx.model.to("cpu")

with open(f"{PARENT}/Carter Field/Imagery/point_dictionaries.jsonl") as f:
    pts = [json.loads(l) for l in f if l.strip()]

out = {}
for i in [0, 1, 2]:
    r = compute_point_features(pts[i], fx, gx)
    out[i] = r
    print(f"point {i}: {json.dumps(r, sort_keys=True)}")

with open("/private/tmp/claude-504/-Users-legariapena-j-Documents-open-sensing-analysis-open-sensing-analysis/7485ff47-57c1-4428-b571-58a8162afd0f/scratchpad/local_ref.json","w") as f:
    json.dump(out, f, indent=1, sort_keys=True)
print("WROTE local_ref.json")
