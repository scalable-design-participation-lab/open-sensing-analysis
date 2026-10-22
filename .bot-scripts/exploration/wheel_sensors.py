import sys, json
from pathlib import Path
import numpy as np, pandas as pd
from PIL import Image
import matplotlib
matplotlib.use("Agg")
from matplotlib.colors import LinearSegmentedColormap

ROOT = Path("/Users/legariapena.j/Documents/open-sensing-analysis/open-sensing-analysis")
D = ROOT/"data/2026_09_16_site_built_environment_comparison"
sys.path.append(str(ROOT/"src"/"time_series"))
from series_aligner import align_sensor_series_from_list
from time_series_comparison_metrics import compute_rmse

from imageable.visualization.wheel_visualization import WheelElement, WheelVisualization

FOOTPRINT_M = 50
PSEN = ROOT/"data"/"sensors"
PS = ROOT/"data"/"2026_08_26_sensor_comparisons"/"data"

site_to_sensor = {
    "Carter Field": ("Boston Carter Field (ours)", "Carter (ours)", "boston_carter_field/boston_carter_field.csv"),
    "Carter Field — 2": ("Boston Carter Field (ref)", "Carter (ref)", "boston_carter_field_reference/MOD-00157-CarterField.csv"),
    "Robinson Hall": ("Boston Robinson Hall", "Robinson", "boston_robinson_hall/boston_robinson_hall.csv"),
    "Gainsborough Parking Garage": ("Boston Gainsborough Parking", "Gainsborough", "boston_gainsborough_parking/boston_gainsborough_parking.csv"),
    "West Village B": ("Boston West Village B", "West Village B", "boston_west_village_b/boston_west_village_b.csv"),
    "World Series Way ": ("Boston World Series Way", "World Series", "boston_world_series_way/boston_world_series_way.csv"),
}
EPA = {"Roxbury (EPA)": "DUDLEY SQUARE ROXBURY", "Von Hillern (EPA)": "VON HILLERN ST"}
MINP, MAXP = 0.05, 200

loc = pd.read_csv(ROOT/"data/spatial/data-1775857265051.csv")
coords = {}
for site, eco in [("Carter Field","Carter Field"),("Robinson Hall","Robinson Hall"),
                  ("Gainsborough Parking Garage","Gainsborough Parking Garage"),
                  ("West Village B","West Village B"),("World Series Way ","World Series Way")]:
    r = loc[loc["ecohub_location"].str.strip()==eco]
    coords[site] = (float(r["lat"].iloc[0]), float(r["lon"].iloc[0]))
coords["Carter Field — 2"] = (42.3382, -71.0851)

def hav(la1,lo1,la2,lo2):
    R=6371000.0; p1,p2=np.radians(la1),np.radians(la2)
    a=np.sin((p2-p1)/2)**2+np.cos(p1)*np.cos(p2)*np.sin(np.radians(lo2-lo1)/2)**2
    return 2*R*np.arcsin(np.sqrt(a))

feats = pd.read_csv(D/"built_environment_features.csv")
pm = pd.read_csv(PS/"boston_pm25_combined.csv")
epa_data = {}
for k,v in EPA.items():
    e = pm[pm["site_name"]==v].copy(); e["timestamp"]=e["date"]; epa_data[k]=e

sensor_data, rh_daily = {}, {}
for site,(sname,abbr,rel) in site_to_sensor.items():
    d = pd.read_csv(PSEN/rel)
    if "temperature" not in d.columns: d["temperature"]=d["temp"]
    p = pd.to_numeric(d["pm25"],errors="coerce")
    d["pm25"] = p.where((p>=MINP)&(p<=MAXP))
    sensor_data[sname]=d
    rc = "relative_humidity" if "relative_humidity" in d.columns else "rh"
    fr = pd.DataFrame({"t":pd.to_datetime(d["timestamp"],errors="coerce",utc=True),
                       "rh":pd.to_numeric(d[rc],errors="coerce")}).dropna()
    rh_daily[sname] = fr.set_index("t")["rh"].resample("24h").mean()
H = pd.DataFrame(rh_daily).dropna()
print(f"shared humidity days: {len(H)}")

rows=[]
for site,(sname,abbr,rel) in site_to_sensor.items():
    la,lo = coords[site]
    g = feats[feats["site_name"]==site].copy()
    g["d"] = hav(la,lo,g["latitude"].values,g["longitude"].values)
    near = g[g["d"]<=FOOTPRINT_M]
    rmses=[]
    for k in EPA:
        a,_ = align_sensor_series_from_list(
            sensor_dataframes=[epa_data[k], sensor_data[sname]], variable_name="pm25",
            time_column="timestamp", sensor_names=[k,sname], sampling_interval="24h")
        if len(a): rmses.append(compute_rmse(list(a[k]), list(a[sname])))
    nearest = g.sort_values("d").iloc[0]
    img_path = D/site/"Imagery"/f"point_{int(nearest['point_index'])}"/"sidewalk_views"/"sidewalk_left.jpg"
    rows.append(dict(site=site, label=abbr, n_points=len(near), n_images=int(near["n_views"].sum()),
        gvi=float(near["gvi"].mean()), road_ratio=float(near["road_ratio"].mean()),
        people=float(near["n_persons"].mean()), humidity=float(H[sname].median()),
        pm25_rmse=float(np.mean(rmses)), nearest_m=float(nearest["d"]), img=str(img_path)))
prof = pd.DataFrame(rows)
pd.set_option("display.width",240)
print(prof[["label","n_points","n_images","nearest_m","gvi","road_ratio","people","humidity","pm25_rmse"]].round(3).to_string(index=False))

FEATURES=[("gvi","GVI"),("road_ratio","Road ratio"),("people","People"),
          ("humidity","Humidity (%)"),("pm25_rmse","PM2.5 RMSE")]
elements=[]
for col,label in FEATURES:
    for _,r in prof.iterrows():
        elements.append(WheelElement(data=float(r[col]), group_name=r["label"], feature_name=label))
for _,r in prof.iterrows():
    im = Image.open(r["img"]).convert("RGB")
    im.thumbnail((420,420))
    elements.append(WheelElement(data=np.asarray(im), group_name=r["label"], feature_name="Nearest view"))

dracula_seq = LinearSegmentedColormap.from_list("dracula_seq",
    ["#282a36","#44475a","#6272a4","#bd93f9","#ff79c6","#ff6c6c","#ff5555"], N=256)

viz = WheelVisualization(elements, radius_size=40, image_scale=0.5,
                         image_outer_boost=1.2, reduction_factor=0.7)
out = D/f"wheel_sensors_{FOOTPRINT_M}m.png"
viz.draw_wheel(cmap=dracula_seq, radial_alpha=0.1, circle_linewidth=0.7,
               figure_height=13, figure_width=13, save_path=str(out),
               group_label_boost=1.7, wedge_gamma=0.6)
print(f"\nSaved {out}")
