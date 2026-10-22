"""How much does the aggregation radius change the description of a site?

Writes: built_environment_distance_vs_error{,_100m}.png,
        carter_field_radar_by_radius.gif, carter_field_radar_by_points.gif,
        carter_field_feature_trajectories.png
"""
import sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import PillowWriter
import _common as c

sys.path.append("/Users/legariapena.j/Documents/SV-paper-refinement/12 - Results Reconstruction/src")
from RadarChart import RadarChart

FOOTPRINT_RADIUS_M = 100
RADAR_FEATURES = ["n_facades", "gvi", "sky_ratio", "n_cars", "n_persons", "road_ratio"]
RADAR_LABELS = ["Facades", "GVI", "Sky ratio", "Cars", "People", "Road ratio"]
CARTER_SITE = "Carter Field"

features = c.add_distance_to_sensor(c.load_features(), c.load_sensor_coordinates())
summary_300 = c.site_summary_at(features)
summary_100 = c.site_summary_at(features, FOOTPRINT_RADIUS_M)
station_temperature, station_pm25, sensor_data, _, _ = c.load_sensor_series()
metrics = c.sensor_station_metrics(station_temperature, station_pm25, sensor_data)

kept = features[features["distance_to_sensor_m"] <= FOOTPRINT_RADIUS_M]
print(f"points and images within {FOOTPRINT_RADIUS_M} m:")
print(pd.DataFrame({"points": kept.groupby("site_name").size(),
                    "images": kept.groupby("site_name")["n_views"].sum(),
                    "points_300m": features.groupby("site_name").size()}).to_string())
comparison = pd.DataFrame({"gvi_300m": summary_300["gvi"], "gvi_100m": summary_100["gvi"],
                           "cars_300m": summary_300["n_cars"], "cars_100m": summary_100["n_cars"]})
comparison["gvi_change"] = comparison["gvi_100m"] - comparison["gvi_300m"]
print("\n" + comparison.sort_values("gvi_100m").round(3).to_string())

# ---- feature-space distance to the paired station, both footprints ----
for label, summary in [("", summary_300), ("_100m", summary_100)]:
    vectors = summary[c.VECTOR_FEATURES]
    standardized = (vectors - vectors.mean())/vectors.std(ddof=0)
    column = f"distance{label}"
    metrics[column] = [
        float(np.linalg.norm(standardized.loc[row["site_name"]] -
                             standardized.loc[c.EPA_STATION_TO_SITE_NAME[row["epa_station"]]]))
        for _, row in metrics.iterrows()]

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    for ax, variable in zip(axes, ["temperature", "pm25"]):
        subset = metrics[metrics["variable"] == variable]
        for station_name, group in subset.groupby("epa_station"):
            ax.scatter(group[column], group["rmse"], s=140, color=c.EPA_STATION_TO_COLOR[station_name],
                       edgecolor="black", linewidth=0.6, alpha=0.9, label=station_name, zorder=3)
        for _, row in subset.iterrows():
            ax.annotate(row["abbreviation"], (row[column], row["rmse"]),
                        textcoords="offset points", xytext=(7, 5), fontsize=9)
        radius_label = "300 m" if label == "" else f"{FOOTPRINT_RADIUS_M} m"
        ax.set_xlabel(f"Built environment distance to EPA station, {radius_label} footprint")
        ax.set_ylabel(c.VARIABLE_TO_LABEL[variable]); ax.set_title(c.VARIABLE_TO_LABEL[variable])
        ax.grid(alpha=0.25, zorder=0); ax.legend(frameon=True)
    plt.tight_layout()
    plt.savefig(c.DATA/f"built_environment_distance_vs_error{label}.png", dpi=300, bbox_inches="tight")

# ---- Carter Field: radar as the radius grows ----
carter = features[features["site_name"] == CARTER_SITE].sort_values("distance_to_sensor_m").reset_index(drop=True)

def profile_by(kind):
    rows = []
    steps = list(range(50, 300, 20)) + [300] if kind == "radius" else \
            list(range(10, len(carter)+1, 10)) + ([len(carter)] if len(carter) % 10 else [])
    for step in steps:
        subset = carter[carter["distance_to_sensor_m"] <= step] if kind == "radius" else carter.iloc[:step]
        record = {"step": step, "points": len(subset), "images": int(subset["n_views"].sum()),
                  "radius_m": float(subset["distance_to_sensor_m"].max())}
        record.update({f: float(subset[f].mean()) for f in RADAR_FEATURES})
        rows.append(record)
    return pd.DataFrame(rows)

for kind, filename, fps in [("radius", "carter_field_radar_by_radius.gif", 2),
                            ("points", "carter_field_radar_by_points.gif", 4)]:
    profile = profile_by(kind)
    minimums = [0.0]*len(RADAR_FEATURES)
    maximums = [float(np.ceil(profile[f].max()*110)/100) for f in RADAR_FEATURES]
    fig, ax = plt.subplots(figsize=(7.5, 7.5))
    radar, writer = RadarChart(), PillowWriter(fps=fps)
    with writer.saving(fig, str(c.DATA/filename), dpi=105):
        for _, row in profile.iterrows():
            ax.clear()
            legend = f"Carter Field, {int(row['step'])} m" if kind == "radius" else \
                     f"Carter Field, nearest {int(row['step'])} points"
            radar.createChart([[row[f] for f in RADAR_FEATURES]], RADAR_LABELS, minimums, maximums,
                              [c.PINK_DRACULA], [legend], fillAlpha=0.45, labelFontSize=12,
                              legendFontSize=12, legendLocation="upper center",
                              legendAnchor=(0.5, 0.02), labelOffset=1.2, ax=ax)
            ax.set_title(f"{int(row['points'])} points, {int(row['images'])} images, reaches {row['radius_m']:.0f} m",
                         fontsize=12, pad=18)
            writer.grab_frame()
    print(f"\nwrote {filename} ({len(profile)} frames)")
    if kind == "points":
        point_profile = profile

# ---- is the deformation continuous? ----
fig, axes = plt.subplots(2, 3, figsize=(17, 9))
for ax, feature, label in zip(axes.flatten(), RADAR_FEATURES, RADAR_LABELS):
    ax.plot(point_profile["points"], point_profile[feature], marker="o", ms=4, lw=1.8, color=c.PINK_DRACULA)
    ax.set_title(label); ax.set_xlabel("nearest N points"); ax.grid(alpha=0.25)
    changes = np.diff(point_profile[feature].values)
    for i in range(1, len(changes)):
        if changes[i]*changes[i-1] < 0:
            ax.axvline(point_profile["points"].values[i+1], color="gray", lw=0.5, alpha=0.35)
fig.suptitle("Carter Field: each feature as points are added nearest-first\n(vertical lines mark reversals)", fontsize=13)
plt.tight_layout()
plt.savefig(c.DATA/"carter_field_feature_trajectories.png", dpi=200, bbox_inches="tight")

print("\ndirection reversals per feature:")
for feature, label in zip(RADAR_FEATURES, RADAR_LABELS):
    changes = np.diff(point_profile[feature].values)
    reversals = sum(1 for i in range(1, len(changes)) if changes[i]*changes[i-1] < 0)
    largest = np.nanmax(np.abs(changes))/(point_profile[feature].max() - point_profile[feature].min())
    print(f"  {label:11s} reversals={reversals:3d}  largest step = {largest*100:5.1f}% of range")
