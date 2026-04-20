from typing import Iterable, Union, Any
import numpy as np
import geopandas as gpd
from shapely.geometry import (
    box,
    LineString,
    MultiLineString,
    Polygon,
    Point,
    GeometryCollection,
)
from openeo.udf import inspect
from openeo.udf.feature_collection import FeatureCollection
from openeo.udf.udf_data import UdfData

GeometryLike = Union[LineString, MultiLineString, GeometryCollection]

DEFAULT_OUT_LAYER = "waterline"
DEFAULT_TIME_DIM = "time"
DEFAULT_VAR_NAME = "var"
DEFAULT_SEA_DIRECTION_8_COLUMN = "sea_direction_8"
DEFAULT_SEA_AZIMUTH_DEG_COLUMN = "sea_azimuth_deg"
DEFAULT_MIN_DANGLING_LENGTH = 10000
DEFAULT_MIN_HOLE_AREA = 1000000


def _iter_lines(geom: GeometryLike) -> Iterable[LineString]:
    """Recursively yield all LineString objects contained in a geometry."""
    if geom.is_empty:
        return

    if isinstance(geom, LineString):
        yield geom
    elif isinstance(geom, (MultiLineString, GeometryCollection)):
        for subgeom in geom.geoms:
            yield from _iter_lines(subgeom)


def split_into_segments(geom: GeometryLike) -> list[LineString]:
    """
    Split a geometry into 2-point LineStrings representing individual segments
    between consecutive vertices.

    Args:
        geom: Input geometry.

    Returns: List of non-zero-length segments.
    """
    segments: list[LineString] = []

    for line in _iter_lines(geom):
        coords = list(line.coords)
        for start, end in zip(coords[:-1], coords[1:]):
            if start != end:  # Avoid zero-length segments
                segments.append(LineString([start, end]))

    return segments


def _remove_small_interiors(geom: Polygon, min_hole_area: float = DEFAULT_MIN_HOLE_AREA) -> Polygon:
    """Remove small interior rings from polygon."""
    if geom.is_empty:
        return geom

    kept_holes = []
    for ring in geom.interiors:
        if Polygon(ring).area >= min_hole_area:
            kept_holes.append(ring)

    return Polygon(geom.exterior, holes=kept_holes)


def _remove_extent_intersections(waterline: LineString, bounds, buffer: float = 500) -> list[LineString]:
    """Return 2-point segments that do NOT intersect the raster extent boundary."""
    extent_edge = box(*bounds).boundary
    edges = split_into_segments(waterline)
    extent_edge_buffered = extent_edge.buffer(buffer)
    return [e for e in edges if not e.within(extent_edge_buffered)]


def _remove_short_dangling_segments(
    segments: list[LineString],
    min_dangling_length: float = 0.0,
) -> list[LineString]:
    """Remove short isolated segments (both endpoints occur only once)."""
    if not segments or min_dangling_length <= 0:
        return segments

    endpoint_counts: dict[Any, int] = {}
    for seg in segments:
        a, b = seg.coords[0], seg.coords[-1]
        endpoint_counts[a] = endpoint_counts.get(a, 0) + 1
        endpoint_counts[b] = endpoint_counts.get(b, 0) + 1

    kept: list[LineString] = []
    for seg in segments:
        if seg.length >= min_dangling_length:
            kept.append(seg)
            continue

        a, b = seg.coords[0], seg.coords[-1]
        if endpoint_counts.get(a, 0) > 1 or endpoint_counts.get(b, 0) > 1:
            kept.append(seg)

    return kept


def _clean_waterline_segments(
    waterline: LineString,
    bounds,
    min_dangling_length: float = DEFAULT_MIN_DANGLING_LENGTH,
) -> list[LineString]:
    """
    Clean waterline and return as a *list of 2-point segments* (one per edge).
    """
    segments = _remove_extent_intersections(waterline, bounds)
    if not segments:
        return []

    segments = _remove_short_dangling_segments(
        segments,
        min_dangling_length=min_dangling_length,
    )
    if not segments:
        return []

    return segments


def _get_sea_direction_for_segment(water_poly: Polygon, seg: LineString) -> tuple[str, float | None]:
    """
    Determine where the sea (water polygon side) lies relative to a segment.

    Returns:
        sea_dir: General sea direction (N, S, NS etc) and detailed sea dir in degrees.
    """
    if seg.is_empty or seg.length == 0:
        return "unknown", None

    # Get first and last coordinates of the segment
    a = np.asarray(seg.coords[0], dtype=float)
    b = np.asarray(seg.coords[-1], dtype=float)

    # Compute direction vector and length
    v = b - a
    norm = np.linalg.norm(v)
    if norm == 0:
        return "unknown", None

    # Unit tangent and left normal vector
    t = v / norm
    n_left = np.array([-t[1], t[0]], dtype=float)

    # Segment midpoint
    mid = (a + b) / 2.0

    # How far to step away from the segment (1 perc of segment len.)
    eps = max(0.5, min(5.0, float(seg.length) * 0.01))

    # Probe points
    left_pt = mid + eps * n_left
    right_pt = mid - eps * n_left

    left_in = water_poly.contains(Point(left_pt))
    right_in = water_poly.contains(Point(right_pt))

    if left_in and not right_in:
        sea_vec = n_left
    elif right_in and not left_in:
        sea_vec = -n_left
    else:
        return "unknown", None

    # Map-based 8-way direction from sea_vec (x=east, y=north)
    x, y = float(sea_vec[0]), float(sea_vec[1])

    # Compute angle
    angle = np.degrees(np.arctan2(y, x))
    angle = (angle + 360.0) % 360.0

    # 8-sector compass, centered on E=0°, NE=45°, N=90°, ...
    dirs = ["E", "NE", "N", "NW", "W", "SW", "S", "SE"]
    idx = int(((angle + 22.5) % 360) // 45)

    return dirs[idx], float(angle)


def _segments_for_water_mask(
    gdf_water_one_timestamp,
    bounds,
    simplify_tolerance: float | None = None,
) -> tuple[list[LineString], Polygon] | None:
    """Converts water land mask for single timestamp to cleaned waterline segments."""

    # Remove small interiors
    gdf_water_one_timestamp["geometry"] = gdf_water_one_timestamp["geometry"].apply(_remove_small_interiors)

    # Remove small polygons
    gdf_water_one_timestamp = gdf_water_one_timestamp[gdf_water_one_timestamp["geometry"].area > DEFAULT_MIN_HOLE_AREA]

    # Merge all polygons
    water_poly = gdf_water_one_timestamp.union_all()

    if simplify_tolerance is not None:
        water_poly = water_poly.simplify(simplify_tolerance, preserve_topology=True)

    boundary = water_poly.boundary

    # boundary can be MultiLineString/LineString -> convert to a single multilinestring-ish
    if isinstance(boundary, LineString):
        cleaned_segments = _clean_waterline_segments(boundary, bounds=bounds)
    elif isinstance(boundary, MultiLineString):
        cleaned_segments = []
        for part in boundary.geoms:
            cleaned_segments.extend(_clean_waterline_segments(part, bounds=bounds))
    else:
        return None

    return cleaned_segments, water_poly


def waterline_from_vectorized_water_raster(
    gdf: gpd.GeoDataFrame,
    simplify_tolerance: float | None = None,
) -> gpd.GeoDataFrame:
    """
    Generate waterline segments for each time step from a vectorized land/water mask.
    The input gdf is the output of openEO raster_to_vector() process.
    Args:
        gdf: GeoDataFrame containing polygon geometries and one non-geometry column
            per timestamp. For each timestamp column, values indicate whether a
            polygon belongs to water or land at that time:
            - null: polygon not present for that timestamp
            - 0: land polygon
            - non-zero: water polygon
        simplify_tolerance: Optional tolerance for geometry simplification. If
            provided, merged water geometries are simplified before extracting
            boundary segments.

    Returns:
        A GeoDataFrame with columns:
            - time: Time step associated with each geometry.
            - type: Feature classification.
            - sea_direction_8: Direction toward the sea expressed as one of
              eight cardinal/inter-cardinal directions (N, NE, E, SE, S, SW, W, NW).
            - sea_azimuth_deg: Direction toward the sea in degrees (azimuth,
              typically measured clockwise from north).
            - geometry: Waterline geometry (LineString or MultiLineString).
    Raises:
        ValueError if no waterlines segments extracted.
    """

    records: list[dict[str, Any]] = []

    # Get time dimensions
    time_stamps = gdf.loc[:, gdf.columns != "geometry"].columns.to_list()
    inspect(data=[time_stamps], message="Input time stamps.")
    bounds = gdf.total_bounds
    for time_stamp in time_stamps:
        one_time_stamp_gdf = gdf[[time_stamp, "geometry"]].dropna(subset=[time_stamp])
        one_time_stamp_gdf_water_only = one_time_stamp_gdf[one_time_stamp_gdf[time_stamp] != 0]
        inspect(data=[time_stamp], message="Extracting waterlines for timestamp")
        res = _segments_for_water_mask(
            one_time_stamp_gdf_water_only,
            bounds=bounds,
            simplify_tolerance=simplify_tolerance,
        )
        if res is None:
            continue

        segments, water_poly = res
        inspect(data=[time_stamp], message="Calculating sea direction for timestamp")
        for seg in segments:
            sea_direction = _get_sea_direction_for_segment(water_poly, seg)
            records.append(
                {
                    "time": time_stamp,
                    "type": "waterline_segment",
                    DEFAULT_SEA_DIRECTION_8_COLUMN: sea_direction[0],
                    DEFAULT_SEA_AZIMUTH_DEG_COLUMN: sea_direction[1],
                    "geometry": seg,
                }
            )
    if len(records) == 0:
        raise ValueError(
            "No waterline segments found within the specified area of interest. Check that the area overlaps with known water bodies and that the input data is valid."
        )
    inspect(data=[records], message="Converting records to geodataframe")
    gdf = gpd.GeoDataFrame(records, geometry="geometry", crs=gdf.crs)
    gdf = gdf[~gdf.geometry.isna() & ~gdf.geometry.is_empty].reset_index(drop=True)
    return gdf


def apply_udf_data(udf_data: UdfData) -> UdfData:

    feature_collection = udf_data.get_feature_collection_list()
    gdf = feature_collection.data
    inspect(data=[gdf], message="Input gdf data inspection")

    gdf = waterline_from_vectorized_water_raster(
        gdf=gdf,
        simplify_tolerance=15,
    )

    inspect(data=[gdf], message="Output gdf data inspection")

    udf_data.set_feature_collection_list([
        FeatureCollection(id="_", data=gdf)
    ])

    return udf_data
