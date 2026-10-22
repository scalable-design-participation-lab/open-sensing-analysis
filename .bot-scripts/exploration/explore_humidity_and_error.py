"""Does humidity explain the sensor error, and does greenery explain humidity?

Writes: pm25_residual_vs_humidity.png, gvi_vs_humidity.png, humidity_vs_error.png, gvi_vs_error.png
"""
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import _common as c

RELATIVE_HUMIDITY_BANDS = [0, 50, 60, 70, 80, 100]
BAND_CENTRES = [25, 55, 65, 75, 90]
HIGHLIGHT = "Boston World Series Way"
RH_TOLERANCE = pd.Timedelta("12h")

features = c.add_distance_to_sensor(c.load_features(), c.load_sensor_coordinates())
summary_300 = c.site_summary_at(features)
summary_100 = c.site_summary_at(features, 100)
station_temperature, station_pm25, sensor_data, daily_humidity, humidity_frame = c.load_sensor_series()
metrics = c.sensor_station_metrics(station_temperature, station_pm25, sensor_data)
sensor_to_site = {s: k for k, (s, _, _) in c.SITE_TO_SENSOR.items()}
abbreviation = {s: a for _, (s, a, _) in c.SITE_TO_SENSOR.items()}

# ---- residual against the sensor's own humidity, day by day ----
rows = []
for sensor_name, daily in daily_humidity.items():
    for station_name in c.EPA_STATION_TO_SITE_NAME:
        aligned, _ = c.align_sensor_series_from_list(
            sensor_dataframes=[station_pm25[station_name], sensor_data[sensor_name]],
            variable_name="pm25", time_column="timestamp",
            sensor_names=[station_name, sensor_name], sampling_interval=c.SAMPLING_INTERVAL)
        if len(aligned) == 0:
            continue
        index = pd.to_datetime(aligned.index, utc=True)
        matched = daily.reindex(index, method="nearest", tolerance=RH_TOLERANCE)
        residual = np.asarray(aligned[sensor_name], float) - np.asarray(aligned[station_name], float)
        for value, humidity in zip(residual, matched.values):
            rows.append(dict(sensor_name=sensor_name, residual=value, relative_humidity=humidity))
residuals = pd.DataFrame(rows).dropna()
residuals["band"] = pd.cut(residuals["relative_humidity"], RELATIVE_HUMIDITY_BANDS)
print(f"paired days: {len(residuals)}\n")
print(residuals.pivot_table(index="sensor_name", columns="band", values="residual",
                            aggfunc="mean", observed=True).round(2).to_string())
print("\nslope of residual on relative humidity, ug/m3 per 1 percent")
for sensor_name, group in residuals.groupby("sensor_name"):
    slope = np.polyfit(group["relative_humidity"], group["residual"], 1)[0]
    low = group[group["relative_humidity"] < 55]["residual"].mean()
    high = group[group["relative_humidity"] > 75]["residual"].mean()
    print(f"  {sensor_name:29s} slope {slope:+.3f}  RH<55 {low:+5.2f}  RH>75 {high:+5.2f}  change {high-low:+5.2f}")

fig, axes = plt.subplots(1, 2, figsize=(16, 6.5))
for sensor_name, group in residuals.groupby("sensor_name"):
    band_means = group.groupby("band", observed=True)["residual"].mean()
    is_highlight = sensor_name == HIGHLIGHT
    axes[0].plot([BAND_CENTRES[list(band_means.index.categories).index(b)] for b in band_means.index],
                 band_means.values, marker="o", linewidth=3.0 if is_highlight else 1.4,
                 markersize=9 if is_highlight else 5,
                 color=c.PINK_DRACULA if is_highlight else "gray",
                 alpha=1.0 if is_highlight else 0.65, zorder=3 if is_highlight else 2,
                 label=abbreviation[sensor_name])
axes[0].axhline(0, color="black", linewidth=0.8)
axes[0].set_xlabel("Sensor relative humidity, daily mean (%)")
axes[0].set_ylabel("PM2.5 residual, sensor - station (ug/m3)")
axes[0].set_title("Every sensor reads higher as humidity rises")
axes[0].grid(alpha=0.25); axes[0].legend(frameon=True, fontsize=9)
order = list(humidity_frame.columns)
box = axes[1].boxplot([humidity_frame[s].dropna() for s in order], vert=False,
                      tick_labels=[abbreviation[s] for s in order], patch_artist=True)
for patch, sensor_name in zip(box["boxes"], order):
    patch.set_facecolor(c.PINK_DRACULA if sensor_name == HIGHLIGHT else "lightgray")
axes[1].set_xlabel("Sensor relative humidity, daily mean (%)")
axes[1].set_title("World Series Way is not the most humid site")
axes[1].grid(alpha=0.25, axis="x")
plt.tight_layout(); plt.savefig(c.DATA/"pm25_residual_vs_humidity.png", dpi=300, bbox_inches="tight")

# ---- GVI against humidity, both footprints ----
def gvi_humidity(summary):
    out = []
    for sensor_name in humidity_frame.columns:
        values = humidity_frame[sensor_name]
        out.append(dict(sensor_name=sensor_name,
                        gvi=float(summary.loc[sensor_to_site[sensor_name], "gvi"]),
                        median=float(values.median()),
                        q25=float(values.quantile(0.25)), q75=float(values.quantile(0.75))))
    return pd.DataFrame(out).sort_values("gvi")

fig, axes = plt.subplots(1, 2, figsize=(16, 7), sharey=True)
for ax, (label, summary) in zip(axes, [("300 m footprint", summary_300), ("100 m footprint", summary_100)]):
    for _, row in gvi_humidity(summary).iterrows():
        is_highlight = row["sensor_name"] == HIGHLIGHT
        is_carter = "Carter" in row["sensor_name"]
        ax.errorbar(row["gvi"], row["median"],
                    yerr=[[row["median"]-row["q25"]], [row["q75"]-row["median"]]], fmt="o",
                    markersize=13 if is_highlight else 10,
                    color=c.PINK_DRACULA if is_highlight else ("#FFB86C" if is_carter else c.GREEN_DRACULA),
                    ecolor="gray", elinewidth=1.3, capsize=4,
                    markeredgecolor="black", markeredgewidth=0.6, zorder=3)
        ax.annotate(abbreviation[row["sensor_name"]], (row["gvi"], row["median"]),
                    textcoords="offset points", xytext=(11, 4), fontsize=10)
    ax.set_xlabel("Site GVI (mean over sampled points)"); ax.set_title(label); ax.grid(alpha=0.25)
axes[0].set_ylabel("Sensor relative humidity, daily mean (%)")
fig.suptitle(f"GVI against humidity, {len(humidity_frame)} shared days (Carter pair in orange)", fontsize=13)
plt.tight_layout(); plt.savefig(c.DATA/"gvi_vs_humidity.png", dpi=300, bbox_inches="tight")

# ---- humidity and GVI against error ----
median_humidity = humidity_frame.median()
metrics["sensor_median_humidity"] = [float(median_humidity[s]) for s in metrics["sensor_name"]]
metrics["gvi_300m"] = [float(summary_300.loc[s, "gvi"]) for s in metrics["site_name"]]
metrics["gvi_100m"] = [float(summary_100.loc[s, "gvi"]) for s in metrics["site_name"]]

def scatter_panel(ax, subset, x_column, x_label, y_label, title):
    for station_name, group in subset.groupby("epa_station"):
        ax.scatter(group[x_column], group["rmse"], s=150, color=c.EPA_STATION_TO_COLOR[station_name],
                   edgecolor="black", linewidth=0.6, alpha=0.9, label=station_name, zorder=3)
    for _, row in subset.iterrows():
        ax.annotate(row["abbreviation"], (row[x_column], row["rmse"]),
                    textcoords="offset points", xytext=(8, 5), fontsize=9)
    ax.set_xlabel(x_label); ax.set_ylabel(y_label); ax.set_title(title)
    ax.grid(alpha=0.25, zorder=0); ax.legend(frameon=True, fontsize=9)

fig, axes = plt.subplots(1, 2, figsize=(16, 7))
for ax, variable in zip(axes, ["temperature", "pm25"]):
    scatter_panel(ax, metrics[metrics["variable"] == variable], "sensor_median_humidity",
                  "Sensor median relative humidity (%)", c.VARIABLE_TO_LABEL[variable],
                  c.VARIABLE_TO_LABEL[variable])
plt.tight_layout(); plt.savefig(c.DATA/"humidity_vs_error.png", dpi=300, bbox_inches="tight")

fig, axes = plt.subplots(2, 2, figsize=(16, 13))
for row_index, (column, label) in enumerate([("gvi_300m", "300 m"), ("gvi_100m", "100 m")]):
    for column_index, variable in enumerate(["temperature", "pm25"]):
        scatter_panel(axes[row_index, column_index], metrics[metrics["variable"] == variable], column,
                      f"Site GVI, {label} footprint", c.VARIABLE_TO_LABEL[variable],
                      f"{c.VARIABLE_TO_LABEL[variable]} against GVI, {label}")
plt.tight_layout(); plt.savefig(c.DATA/"gvi_vs_error.png", dpi=300, bbox_inches="tight")
print(f"\nwrote 4 figures to {c.DATA}")
