from pathlib import Path
import json
import re
import subprocess
import sys

import jsonschema
import pytest

from apex_algorithm_qa_tools.common import get_project_root
from apex_algorithm_qa_tools.scenarios.common import (
    get_benchmark_scenarios,
    get_regression_scenarios,
    lint_benchmark_scenario,
    select_regression_scenario_ids,
)
from apex_algorithm_qa_tools.scenarios.factory import _benchmark_factory
from apex_algorithm_qa_tools.scenarios.scenario import BenchmarkScenario
from apex_algorithm_qa_tools.scenarios.openeo import openEOBenchmarkScenario

def test_get_benchmark_scenarios():
    scenarios = get_benchmark_scenarios()
    assert len(scenarios) > 0


# TODO: tests to check uniqueness of scenario ids?


def test_regression_flag():
    data = {"id": "r", "type": "openeo", "backend": "openeo.test", "process_graph": {}}
    assert openEOBenchmarkScenario.from_dict(data).regression is False
    assert openEOBenchmarkScenario.from_dict({**data, "regression": True}).regression is True
    with pytest.raises(jsonschema.ValidationError):
        openEOBenchmarkScenario.from_dict({**data, "regression": "yes"})


@pytest.fixture
def catalog_root(tmp_path) -> Path:
    """Fake catalog with 6 regression scenarios and 1 regular benchmark scenario."""
    ids = [f"algo{i}_large" for i in range(6)] + ["algo_regular"]
    scenarios = [
        {
            "id": id,
            "type": "openeo",
            "backend": "openeo.test",
            "process_graph": {},
            "regression": id != "algo_regular",
        }
        for id in ids
    ]
    path = tmp_path / "algorithm_catalog" / "org" / "algo" / "benchmark_scenarios" / "scenarios.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(scenarios))
    return tmp_path


def test_select_regression_scenario_ids_limits_to_random_regression_subset(catalog_root):
    regression_ids = {f"algo{i}_large" for i in range(6)}
    selections = [select_regression_scenario_ids(catalog_root, max_scenarios=4) for _ in range(20)]

    for selected in selections:
        assert len(selected) == len(set(selected)) == 4
        assert set(selected) <= regression_ids
    # Random: not always the same subset
    assert len({frozenset(s) for s in selections}) > 1


def test_select_regression_scenario_ids_returns_all_when_fewer_than_limit(catalog_root):
    selected = select_regression_scenario_ids(catalog_root, max_scenarios=10)
    assert sorted(selected) == [f"algo{i}_large" for i in range(6)]


@pytest.mark.parametrize(
    ["scenario", "expected"],
    [
        ("algo3_large", ["algo3_large"]),
        ("algo_regular", []),
        ("unknown", []),
    ],
)
def test_select_regression_scenario_ids_explicit_scenario(catalog_root, scenario, expected):
    assert select_regression_scenario_ids(catalog_root, scenario=scenario, max_scenarios=1) == expected


def _collect_benchmarks(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *args],
        cwd=get_project_root() / "qa" / "benchmarks",
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _collected_benchmarks(*args) -> set[tuple[str, str]]:
    """(test function, scenario id) pairs collected by the benchmark suite."""
    result = _collect_benchmarks(*args)
    assert result.returncode == 0, result.stdout + result.stderr
    return set(re.findall(r"(test_run_\w+)\[([^\]]+)\]", result.stdout))


def test_benchmark_runs_never_collect_regression_scenarios():
    regression_ids = {s.id for s in get_regression_scenarios()}
    regular = _collected_benchmarks()
    regression = _collected_benchmarks("-m", "regression")

    assert regular and regression
    assert {test for test, _ in regular} == {"test_run_benchmark"}
    assert not {scenario_id for _, scenario_id in regular} & regression_ids
    assert regression == {("test_run_regression", scenario_id) for scenario_id in regression_ids}


def test_regression_scenario_node_id_only_runs_with_regression_marker():
    # Workflows select a single scenario by node id (e.g. benchmark-pr-check.yml).
    scenario_id = get_regression_scenarios()[0].id
    node_id = f"tests/test_benchmarks.py::test_run_regression[{scenario_id}]"

    assert _collect_benchmarks(node_id).returncode == pytest.ExitCode.NO_TESTS_COLLECTED
    assert _collected_benchmarks(node_id, "-m", "regression") == {("test_run_regression", scenario_id)}


@pytest.mark.parametrize(
    "scenario",
    [
        # Use scenario id as parameterization id to give nicer test names.
        pytest.param(uc, id=uc.id)
        for uc in get_benchmark_scenarios()
    ],
)
def test_lint_scenario(scenario: BenchmarkScenario):
    lint_benchmark_scenario(scenario)

    assert isinstance(scenario.source, Path) and scenario.source.exists()


class TestOpenEOBenchmarkScenario:
    def test_openeo_init_minimal(self):
        bs = openEOBenchmarkScenario(
            id="foo",
            type="openeo",
            backend="openeo.test",
            process_graph={},
        )
        assert bs.id == "foo"
        assert bs.description is None
        assert bs.backend == "openeo.test"
        assert bs.process_graph == {}
        assert bs.job_options is None
        assert bs.reference_data == {}
        assert bs.reference_options == {}

    def test_openeo_validation_minimal(self):
        bs = openEOBenchmarkScenario.from_dict(
            {
                "id": "foo",
                "type": "openeo",
                "backend": "openeo.test",
                "process_graph": {},
            }
        )
        assert bs.id == "foo"
        assert bs.description is None
        assert bs.backend == "openeo.test"
        assert bs.process_graph == {}
        assert bs.job_options is None
        assert bs.reference_data == {}
        assert bs.reference_options == {}

    def test_validation_missing_essentials(self):
        with pytest.raises(jsonschema.ValidationError):
            openEOBenchmarkScenario.from_dict({})


class TestBenchmarkFactory:
    def test_openeo_factory(self):
        path = Path("dummy_scenarios.json")
        scenario = _benchmark_factory(
            item={
                "id": "foo",
                "type": "openeo",
                "backend": "openeo.test",
                "process_graph": {},
            },
            path=path,
        )

        assert isinstance(scenario, openEOBenchmarkScenario)
        assert scenario.id == "foo"
        assert scenario.type == "openeo"
        assert scenario.source == path

    def test_factory_missing_type(self):
        with pytest.raises(
            AssertionError,
            match="Missing required 'type' field in benchmark scenario",
        ):
            _benchmark_factory(item={"type": None}, path=Path("dummy.json"))

    def test_factory_unsupported_type(self):
        with pytest.raises(
            ValueError,
            match="Unsupported benchmark scenario type: ogcapi-processes",
        ):
            _benchmark_factory(
                item={"type": "ogcapi-processes"},
                path=Path("dummy.json"),
            )
