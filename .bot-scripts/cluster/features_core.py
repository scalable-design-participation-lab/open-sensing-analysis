import os
import numpy as np
from PIL import Image

RATIO_CLASSES = ["sky", "road", "sidewalk"]
COUNT_CLASSES = [
    "vehicle", "facade", "bench", "door", "graffiti", "person",
    "signage", "street light", "trash", "utility pole", "window"
]
VEGETATION_CLASS = "vegetation"

RATIO_NAME_MAP = {"sky": "sky_ratio", "road": "road_ratio", "sidewalk": "sidewalk_ratio"}
COUNT_NAME_MAP = {
    "vehicle": "n_cars",
    "facade": "n_facades",
    "bench": "n_benches",
    "door": "n_doors",
    "graffiti": "n_graffiti",
    "person": "n_persons",
    "signage": "n_signage",
    "street light": "n_street_lights",
    "trash": "n_trash",
    "utility pole": "n_utility_poles",
    "window": "n_windows",
}

CONFIDENCE_THRESHOLDS = {"sky": 0.0, "road": 0.2, "facade": 0.2, "vehicle": 0.2}
DEFAULT_CONFIDENCE_THRESHOLD = 0.2

COUNT_FEATURES = [COUNT_NAME_MAP[name] for name in COUNT_CLASSES]
RATIO_FEATURES = [RATIO_NAME_MAP[name] for name in RATIO_CLASSES]
REQUIRED_FEATURES = ["n_views", "gvi"] + RATIO_FEATURES + COUNT_FEATURES


def mask_ratio(masks):
    if not masks:
        return 0.0
    final_mask = np.logical_or.reduce(masks)
    return float(np.mean(final_mask))


def compute_view_features(view_path, facade_extractor, gvi_extractor):
    if not os.path.exists(view_path):
        return None

    try:
        with Image.open(view_path) as img:
            image = np.array(img)
    except Exception:
        return None

    view_features = {}

    for class_name in COUNT_CLASSES:
        masks, _ = facade_extractor.get_masks(
            image,
            class_name = class_name,
            confidence_threshold = CONFIDENCE_THRESHOLDS.get(class_name, DEFAULT_CONFIDENCE_THRESHOLD)
        )
        view_features[COUNT_NAME_MAP[class_name]] = float(len(masks))

    for class_name in RATIO_CLASSES:
        masks, _ = facade_extractor.get_masks(
            image,
            class_name = class_name,
            confidence_threshold = CONFIDENCE_THRESHOLDS.get(class_name, DEFAULT_CONFIDENCE_THRESHOLD)
        )
        view_features[RATIO_NAME_MAP[class_name]] = mask_ratio(masks)

    view_features["gvi"] = float(gvi_extractor.compute(image)["GVI"])

    return view_features


def compute_point_features(point_dictionary, facade_extractor, gvi_extractor, view_paths = None):
    if view_paths is None:
        view_paths = point_dictionary.get("view_paths") or []

    view_features_list = [
        compute_view_features(path, facade_extractor, gvi_extractor) for path in view_paths
    ]
    view_features_list = [v for v in view_features_list if v is not None]

    n_views = len(view_features_list)
    point_features = {
        "latitude": point_dictionary.get("latitude"),
        "longitude": point_dictionary.get("longitude"),
        "n_views": n_views
    }

    if n_views == 0:
        return point_features

    for feature_name in COUNT_FEATURES:
        point_features[feature_name] = float(sum(v[feature_name] for v in view_features_list))

    for feature_name in RATIO_FEATURES + ["gvi"]:
        point_features[feature_name] = float(np.mean([v[feature_name] for v in view_features_list]))

    return point_features
