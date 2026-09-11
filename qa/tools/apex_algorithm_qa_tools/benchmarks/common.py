from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any
from typing import Union
from urllib.parse import urlparse

from apex_algorithm_qa_tools.pytest.pytest_track_metrics import MetricsTracker
from apex_algorithm_qa_tools.benchmarks.runners.base import BenchmarkJobMetadata, BenchmarkResults
import requests


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
    job_metadata: BenchmarkJobMetadata,
    track_metric: MetricsTracker,
):
    track_metric("costs", job_metadata.cost)
    for usage_metric in job_metadata.usage or []:
        if usage_metric.unit and usage_metric.value is not None:
            track_metric(f"usage:{usage_metric.name}:{usage_metric.unit}", usage_metric.value)


def collect_metrics_from_results_metadata(results_metadata: BenchmarkResults, track_metric: MetricsTracker):
    proj_shape_area_mpx = []
    proj_shape_area_km2 = []
    for asset_name, asset_data in results_metadata.assets.items():
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


def download_file(href: str, target: Path, user_token: str | None = None):
    parsed = urlparse(href)
    target.parent.mkdir(parents=True, exist_ok=True)

    if parsed.scheme in {"http", "https"}:
        headers = {"Authorization": f"Bearer {user_token}"} if user_token else None
        with requests.get(href, headers=headers, stream=True) as response:
            response.raise_for_status()
            with target.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=1024 * 64):
                    fh.write(chunk)
    else:
        raise ValueError(f"Unsupported URL scheme in href: {href!r}")
