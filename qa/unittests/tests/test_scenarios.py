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
