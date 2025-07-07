import re
import textwrap

import dirty_equals
from apex_algorithm_qa_tools.test_failure_handler import (
    GitHubIssueManager,
    ScenarioProcessor,
)


def test_dummy():
    assert GitHubIssueManager


class TestScenarioProcessor:
    def test_basic(self, tmp_path):
        pytest_output = """
            ============================= test session starts ==============================
            rootdir: /foo/bar
            configfile: pytest.ini

            benchmarks/tests/test_benchmarks.py::test_run_benchmark[sentinel1_stats] FAILED [ 50%]
            benchmarks/tests/test_benchmarks.py::test_run_benchmark[max_ndvi] FAILED [100%]

            =================================== FAILURES ===================================
            _____________________ test_run_benchmark[sentinel1_stats] ______________________

            scenario = BenchmarkScenario(id='sentinel1_stats', description='Sentinel 1 statistics example', backend='openeofed.dataspace.cope...gh-11743427213!tests_test_benchmarks.py__test_run_benchmark_sentinel1_stats_!actual/openEO.tif'}, reference_options={})
            connection_factory = <function connection_factory.<locals>.get_connection at 0x7d6937266e80>
            request = <FixtureRequest for <Function test_run_benchmark[sentinel1_stats]>>

            >           connection: openeo.Connection = connection_factory(url=backend)

            benchmarks/tests/test_benchmarks.py:55:
            _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
            benchmarks/tests/conftest.py:165: in get_connection
                connection.authenticate_oidc(max_poll_time=max_poll_time)
            ../../../openeo/openeo-python-client/openeo/rest/connection.py:580: in authenticate_oidc
                return self.authenticate_oidc_client_credentials(
            ../../../openeo/openeo-python-client/openeo/rest/connection.py:428: in authenticate_oidc_client_credentials
                provider_id, client_info = self._get_oidc_provider_and_client_info(
            _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

                    if client_id is None:
            >           raise OpenEoClientException("No client_id found.")
            E           openeo.rest.OpenEoClientException: No client_id found.

            ../../../openeo/openeo-python-client/openeo/rest/connection.py:333: OpenEoClientException
            _________________________ test_run_benchmark[max_ndvi] _________________________

            scenario = BenchmarkScenario(id='max_ndvi', description='max_ndvi example', backend='openeofed.dataspace.copernicus.eu', process_...hmarks/gh-15066001243!tests_test_benchmarks.py__test_run_benchmark_max_ndvi_!actual/openEO.tif'}, reference_options={})

            >           connection: openeo.Connection = connection_factory(url=backend)

            benchmarks/tests/test_benchmarks.py:55:
            _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
            benchmarks/tests/conftest.py:165: in get_connection
                connection.authenticate_oidc(max_poll_time=max_poll_time)
            ../../../openeo/openeo-python-client/openeo/rest/connection.py:580: in authenticate_oidc
                return self.authenticate_oidc_client_credentials(
            ../../../openeo/openeo-python-client/openeo/rest/connection.py:428: in authenticate_oidc_client_credentials
                provider_id, client_info = self._get_oidc_provider_and_client_info(
            _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

                    if client_id is None:
            >           raise OpenEoClientException("No client_id found.")
            E           openeo.rest.OpenEoClientException: No client_id found.

            ../../../openeo/openeo-python-client/openeo/rest/connection.py:333: OpenEoClientException
            =============================== warnings summary ===============================
            tests/test_benchmarks.py::test_run_benchmark[sentinel1_stats]
            tests/test_benchmarks.py::test_run_benchmark[max_ndvi]
            /home/lippenss/src/APEx/apex_algorithms/qa/tools/apex_algorithm_qa_tools/pytest/pytest_track_metrics.py:376: UserWarning: Fixture `track_metric` is a no-op (incomplete set up).
                warnings.warn("Fixture `track_metric` is a no-op (incomplete set up).")


            -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
            =========================== short test summary info ============================
            FAILED benchmarks/tests/test_benchmarks.py::test_run_benchmark[sentinel1_stats] - openeo.rest.OpenEoClientException: No client_id found.
            FAILED benchmarks/tests/test_benchmarks.py::test_run_benchmark[max_ndvi] - openeo.rest.OpenEoClientException: No client_id found.
            ================= 2 failed, 10 deselected, 4 warnings in 1.23s =================
            """

        pytest_output_path = tmp_path / "pytest_output.txt"
        pytest_output_path.write_text(textwrap.dedent(pytest_output))

        failed_tests = ScenarioProcessor().parse_failed_tests(pytest_output_path)
        assert failed_tests == [
            {
                "test_name": "test_run_benchmark[sentinel1_stats]",
                "scenario_id": "sentinel1_stats",
                "logs": dirty_equals.IsStr(
                    regex="scenario = BenchmarkScenario.*OpenEoClientException",
                    regex_flags=re.DOTALL,
                ),
            },
            # TODO: there should also be an entry for `test_run_benchmark[max_ndvi]` here
        ]
