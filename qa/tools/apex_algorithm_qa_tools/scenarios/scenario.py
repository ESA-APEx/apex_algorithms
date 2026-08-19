from __future__ import annotations

from abc import ABC
import dataclasses
import json
from pathlib import Path
from typing import List


from apex_algorithm_qa_tools.common import (
    get_project_root,
)


# TODO #15 Flatten apex_algorithm_qa_tools to a single module and push as much functionality to https://github.com/ESA-APEx/esa-apex-toolbox-python
def get_benchmark_scenario_schema() -> dict:
    with open(get_project_root() / "schemas/benchmark_scenario.json") as f:
        return json.load(f)



@dataclasses.dataclass(kw_only=True)
class BenchmarkScenario(ABC):
    id: str
    type: str
    description: str | None = None
    reference_data: dict = dataclasses.field(default_factory=dict)
    reference_options: dict = dataclasses.field(default_factory=dict)
    source: str | Path | None = None

    @classmethod
    def from_dict(cls, data: dict, source: str | Path | None = None) -> BenchmarkScenario:
        pass