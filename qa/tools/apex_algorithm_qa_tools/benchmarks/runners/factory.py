

from apex_algorithm_qa_tools.benchmarks.runners.openeo import OpenEOBenchmarkRunner


def create_benchmark_runner(*, scenario, request):
    if scenario.type == "openeo":
        return OpenEOBenchmarkRunner(
            scenario=scenario,
            request=request,
        )

    raise ValueError(f"Unsupported benchmark scenario type {scenario.type!r}")
