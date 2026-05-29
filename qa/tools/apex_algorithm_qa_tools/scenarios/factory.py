import json
from pathlib import Path
from typing import List

from apex_algorithm_qa_tools.scenarios.scenario import BenchmarkScenario
from apex_algorithm_qa_tools.scenarios.openeo import openEOBenchmarkScenario


def read_scenarios_file(path: str | Path) -> List[BenchmarkScenario]:
    """
    Load list of benchmark scenarios from a JSON file.
    """
    path = Path(path)
    with path.open("r", encoding="utf8") as f:
        data = json.load(f)
    # TODO: support single scenario files in addition to listings?
    assert isinstance(data, list)
    return [_benchmark_factory(item, path) for item in data]


def _benchmark_factory(item: dict, path: str | Path) -> BenchmarkScenario:
    # TODO #14 need for differentiation between different types of scenarios?
    assert item["type"] is not None, "Missing required 'type' field in benchmark scenario"
    if item["type"] == "openeo":
        return openEOBenchmarkScenario.from_dict(data=item, source=path)
    else:
        raise ValueError(f"Unsupported benchmark scenario type: {item['type']}")
