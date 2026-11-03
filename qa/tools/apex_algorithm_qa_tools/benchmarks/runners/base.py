from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from apex_algorithm_qa_tools.scenarios import (
    BenchmarkScenario,
    download_reference_data,
)


@dataclasses.dataclass
class BenchmarkResults:
    assets: dict


@dataclasses.dataclass
class BenchmarkMetric:
    name: str
    value: Any
    unit: str | None = None


@dataclasses.dataclass
class BenchmarkJobMetadata:
    cost: float | None
    usage: list[BenchmarkMetric] | None


@dataclasses.dataclass
class BenchmarkRunnerArtifacts:
    job_id: str | None
    job_metadata: BenchmarkJobMetadata
    results_metadata: BenchmarkResults


class BenchmarkRunner(ABC):
    def __init__(self, *, scenario: BenchmarkScenario, request):
        self.scenario = scenario
        self.request = request
        self.origin = f"apex-algorithms/benchmarks/{request.session.name}/{request.node.name}"

    @abstractmethod
    def create_job(self):
        pass

    @abstractmethod
    def run_job(self, *, max_minutes: int | None):
        pass

    @abstractmethod
    def collect_artifacts(self) -> BenchmarkRunnerArtifacts:
        pass

    @abstractmethod
    def download_actual(self, *, actual_dir: Path) -> list[Path]:
        pass

    def download_reference(self, scenario: BenchmarkScenario, reference_dir: Path) -> Path:
        return download_reference_data(scenario, reference_dir)

    def can_check_job_results_validity(self) -> bool:
        return False

    def assert_job_results_validity(self, reference_dir: Path, actual_dir: Path):
        raise NotImplementedError("This runner does not support custom result validation.")
