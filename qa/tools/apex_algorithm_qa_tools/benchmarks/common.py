from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import Any
from typing import Union

from apex_algorithm_qa_tools.pytest.pytest_track_metrics import MetricsTracker

_log = logging.getLogger(__name__)

@dataclasses.dataclass
class BenchmarkExecutionArtifacts:
    """Backend-agnostic benchmark execution artifacts."""

    job_id: str | None
    job_metadata: dict | Any
    results_metadata: dict | Any
    paths: list[Path]


def ensure_safe_relative_target(base_dir: Path, relative_path: str) -> Path:
    """Resolve a relative path under base_dir and reject path traversal."""

    root = base_dir.resolve()
    target = (base_dir / relative_path).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"Unsafe result path: {relative_path!r}")
    return target


def to_jsonable(value: Any) -> Any:
    """Convert pydantic/generated client values to plain JSON-serializable data."""

    if hasattr(value, "actual_instance"):
        value = value.actual_instance
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


def collect_metrics_from_job_metadata(
    job_metadata: dict,
    track_metric: MetricsTracker,
):
    track_metric("costs", job_metadata.get("costs"))
    for usage_metric, usage_data in job_metadata.get("usage", {}).items():
        if "unit" in usage_data and "value" in usage_data:
            track_metric(
                f"usage:{usage_metric}:{usage_data['unit']}", usage_data["value"]
            )


def collect_metrics_from_results_metadata(
    results_metadata: dict, 
    track_metric: MetricsTracker
):
    proj_shape_area_mpx = []
    proj_shape_area_km2 = []
    for asset_name, asset_data in results_metadata.get("assets", {}).items():
        if "proj:shape" in asset_data:
            y, x = asset_data["proj:shape"][:2]
            proj_shape_area_mpx.append(y * x / 1e6)

            if "proj:epsg" in asset_data and "proj:bbox" in asset_data:
                epsg_code = int(asset_data["proj:epsg"])
                if (32601 <= epsg_code < 32660) or (32701 <= epsg_code < 32760):
                    # UTM zone: bbox coordinates are in meter -> calculate area in km2
                    w, s, e, n = asset_data["proj:bbox"][:4]
                    proj_shape_area_km2.append((n - s) * (e - w) / 1e6)

    # When there are multiple results, just report maximum for now
    if proj_shape_area_mpx:
        track_metric("results:proj:shape:area:megapixel", max(proj_shape_area_mpx))
    if proj_shape_area_km2:
        track_metric("results:proj:bbox:area:utm:km2", max(proj_shape_area_km2))


def analyse_results_comparison_exception(exc: Exception) -> Union[str, None]:
    if isinstance(exc, AssertionError):
        if "Differing 'derived_from' links" in str(exc):
            return "derived_from-change"