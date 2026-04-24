from __future__ import annotations

import io
from pathlib import Path
import subprocess
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import CRS

from data_extract import BBox, DataExtractor


class NEIEmissionsExtractor(DataExtractor):
    """
    Extract EPA NEI emissions (point + area) from a local dataset.

    Supported local formats:
    - geospatial vector: `.gpkg`, `.shp`, `.geojson`, `.parquet`
    - tabular: `.csv` / `.txt` with lon/lat columns
    """

    def __init__(
        self,
        local_data_path: str | Path,
        emission_column: str | None = None,
        source_type_column: str | None = None,
        longitude_column: str | None = None,
        latitude_column: str | None = None,
        point_labels: tuple[str, ...] = ("POINT",),
        area_labels: tuple[str, ...] = ("AREA", "NONPOINT"),
        grid_path: str | Path | None = None,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.local_data_path = Path(local_data_path).expanduser().resolve()
        self.emission_column = emission_column
        self.source_type_column = source_type_column
        self.longitude_column = longitude_column
        self.latitude_column = latitude_column
        self.point_labels = tuple(v.upper() for v in point_labels)
        self.area_labels = tuple(v.upper() for v in area_labels)

    @property
    def layer_name(self) -> str:
        return "nei_emissions"

    @property
    def value_columns(self) -> tuple[str, ...]:
        return ("emissions_tpy", "emissions_point_tpy", "emissions_area_tpy")

    def get_data(self, bbox: BBox) -> gpd.GeoDataFrame:
        """
        Read local NEI data and clip to bbox.
        """

        self.validate_bbox(bbox)
        target_crs = self.get_target_crs()
        if target_crs is None:
            raise ValueError("Grid CRS is missing; cannot extract NEI emissions.")
        if not self.local_data_path.exists():
            raise ValueError(f"local_data_path not found: {self.local_data_path}")

        nei = self._read_local_nei()
        if not isinstance(nei, gpd.GeoDataFrame):
            nei = self._frame_to_point_gdf(pd.DataFrame(nei))
        if nei.empty:
            return gpd.GeoDataFrame(
                columns=["emission_tpy", "source_kind", "geometry"],
                geometry="geometry",
                crs=target_crs,
            )

        emission_col = self._resolve_emission_column(nei)
        nei["emission_tpy"] = pd.to_numeric(nei[emission_col], errors="coerce")
        nei = nei[nei["emission_tpy"].notna() & (nei["emission_tpy"] >= 0)].copy()
        if nei.empty:
            return gpd.GeoDataFrame(
                columns=["emission_tpy", "source_kind", "geometry"],
                geometry="geometry",
                crs=target_crs,
            )

        source_col = self._resolve_source_type_column(nei)
        nei["source_kind"] = self._infer_source_kind(nei, source_col)

        if nei.crs is None:
            nei = nei.set_crs("EPSG:4326")
        if nei.crs.to_string() != target_crs:
            nei = nei.to_crs(target_crs)

        clipped = self.clip_to_bbox(nei[["emission_tpy", "source_kind", "geometry"]], bbox=bbox, crs=target_crs)
        if clipped.empty:
            return gpd.GeoDataFrame(
                columns=["emission_tpy", "source_kind", "geometry"],
                geometry="geometry",
                crs=target_crs,
            )
        return clipped

    def align_to_grid(
        self,
        data: gpd.GeoDataFrame,
        grid: gpd.GeoDataFrame,
    ) -> gpd.GeoDataFrame:
        """
        Aggregate NEI emissions into per-cell totals (tons/year).
        """

        out = grid.copy()
        if "id" not in out.columns:
            out["id"] = np.arange(len(out))
        out = out[["id", "geometry"]].copy()
        out["emissions_tpy"] = np.nan
        out["emissions_point_tpy"] = np.nan
        out["emissions_area_tpy"] = np.nan
        if out.empty or data.empty:
            return out

        data_local = data.copy()
        if data_local.crs and out.crs and data_local.crs != out.crs:
            data_local = data_local.to_crs(out.crs)

        point_sources = data_local[data_local["source_kind"] == "point"].copy()
        area_sources = data_local[data_local["source_kind"] == "area"].copy()

        point_sum = pd.Series(dtype=float)
        if not point_sources.empty:
            join = gpd.sjoin(
                point_sources[["emission_tpy", "geometry"]],
                out[["id", "geometry"]],
                how="inner",
                predicate="intersects",
            )
            point_sum = join.groupby("id")["emission_tpy"].sum()

        area_sum = pd.Series(dtype=float)
        if not area_sources.empty:
            area_polys = area_sources[
                area_sources.geometry.geom_type.isin(["Polygon", "MultiPolygon"])
            ].copy()
            if not area_polys.empty:
                area_polys = area_polys.reset_index(drop=False).rename(columns={"index": "src_id"})
                intersections = gpd.overlay(
                    area_polys[["src_id", "emission_tpy", "geometry"]],
                    out[["id", "geometry"]],
                    how="intersection",
                )
                if not intersections.empty:
                    metric_crs = self._metric_crs(out)
                    polys_metric = (
                        area_polys.to_crs(metric_crs) if area_polys.crs != metric_crs else area_polys
                    )
                    inter_metric = (
                        intersections.to_crs(metric_crs)
                        if intersections.crs != metric_crs
                        else intersections
                    )

                    src_area = polys_metric.set_index("src_id").geometry.area.replace(0.0, np.nan)
                    inter_metric["inter_area"] = inter_metric.geometry.area
                    inter_metric["allocated_tpy"] = (
                        inter_metric["emission_tpy"]
                        * inter_metric["inter_area"]
                        / inter_metric["src_id"].map(src_area)
                    )
                    area_sum = inter_metric.groupby("id")["allocated_tpy"].sum(min_count=1)

        total = point_sum.add(area_sum, fill_value=0.0)
        if not total.empty:
            out.loc[out["id"].isin(total.index), "emissions_tpy"] = out["id"].map(total)
        if not point_sum.empty:
            out.loc[out["id"].isin(point_sum.index), "emissions_point_tpy"] = out["id"].map(point_sum)
        if not area_sum.empty:
            out.loc[out["id"].isin(area_sum.index), "emissions_area_tpy"] = out["id"].map(area_sum)
        return out

    def _read_local_nei(self) -> gpd.GeoDataFrame:
        suffix = self.local_data_path.suffix.lower()
        if suffix in {".csv", ".txt"}:
            frame = pd.read_csv(self.local_data_path)
            return self._frame_to_point_gdf(frame)

        if suffix == ".zip":
            with zipfile.ZipFile(self.local_data_path, "r") as archive:
                csv_names = [
                    name
                    for name in archive.namelist()
                    if name.lower().endswith(".csv") and not name.startswith("__MACOSX/")
                ]
                if not csv_names:
                    raise ValueError(
                        f"No CSV found in NEI zip: {self.local_data_path}. "
                        "Use a zip that contains an emissions CSV."
                    )

                preferred_keywords = ("point", "facility", "nei")
                preferred = [
                    name for name in csv_names if any(k in Path(name).name.lower() for k in preferred_keywords)
                ]
                selected = sorted(preferred if preferred else csv_names)[0]
                try:
                    with archive.open(selected, "r") as handle:
                        frame = pd.read_csv(handle, low_memory=False)
                except NotImplementedError:
                    # Some EPA zips use compression methods unsupported by Python's zipfile.
                    frame = self._read_zip_member_with_unzip(self.local_data_path, selected)
            return self._frame_to_point_gdf(frame)

        gdf = gpd.read_file(self.local_data_path)
        if not isinstance(gdf, gpd.GeoDataFrame):
            return self._frame_to_point_gdf(pd.DataFrame(gdf))

        if gdf.empty:
            return gdf

        # Some drivers can return a GeoDataFrame-like object without an active geometry.
        try:
            geom = gdf.geometry
        except Exception:
            return self._frame_to_point_gdf(pd.DataFrame(gdf))

        return gdf[geom.notnull()].copy()

    def _frame_to_point_gdf(self, frame: pd.DataFrame) -> gpd.GeoDataFrame:
        lon_col, lat_col = self._resolve_lon_lat_columns(frame)
        lon_vals = pd.to_numeric(frame[lon_col], errors="coerce")
        lat_vals = pd.to_numeric(frame[lat_col], errors="coerce")
        valid = lon_vals.notna() & lat_vals.notna()
        frame = frame.loc[valid].copy()
        geometry = gpd.points_from_xy(lon_vals.loc[valid], lat_vals.loc[valid])
        gdf = gpd.GeoDataFrame(frame, geometry=geometry, crs="EPSG:4326")
        return gdf[gdf.geometry.notnull()].copy()

    def _resolve_emission_column(self, gdf: gpd.GeoDataFrame) -> str:
        if self.emission_column is not None:
            if self.emission_column not in gdf.columns:
                raise ValueError(f"Configured emission_column not found: {self.emission_column}")
            return self.emission_column

        by_norm = {self._normalize_colname(c): c for c in gdf.columns}
        preferred_norm = [
            "emissiontpy",
            "annemis",
            "annemistpy",
            "annvalue",
            "totalemissions",
            "totalemissionstpy",
        ]
        for norm in preferred_norm:
            if norm in by_norm:
                return by_norm[norm]

        for col in gdf.columns:
            norm = self._normalize_colname(col)
            if "emis" in norm:
                return col

        raise ValueError(
            "Could not infer emission column from NEI file. "
            "Set `emission_column` explicitly."
        )

    def _resolve_source_type_column(self, gdf: gpd.GeoDataFrame) -> str | None:
        if self.source_type_column is not None:
            if self.source_type_column not in gdf.columns:
                raise ValueError(f"Configured source_type_column not found: {self.source_type_column}")
            return self.source_type_column

        by_norm = {self._normalize_colname(c): c for c in gdf.columns}
        candidate_norms = [
            "sourcekind",
            "sourcetype",
            "facilitysourcetype",
            "datacategory",
            "sectortype",
        ]
        for norm in candidate_norms:
            if norm in by_norm:
                return by_norm[norm]
        return None

    def _infer_source_kind(self, gdf: gpd.GeoDataFrame, source_col: str | None) -> pd.Series:
        geom_types = gdf.geometry.geom_type.fillna("")
        kinds = pd.Series("unknown", index=gdf.index, dtype="object")

        point_geom = geom_types.isin(["Point", "MultiPoint"])
        area_geom = geom_types.isin(["Polygon", "MultiPolygon"])
        kinds.loc[point_geom] = "point"
        kinds.loc[area_geom] = "area"

        if source_col is None:
            return kinds

        source_values = gdf[source_col].astype(str).str.upper().str.strip()
        kinds.loc[source_values.isin(self.point_labels)] = "point"
        kinds.loc[source_values.isin(self.area_labels)] = "area"
        return kinds

    def _resolve_lon_lat_columns(self, frame: pd.DataFrame) -> tuple[str, str]:
        if self.longitude_column and self.latitude_column:
            if self.longitude_column not in frame.columns or self.latitude_column not in frame.columns:
                raise ValueError(
                    "Configured longitude/latitude columns are missing from NEI table."
                )
            return self.longitude_column, self.latitude_column

        by_norm = {self._normalize_colname(c): c for c in frame.columns}
        lon_norms = [
            "longitude",
            "lon",
            "x",
            "longitudemeasure",
            "sitelongitude",
        ]
        lat_norms = [
            "latitude",
            "lat",
            "y",
            "latitudemeasure",
            "sitelatitude",
        ]

        lon_col = next((by_norm[n] for n in lon_norms if n in by_norm), None)
        lat_col = next((by_norm[n] for n in lat_norms if n in by_norm), None)
        if lon_col is None or lat_col is None:
            raise ValueError(
                "Could not infer lon/lat columns for NEI CSV. "
                "Set `longitude_column` and `latitude_column`."
            )
        return lon_col, lat_col

    def _read_zip_member_with_unzip(self, zip_path: Path, member_name: str) -> pd.DataFrame:
        """
        Read a zip member using the system `unzip -p` command.
        Fallback path for zip methods unsupported by Python's stdlib zipfile.
        """

        try:
            result = subprocess.run(
                ["unzip", "-p", str(zip_path), member_name],
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ValueError(
                "Python cannot read this zip compression and system `unzip` is not available. "
                f"Please manually extract: {zip_path}"
            ) from exc

        if result.returncode != 0 or not result.stdout:
            stderr = result.stderr.decode(errors="ignore").strip()
            raise ValueError(
                "Failed to extract NEI CSV from zip with system unzip. "
                f"zip={zip_path}, member={member_name}, stderr={stderr}"
            )

        return pd.read_csv(io.BytesIO(result.stdout), low_memory=False)

    def _metric_crs(self, gdf: gpd.GeoDataFrame) -> str:
        if gdf.crs is None:
            return "EPSG:3857"
        crs_obj = CRS.from_user_input(gdf.crs)
        return "EPSG:3857" if crs_obj.is_geographic else gdf.crs.to_string()

    def _normalize_colname(self, name: str) -> str:
        return "".join(ch for ch in str(name).lower() if ch.isalnum())
