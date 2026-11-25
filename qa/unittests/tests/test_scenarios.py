from pathlib import Path

import jsonschema
import pytest

from apex_algorithm_qa_tools.scenarios.common import (
    get_benchmark_scenarios,
    get_regression_scenarios,
    lint_benchmark_scenario,
    lint_regression_scenario,
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


@pytest.mark.parametrize(
    "scenario",
    [pytest.param(s, id=s.id) for s in get_regression_scenarios()],
)
def test_lint_regression_scenario(scenario: BenchmarkScenario):
    lint_regression_scenario(scenario)


def _scenario_with_extent(spatial_extent) -> openEOBenchmarkScenario:
    return openEOBenchmarkScenario(
        id="regression",
        type="openeo",
        backend="openeofed.dataspace.copernicus.eu",
        process_graph={
            "node": {
                "process_id": "foo",
                "arguments": {"spatial_extent": spatial_extent},
                "result": True,
            }
        },
    )


@pytest.mark.parametrize(
    "spatial_extent",
    [
        {"west": 0, "east": 20000, "south": 0, "north": 20000, "crs": "EPSG:32631"},
        {"west": 5.0, "east": 5.3, "south": 51.0, "north": 51.2},
    ],
)
def test_lint_regression_scenario_accepts_large_extent(spatial_extent):
    lint_regression_scenario(_scenario_with_extent(spatial_extent))


@pytest.mark.parametrize(
    "spatial_extent",
    [
        {"west": 0, "east": 19000, "south": 0, "north": 20000, "crs": "EPSG:32631"},
        # 0.3 degrees longitude is only ~16 km wide at 60N
        {"west": 5.0, "east": 5.3, "south": 60.0, "north": 60.2, "crs": "EPSG:4326"},
    ],
)
def test_lint_regression_scenario_rejects_small_extent(spatial_extent):
    with pytest.raises(AssertionError, match="20x20 km"):
        lint_regression_scenario(_scenario_with_extent(spatial_extent))


def test_lint_regression_scenario_requires_extent():
    with pytest.raises(AssertionError, match="spatial extent"):
        lint_regression_scenario(_scenario_with_extent(None))


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
