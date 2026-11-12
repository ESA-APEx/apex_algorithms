from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "options, passed, deselected",
    [
        ([], 3, 0),
        (["--override-backend=https://override.example"], 3, 0),
        (["--backend-filter=https://original.example"], 1, 2),
        (
            [
                "--backend-filter=https://original.example",
                "--override-backend=https://override.example",
            ],
            1,
            2,
        ),
        (["--backend-filter=https://missing.example"], 0, 3),
        (["--backend-filter=https://original.example", "--random-subset=1"], 1, 2),
        (["--backend-filter=https://.*example", "--random-subset=1"], 1, 2),
    ],
)
def test_backend_filter_scenarios(pytester, options, passed, deselected):
    benchmark_conftest = Path(__file__).parents[3] / "benchmarks/tests/conftest.py"
    pytester.makeconftest(benchmark_conftest.read_text())
    pytester.makepyfile(
        test_benchmarks="""
        from types import SimpleNamespace
        import pytest

        @pytest.mark.parametrize("scenario", [
            SimpleNamespace(id="matching", backend="https://original.example"),
            SimpleNamespace(id="other", backend="https://other.example"),
            SimpleNamespace(id="ogc", endpoint="https://ogc.example"),
        ])
        def test_benchmark(scenario):
            assert scenario.id != "ogc" or not FILTER_ACTIVE
        """.replace("FILTER_ACTIVE", repr(any(option.startswith("--backend-filter=") for option in options)))
    )
    result = pytester.runpytest_subprocess(*options)
    result.assert_outcomes(passed=passed, deselected=deselected)
