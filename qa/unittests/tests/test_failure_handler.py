import textwrap

from apex_algorithm_qa_tools.test_failure_handler import (
    GitHubIssueManager,
    ScenarioProcessor,
    TerminalReportSection,
)


def test_dummy():
    assert GitHubIssueManager


class TestScenarioProcessor:
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

        metrics = ScenarioProcessor().parse_metrics_json(path)
        assert metrics == [
            {
                "nodeid": "tests/test_benchmarks.py::test_run_benchmark[max_ndvi]",
                "outcome": "failed",
                "duration": 12.34,
                "scenario_id": "max_ndvi",
                "job_id": "j-1234",
                "costs": 4,
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

        sections = ScenarioProcessor().parse_terminal_report_sections(
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

        logs = ScenarioProcessor().extract_failure_logs(pytest_output_path)
        assert logs == {
            "test_run_benchmark[sentinel1_stats]": "hello sentinel1",
            "test_run_benchmark[max_ndvi]": textwrap.dedent(
                """\
                max the NDVI!
                _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
                subsub"""
            ),
        }
