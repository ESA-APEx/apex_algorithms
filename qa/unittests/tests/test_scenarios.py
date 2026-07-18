from pathlib import Path

import jsonschema
import pytest

from apex_algorithm_qa_tools.scenarios.common import get_benchmark_scenarios, lint_benchmark_scenario
from apex_algorithm_qa_tools.scenarios.factory import _benchmark_factory
from apex_algorithm_qa_tools.scenarios.scenario import BenchmarkScenario
from apex_algorithm_qa_tools.scenarios.openeo import openEOBenchmarkScenario

def test_get_benchmark_scenarios():
    scenarios = get_benchmark_scenarios()
    assert len(scenarios) > 0


# TODO: tests to check uniqueness of scenario ids?


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
