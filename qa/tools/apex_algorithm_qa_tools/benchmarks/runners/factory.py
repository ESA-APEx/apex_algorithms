from apex_algorithm_qa_tools.benchmarks.runners.openeo import OpenEOBenchmarkRunner
from apex_algorithm_qa_tools.benchmarks.runners.ogc import OGCBenchmarkRunner


def create_benchmark_runner(*, scenario, request):
    if scenario.type == "openeo":
        return OpenEOBenchmarkRunner(
            scenario=scenario,
            request=request,
        )
    elif scenario.type == "ogc_api_process":
        return OGCBenchmarkRunner(
            scenario=scenario,
            request=request,
        )
    else:
        raise ValueError(f"Unsupported benchmark scenario type {scenario.type!r}")
