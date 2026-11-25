from __future__ import annotations

import glob
import json
import logging
import math
import re
from pathlib import Path
from typing import List

import requests
import time
from apex_algorithm_qa_tools.common import (
    get_project_root,
)
from openeo.util import TimingLogger

from apex_algorithm_qa_tools.scenarios.openeo import lint_openeo_fields
from apex_algorithm_qa_tools.scenarios.ogc import OGCAPIBenchmarkScenario
from apex_algorithm_qa_tools.scenarios.scenario import BenchmarkScenario
from apex_algorithm_qa_tools.scenarios.factory import read_scenarios_file

_log = logging.getLogger(__name__)


def get_benchmark_scenarios(root=None) -> List[BenchmarkScenario]:
    # TODO: instead of flat list, keep original grouping/structure of benchmark scenario files?
    # TODO: check for uniqueness of scenario IDs? Also make this a pre-commit lint tool?
    scenarios = []
    # old style glob is used to support symlinks
    for path in glob.glob(
        str((root or get_project_root()) / "algorithm_catalog") + "/**/*benchmark_scenarios*/*.json",
        recursive=True,
    ):
        scenarios.extend(read_scenarios_file(path))
    return scenarios


REGRESSION_MIN_SIDE_KM = 20


def get_regression_whitelist(root=None) -> List[str]:
    """Scenario ids of regression scenarios that are enabled for (scheduled) runs."""
    path = (root or get_project_root()) / "qa" / "benchmarks" / "regression_whitelist.json"
    return json.loads(path.read_text(encoding="utf-8"))["scenarios"]


def get_regression_scenarios(root=None) -> List[BenchmarkScenario]:
    """Whitelisted scenarios from `algorithm_catalog/**/regression_scenarios/*.json`."""
    whitelist = set(get_regression_whitelist(root))
    scenarios = []
    # old style glob is used to support symlinks
    for path in glob.glob(
        str((root or get_project_root()) / "algorithm_catalog") + "/**/*regression_scenarios*/*.json",
        recursive=True,
    ):
        scenarios.extend(s for s in read_scenarios_file(path) if s.id in whitelist)
    return scenarios


def _find_bboxes(data):
    if isinstance(data, dict):
        if {"west", "east", "south", "north"} <= data.keys():
            yield data
        else:
            for value in data.values():
                yield from _find_bboxes(value)
    elif isinstance(data, list):
        for value in data:
            yield from _find_bboxes(value)


def _bbox_size_km(bbox: dict) -> tuple[float, float]:
    """Approximate (width, height) in km. Non-4326 CRSs are assumed to be in metres."""
    width = bbox["east"] - bbox["west"]
    height = bbox["north"] - bbox["south"]
    if str(bbox.get("crs", 4326)).upper() in {"4326", "EPSG:4326"}:
        mid_lat = math.radians((bbox["north"] + bbox["south"]) / 2)
        return width * 111.32 * math.cos(mid_lat), height * 110.57
    return width / 1000, height / 1000


def lint_regression_scenario(scenario: BenchmarkScenario):
    """Benchmark lint plus a minimum spatial extent of 20x20 km."""
    lint_benchmark_scenario(scenario)

    data = getattr(scenario, "process_graph", None) or getattr(scenario, "parameters", None)
    bboxes = list(_find_bboxes(data))
    assert bboxes, f"[{scenario.id}] no spatial extent (west/east/south/north) found"
    for bbox in bboxes:
        width, height = _bbox_size_km(bbox)
        assert min(width, height) >= REGRESSION_MIN_SIDE_KM, (
            f"[{scenario.id}] spatial extent {width:.1f}x{height:.1f} km is smaller than "
            f"{REGRESSION_MIN_SIDE_KM}x{REGRESSION_MIN_SIDE_KM} km"
        )


def lint_common_fields(scenario: BenchmarkScenario):
    """
    Various sanity checks for scenario data.
    To be used in unit tests and pre-commit hooks.
    """
    assert re.match(r"^[a-zA-Z0-9_-]+$", scenario.id)


def lint_benchmark_scenario(scenario: BenchmarkScenario):
    """
    Various sanity checks for scenario data.
    To be used in unit tests and pre-commit hooks.
    """
    lint_common_fields(scenario=scenario)

    if scenario.type == "openeo":
        lint_openeo_fields(scenario=scenario)
    elif scenario.type == "ogc_api_process":
        lint_ogc_fields(scenario=scenario)
    else:
        raise ValueError(f"Unsupported benchmark scenario type: {scenario.type!r}")


def lint_ogc_fields(scenario: OGCAPIBenchmarkScenario):
    assert scenario.endpoint.startswith(("http://", "https://")), (
        f"Unsupported OGC endpoint: {scenario.endpoint!r}"
    )
    assert scenario.application
    assert isinstance(scenario.parameters, dict)


def download_reference_data(scenario: BenchmarkScenario, reference_dir: Path, headers: dict=None) -> Path:
    with TimingLogger(
        title=f"Downloading reference data for {scenario.id=} to {reference_dir=}",
        logger=_log.info,
    ):
        for path, source in scenario.reference_data.items():
            path = reference_dir / path
            if not path.is_relative_to(reference_dir):
                raise ValueError(f"Resolved {path=} is not relative to {reference_dir=} ({scenario.id=})")
            path.parent.mkdir(parents=True, exist_ok=True)

            with TimingLogger(title=f"Downloading {source=} to {path=}", logger=_log.info):
                # Handle file:// URLs (local files)
                if source.startswith("file://"):
                    file_path = source[7:]  # Remove "file://" prefix
                    with open(file_path, "rb") as src_file:
                        with path.open("wb") as f:
                            f.write(src_file.read())
                else:
                    # Handle HTTP(S) URLs
                    retries = 3
                    while retries > 0:
                        retries -= 1
                        try:
                            response = requests.get(source, headers=headers, stream=True)
                            response.raise_for_status()
                            with path.open("wb") as f:
                                for chunk in response.iter_content(chunk_size=128):
                                    f.write(chunk)
                            break
                        except:
                            if response.status_code in [501, 502, 503, 504]:
                                time.sleep(10)
                            else:
                                _log.error("Error downloading reference data")
                                response.raise_for_status()
                            

    return reference_dir
