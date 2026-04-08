"""Land/water mask extraction methods using openEO."""

from __future__ import annotations
from functools import reduce
from operator import or_
from enum import Enum
from typing import Mapping, Optional
from dataclasses import dataclass
from openeo import collection_property

from openeo.rest.connection import Connection
from openeo.rest.datacube import DataCube
from openeo.processes import gt, lt


# region defaults

DEFAULT_S2_COLLECTION = "SENTINEL2_L2A"
DEFAULT_TARGET_EPSG: int = 3857
DEFAULT_MAX_CLOUD_COVER = 10

# endregion


# region types


class ThresholdMode(str, Enum):
    """Comparison direction used when applying a threshold to an index."""

    GT = "gt"
    LT = "lt"


@dataclass(frozen=True)
class ThresholdSpec:
    """Default threshold(s) and help text for UI/CLI usage."""

    defaults: Mapping[str, Optional[float]]  # keys are method-arg names, e.g. {"threshold": 0.1}
    mode: ThresholdMode
    description: str


# endregion


# region registries


WATERLAND_THRESHOLDS: dict[str, ThresholdSpec] = {
    "S2_NDWI": ThresholdSpec(
        defaults={"threshold": 0.01},
        mode=ThresholdMode.GT,
        description="NDWI threshold (water if NDWI > threshold).",
    ),
    "S2_MNDWI": ThresholdSpec(
        defaults={"threshold": 0.1},
        mode=ThresholdMode.GT,
        description="MNDWI threshold (water if MNDWI > threshold).",
    ),
    "S2_SCL": ThresholdSpec(
        defaults={},
        mode=ThresholdMode.GT,  # unused (no threshold), kept for consistency
        description="No threshold (SCL class 6 = water).",
    ),
    "S2_NDVI": ThresholdSpec(
        defaults={"threshold": 0.03},
        mode=ThresholdMode.LT,
        description="NDVI threshold (water if NDVI < threshold).",
    ),
    "S2_BNDVI": ThresholdSpec(
        defaults={"threshold": 0.03},
        mode=ThresholdMode.LT,
        description="BNDVI threshold (water if BNDVI < threshold).",
    ),
    "S2_GNDVI": ThresholdSpec(
        defaults={"threshold": 0.03},
        mode=ThresholdMode.LT,
        description="GNDVI threshold (water if GNDVI < threshold).",
    ),
}

# endregion


@dataclass(frozen=True)
class SpatialExtent:
    """Spatial extent."""

    west: float
    south: float
    east: float
    north: float

    def to_openeo(self) -> dict[str, float]:
        """Converts spatial extent to openeo format."""
        return {
            "west": self.west,
            "south": self.south,
            "east": self.east,
            "north": self.north,
        }


_NORMDIFF_S2: dict[str, tuple[str, str]] = {
    # index_name: (band_pos, band_neg) used in (pos - neg) / (pos + neg)
    "ndwi": ("B03", "B08"),
    "mndwi": ("B03", "B11"),
    "ndvi": ("B08", "B04"),
    "bndvi": ("B08", "B02"),
    "gndvi": ("B08", "B03"),
}


def load_collection(
    con: Connection,
    collection_id: str,
    bbox: SpatialExtent,
    time_range: list[str] | None,
    bands: list[str] | None = None,
    max_cloud_cover: float | None = None,
    target_epsg: int | None = None,
    resolution: float | tuple[float, float] | None = None,
    method: str = "near",
    grid_ids: list[str] | None = None,
) -> DataCube:
    """Generic openEO collection loader.

    max_cloud_cover is only applied to Sentinel-2 collections.

    Args:
        target_epsg: Reproject output to this EPSG code.
        resolution: Optional output resolution (single value or (x, y)).
        method: Resampling method for reprojection.
    """

    load_kwargs = {
        "collection_id": collection_id,
        "spatial_extent": bbox,
        "temporal_extent": time_range,
        "bands": bands,
    }

    properties = []
    if grid_ids:
        grid_prop = collection_property("grid:code")
        grid_filter = reduce(or_, [(grid_prop == gid) for gid in grid_ids])
        properties.append(grid_filter)

    if properties:
        load_kwargs["properties"] = properties

    # Apply cloud cover filter only for Sentinel-2
    if "SENTINEL2" in collection_id.upper() and max_cloud_cover is not None:
        load_kwargs["max_cloud_cover"] = max_cloud_cover

    cube = con.load_collection(**load_kwargs)

    # Optional reprojection
    if target_epsg is not None:
        reproj_kwargs = {"projection": target_epsg, "method": method}
        if resolution is not None:
            reproj_kwargs["resolution"] = resolution

        cube = cube.process("resample_spatial", data=cube, **reproj_kwargs)

    return cube


def s2_clear_mask_from_scl(cube: DataCube) -> DataCube:
    """Create a boolean clear-pixel mask from the Sentinel-2 SCL band."""
    scl = cube.band("SCL")
    # SCL codes: 3 - cloud shadows, 8 - cloud medium prob, 9 - cloud high prob
    return (scl == 3 - 1000) | (scl == 8 - 1000) | (scl == 9 - 1000)


def load_s2(
    con: Connection,
    collection_id: str,
    bbox: SpatialExtent,
    time_range: list[str],
    bands: list[str],
    max_cloud_coverage: float | None = DEFAULT_MAX_CLOUD_COVER,
    target_epsg: int | None = DEFAULT_TARGET_EPSG,
    grid_ids: list[str] | None = None,
) -> tuple[DataCube, DataCube]:
    """Load Sentinel-2 with SCL-based cloud masking before optional temporal reduction."""
    bands_with_scl = list(dict.fromkeys(bands + ["SCL"]))  # keep order, unique

    # Load S2 bands + SCL
    cube = load_collection(
        con,
        collection_id,
        bbox,
        time_range,
        bands_with_scl,
        max_cloud_cover=max_cloud_coverage,
        target_epsg=target_epsg,
        grid_ids=grid_ids,
    )

    # Cloud masking
    clear = s2_clear_mask_from_scl(cube)
    cube = cube.mask(clear)

    # Remove SCL band
    cube = cube.filter_bands(bands)

    return cube, clear


# region private (processing helpers)


def _bin(cube: DataCube) -> DataCube:
    """Convert a boolean condition cube to a 0/1 cube using an openEO `if` process."""
    return cube.apply(lambda x: x.process("if", arguments={"value": x, "accept": 1, "reject": 0}))


# endregion


# region public
def s2_scl(
    con: Connection,
    collection_id: str,
    bbox: SpatialExtent,
    time_range: list[str],
    max_cloud_coverage: float,
) -> tuple[DataCube, DataCube]:
    """Load Sentinel-2 SCL and return a boolean mask selecting SCL class 6.

    Args:
        con: openEO connection object.
        collection_id: Sentinel-2 collection identifier to load.
        bbox: Spatial extent (bounding box) to load.
        time_range: Temporal extent as `[start, end]`.

    Returns:
        Sentinel-2 cube and
        Boolean cube where pixels equal to SCL class 6 are True.
    """
    s2_cube, _ = load_s2(con, collection_id, bbox, time_range, bands=["SCL"], max_cloud_coverage=max_cloud_coverage)
    scl_water_mask = s2_cube.band("SCL") == 6
    return s2_cube, scl_water_mask


def s2_index_mask(
    con: Connection,
    collection_id: str,
    bbox: SpatialExtent,
    time_range: list[str],
    index_name: str,
    threshold: float | None,
    mode: str = "gt",
    max_cloud_coverage: float | None = None,
    grid_ids: list[str] | None = None,
) -> tuple[DataCube, DataCube]:
    """Compute a supported Sentinel-2 norm-diff index and return a binary mask using a threshold.

    Args:
        con: openEO connection object.
        collection_id: Sentinel-2 collection identifier to load.
        bbox: Spatial extent (bounding box) to load.
        time_range: Temporal extent as `[start, end]`.
        index_name: Name of the index to compute. Supported values: `ndwi`, `mndwi`,
            `ndvi`, `bndvi`, `gndvi`.
        threshold: Threshold applied to the index.
        mode: Threshold mode:
            - `"gt"`: pixels where index > threshold become 1
            - `"lt"`: pixels where index < threshold become 1
        max_cloud_coverage: Max allowed cloud coverage.
        grid_ids: Filter collection output to these grid IDs.

    Returns:
        Sentinel-2 cube and
        0/1 cube representing the index threshold mask. The land pixels
        are labelled with 0 and the water pixels are labelled with 1.

    Raises:
        ValueError: If `index_name` is not supported or `mode` is not `gt`/`lt`.
    """
    key = index_name.lower().split("_")[1]
    if key not in _NORMDIFF_S2:
        raise ValueError(f"Unsupported index_name={index_name!r}. Supported: {sorted(_NORMDIFF_S2)}")

    band_pos, band_neg = _NORMDIFF_S2[key]
    s2_cube, clear = load_s2(
        con,
        collection_id,
        bbox,
        time_range,
        [band_pos, band_neg],
        max_cloud_coverage,
        grid_ids=grid_ids,
    )

    pos = s2_cube.band(band_pos)
    neg = s2_cube.band(band_neg)

    idx = (pos - neg) / (pos + neg)
    idx = idx.mask(clear)

    if mode == "gt":
        mask = gt(idx, threshold)
    elif mode == "lt":
        mask = lt(idx, threshold)
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    return s2_cube, _bin(mask)


# endregion
