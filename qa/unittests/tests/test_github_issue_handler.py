import textwrap
from pathlib import Path

import pytest
from apex_algorithm_qa_tools.github_issue_handler import (
    GithubApi,
    GithubContext,
    PytestReportParser,
    ScenarioRunInfo,
    TerminalReportSection,
    TestMetricsData,
)
from apex_algorithm_qa_tools.scenarios import BenchmarkScenario


class TestGithubApi:
    def test_list_issues(self, requests_mock):
        def handle_get_issues(request, context):
            assert request.headers["Authorization"] == "Bearer t0k9n!"
            assert request.query == "state=open&page=1"
            return [
                {"number": 123, "title": "Issue 123"},
                {"number": 345, "title": "Issue 345"},
            ]

        requests_mock.get(
            "https://api.github.com/repos/esa/apex/issues",
            json=handle_get_issues,
        )
        api = GithubApi(repository="esa/apex", token="t0k9n!")
        issues = api.list_issues()
        assert issues == [
            {"number": 123, "title": "Issue 123"},
            {"number": 345, "title": "Issue 345"},
        ]

    def test_list_issues_with_labels(self, requests_mock):
        def handle_get_issues(request, context):
            assert request.headers["Authorization"] == "Bearer t0k9n!"
            assert request.query == "state=open&page=1&labels=test-failure"
            return [
                {"number": 123, "title": "Issue 123"},
                {"number": 345, "title": "Issue 345"},
            ]

        requests_mock.get(
            "https://api.github.com/repos/esa/apex/issues",
            json=handle_get_issues,
        )
        api = GithubApi(repository="esa/apex", token="t0k9n!")
        issues = api.list_issues(labels=["test-failure"])
        assert issues == [
            {"number": 123, "title": "Issue 123"},
            {"number": 345, "title": "Issue 345"},
        ]

    def test_create_issue(self, requests_mock):
        def handle_create_issue(request, context):
            assert request.headers["Authorization"] == "Bearer t0k9n!"
            assert request.method == "POST"
            assert request.json() == {
                "title": "Test Issue",
                "body": "This is a test issue.",
                "labels": ["test-failure"],
            }
            context.status_code = 201
            return {"number": 123, "title": "Test Issue"}

        requests_mock.post(
            "https://api.github.com/repos/esa/apex/issues",
            json=handle_create_issue,
        )
        api = GithubApi(repository="esa/apex", token="t0k9n!")
        issue = api.create_issue(
            title="Test Issue", body="This is a test issue.", labels=["test-failure"]
        )
        assert issue == {"number": 123, "title": "Test Issue"}

    def test_create_issue_comment(self, requests_mock):
        def handle_create_comment(request, context):
            assert request.headers["Authorization"] == "Bearer t0k9n!"
            assert request.method == "POST"
            assert request.json() == {"body": "This is a test comment."}
            context.status_code = 201
            return {"id": 456, "body": "This is a test comment."}

        requests_mock.post(
            "https://api.github.com/repos/esa/apex/issues/123/comments",
            json=handle_create_comment,
        )
        api = GithubApi(repository="esa/apex", token="t0k9n!")
        comment = api.create_issue_comment(
            issue_number=123, body="This is a test comment."
        )
        assert comment == {"id": 456, "body": "This is a test comment."}


@pytest.fixture
def github_context() -> GithubContext:
    """GithubContext with explicit initialization."""
    return GithubContext(
        server_url="https://github.test",
        repository="foorg/bar-pro",
        run_id="1234",
        sha="abcdef123456",
        token="t0k9n!",
    )


class TestGithubContext:
    @pytest.fixture
    def with_github_env(self, monkeypatch):
        monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.test")
        monkeypatch.setenv("GITHUB_REPOSITORY", "foorg/bar-pro")
        monkeypatch.setenv("GITHUB_RUN_ID", "1234")
        monkeypatch.setenv("GITHUB_SHA", "abcdef123456")
        monkeypatch.setenv("GITHUB_TOKEN", "t0k9n!")

    def test_workflow_run_explicit_init(self, github_context):
        assert github_context.get_workflow_run_url() == (
            "https://github.test/foorg/bar-pro/actions/runs/1234"
        )

    def test_workflow_run_with_github_env(self, with_github_env):
        context = GithubContext()
        assert context.get_workflow_run_url() == (
            "https://github.test/foorg/bar-pro/actions/runs/1234"
        )

    @pytest.mark.parametrize(
        "path",
        [
            "path/to/file.json",
            Path("path/to/file.json"),
        ],
    )
    def test_get_permalink_explicit_init(self, github_context, path):
        assert github_context.get_file_permalink(path) == (
            "https://github.test/foorg/bar-pro/blob/abcdef123456/path/to/file.json"
        )


class TestPytestReportParser:
    def test_parse_metrics_json(self, tmp_path):
        path = tmp_path / "metrics.json"
        path.write_text(
            """
        [
            {
                "nodeid": "tests/test_benchmarks.py::test_run_benchmark[max_ndvi]",
                "report": {
                    "outcome": "failed",
                    "duration": 12.34
                },
                "metrics": [
                    ["scenario_id", "max_ndvi"],
                    ["test:phase:start", "compare"],
                    ["test:phase:end", "download-reference"],
                    ["test:phase:exception", "compare"],
                    ["job_id", "j-1234"],
                    ["costs", 4]
                ]
            },
            {
                "nodeid": "something_else",
                "report": {
                    "outcome": "whatever"
                },
                "metrics": []
            }
        ]
        """
        )

        metrics = PytestReportParser().parse_metrics_json(path)
        assert metrics == [
            {
                "nodeid": "tests/test_benchmarks.py::test_run_benchmark[max_ndvi]",
                "outcome": "failed",
                "duration": 12.34,
                "scenario_id": "max_ndvi",
                "job_id": "j-1234",
                "costs": 4,
                "start": None,
                "test:phase:start": "compare",
                "test:phase:end": "download-reference",
                "test:phase:exception": "compare",
            },
            {
                "nodeid": "something_else",
                "outcome": "whatever",
                "duration": None,
                "scenario_id": None,
                "job_id": None,
                "costs": None,
                "start": None,
                "test:phase:start": None,
                "test:phase:end": None,
                "test:phase:exception": None,
            },
        ]

    def test_parse_terminal_report_sections(self, tmp_path):
        pytest_output = """\
            ============================= test session starts ==============================
            rootdir: /foo/bar
            configfile: pytest.ini

            =================================== FAILURES ===================================
            _____________________ test_run_benchmark[sentinel1_stats] ______________________
            hello sentinel1

            _________________________ test_run_benchmark[max_ndvi] _________________________
            max the NDVI!
            _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
            subsub

            =========================== short test summary info ============================
            FAILED benchmarks/tests/test_benchmarks.py::test_run_benchmark[sentinel1_stats] - sad
            FAILED benchmarks/tests/test_benchmarks.py::test_run_benchmark[max_ndvi] - failure
            ================= 2 failed, 10 deselected, 4 warnings in 1.23s =================
            """

        pytest_output_path = tmp_path / "pytest_output.txt"
        pytest_output_path.write_text(textwrap.dedent(pytest_output))

        sections = PytestReportParser().parse_terminal_report_sections(
            pytest_output_path
        )
        assert sections == TerminalReportSection(
            title="root",
            subnodes=[
                TerminalReportSection(
                    title="test session starts",
                    subnodes=[
                        "rootdir: /foo/bar",
                        "configfile: pytest.ini",
                        "",
                    ],
                ),
                TerminalReportSection(
                    title="FAILURES",
                    subnodes=[
                        TerminalReportSection(
                            title="test_run_benchmark[sentinel1_stats]",
                            subnodes=[
                                "hello sentinel1",
                                "",
                            ],
                        ),
                        TerminalReportSection(
                            title="test_run_benchmark[max_ndvi]",
                            subnodes=[
                                "max the NDVI!",
                                "_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _",
                                "subsub",
                                "",
                            ],
                        ),
                    ],
                ),
                TerminalReportSection(
                    title="short test summary info",
                    subnodes=[
                        "FAILED benchmarks/tests/test_benchmarks.py::test_run_benchmark[sentinel1_stats] - sad",
                        "FAILED benchmarks/tests/test_benchmarks.py::test_run_benchmark[max_ndvi] - failure",
                    ],
                ),
                TerminalReportSection(
                    title="2 failed, 10 deselected, 4 warnings in 1.23s",
                    subnodes=[],
                ),
            ],
        )

    def test_extract_failure_logs(self, tmp_path):
        pytest_output = """\
            ============================= test session starts ==============================
            rootdir: /foo/bar
            configfile: pytest.ini

            =================================== FAILURES ===================================
            _____________________ test_run_benchmark[sentinel1_stats] ______________________
            hello
                sentinel1

            _________________________ test_run_benchmark[max_ndvi] _________________________
            max the NDVI!
            _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
            subsub

            =========================== short test summary info ============================
            FAILED benchmarks/tests/test_benchmarks.py::test_run_benchmark[sentinel1_stats] - sad
            FAILED benchmarks/tests/test_benchmarks.py::test_run_benchmark[max_ndvi] - failure
            ================= 2 failed, 10 deselected, 4 warnings in 1.23s =================
            """

        pytest_output_path = tmp_path / "pytest_output.txt"
        pytest_output_path.write_text(textwrap.dedent(pytest_output))

        logs = PytestReportParser().extract_failure_logs(pytest_output_path)
        assert logs == {
            "test_run_benchmark[sentinel1_stats]": "hello\n    sentinel1",
            "test_run_benchmark[max_ndvi]": textwrap.dedent(
                """\
                max the NDVI!
                _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
                subsub"""
            ),
        }


class TestScenarioRunInfo:
    @pytest.fixture
    def benchmark_scenario(self, test_data_root) -> BenchmarkScenario:
        path = (
            test_data_root
            / "algorithm_catalog"
            / "foorg"
            / "add35"
            / "benchmark_scenarios"
            / "add3x.json"
        )
        return BenchmarkScenario.read_scenarios_file(path)[0]

    @pytest.fixture
    def metrics_data(self) -> TestMetricsData:
        return {
            "nodeid": "tests/test_foo.py::test_bar[meh]",
            "start": 1752050000,
            "duration": 120,
            "outcome": "failed",
            "test:phase:start": "compare",
            "test:phase:end": "download-reference",
            "test:phase:exception": "compare",
        }

    @pytest.fixture
    def scenario_run_info(
        self, benchmark_scenario, github_context, metrics_data
    ) -> ScenarioRunInfo:
        return ScenarioRunInfo(
            scenario=benchmark_scenario,
            github_context=github_context,
            test_metrics=metrics_data,
            failure_logs=textwrap.dedent(
                """
                        x = 3 * 0
                >       pi = 22 / x
                E       ZeroDivisionError
                """
            ),
        )

    def test_build_workflow_run_overview_minimal(
        self, benchmark_scenario, github_context
    ):
        scenario_run_info = ScenarioRunInfo(
            scenario=benchmark_scenario, github_context=github_context, test_metrics={}
        )
        assert scenario_run_info.build_workflow_run_overview() == textwrap.dedent(
            """
            **Benchmark scenario ID**: `add35`
            **Benchmark scenario definition**: https://github.test/foorg/bar-pro/blob/abcdef123456/qa/unittests/tests/data/algorithm_catalog/foorg/add35/benchmark_scenarios/add3x.json
            **openEO backend**: openeo.test

            **GitHub Actions workflow run**: https://github.test/foorg/bar-pro/actions/runs/1234
            **Workflow artifacts**: https://github.test/foorg/bar-pro/actions/runs/1234#artifacts
            """
        )

    def test_build_workflow_run_overview_full(self, scenario_run_info):
        assert scenario_run_info.build_workflow_run_overview() == textwrap.dedent(
            """
            **Benchmark scenario ID**: `add35`
            **Benchmark scenario definition**: https://github.test/foorg/bar-pro/blob/abcdef123456/qa/unittests/tests/data/algorithm_catalog/foorg/add35/benchmark_scenarios/add3x.json
            **openEO backend**: openeo.test

            **GitHub Actions workflow run**: https://github.test/foorg/bar-pro/actions/runs/1234
            **Workflow artifacts**: https://github.test/foorg/bar-pro/actions/runs/1234#artifacts

            **Test start**: 2025-07-09 08:33:20+00:00
            **Test duration**: 0:02:00
            **Test outcome**: ❌ failed

            **Last successful test phase**: download-reference
            **Failure in test phase**: compare
            """
        )

    def test_build_contact_table(self, scenario_run_info):
        assert scenario_run_info.build_contact_table() == textwrap.dedent(
            """
            | Name   | Organization | Contact |
            |--------|--------------|---------|
            | John Doe | Foorg        | Pigeon post is preferred. ([Foorg Website](https://www.foorg.test/)) |
            """
        )

    def test_build_issue_body(self, scenario_run_info):
        assert scenario_run_info.build_issue_body() == textwrap.dedent(
            """
            **Benchmark scenario ID**: `add35`
            **Benchmark scenario definition**: https://github.test/foorg/bar-pro/blob/abcdef123456/qa/unittests/tests/data/algorithm_catalog/foorg/add35/benchmark_scenarios/add3x.json
            **openEO backend**: openeo.test

            **GitHub Actions workflow run**: https://github.test/foorg/bar-pro/actions/runs/1234
            **Workflow artifacts**: https://github.test/foorg/bar-pro/actions/runs/1234#artifacts

            **Test start**: 2025-07-09 08:33:20+00:00
            **Test duration**: 0:02:00
            **Test outcome**: ❌ failed

            **Last successful test phase**: download-reference
            **Failure in test phase**: compare


            ### Contact Information


            | Name   | Organization | Contact |
            |--------|--------------|---------|
            | John Doe | Foorg        | Pigeon post is preferred. ([Foorg Website](https://www.foorg.test/)) |


            ### Process Graph

            ```json
            {
              "add1": {
                "process_id": "add",
                "arguments": {
                  "x": 3,
                  "y": 5
                },
                "result": true
              }
            }
            ```

            ### Error Logs

            ```plaintext

                    x = 3 * 0
            >       pi = 22 / x
            E       ZeroDivisionError

            ```
            """
        )

    def test_build_comment_body(self, scenario_run_info):
        assert scenario_run_info.build_comment_body() == textwrap.dedent(
            """\
            Report of latest run:

            **Benchmark scenario ID**: `add35`
            **Benchmark scenario definition**: https://github.test/foorg/bar-pro/blob/abcdef123456/qa/unittests/tests/data/algorithm_catalog/foorg/add35/benchmark_scenarios/add3x.json
            **openEO backend**: openeo.test

            **GitHub Actions workflow run**: https://github.test/foorg/bar-pro/actions/runs/1234
            **Workflow artifacts**: https://github.test/foorg/bar-pro/actions/runs/1234#artifacts

            **Test start**: 2025-07-09 08:33:20+00:00
            **Test duration**: 0:02:00
            **Test outcome**: ❌ failed

            **Last successful test phase**: download-reference
            **Failure in test phase**: compare
            """
        )
