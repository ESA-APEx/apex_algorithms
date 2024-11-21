import jsonschema
import pytest
from apex_algorithm_qa_tools.scenarios import (
    BenchmarkScenario,
    get_benchmark_scenarios,
    lint_benchmark_scenario,
)


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


class TestBenchmarkScenario:
    def test_init_minimal(self):
        bs = BenchmarkScenario(
            id="foo",
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

    def test_validation_minimal(self):
        bs = BenchmarkScenario.from_dict(
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
            BenchmarkScenario.from_dict({})
