from apex_algorithm_qa_tools.scenarios import get_project_root


def test_benchmark_workflows_export_expected_cdse_auth_env_var():
    project_root = get_project_root()

    expected_mapping = "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSE: ${{ secrets.OPENEO_AUTH_CLIENT_CREDENTIALS_CDSEFED }}"

    assert expected_mapping in (project_root / ".github/workflows/benchmarks.yaml").read_text()
    assert expected_mapping in (project_root / ".github/workflows/_run_benchmarks.yaml").read_text()


def test_benchmark_specific_workflow_passes_cdsefed_secret_to_reusable_workflow():
    workflow = (get_project_root() / ".github/workflows/benchmark_specific.yaml").read_text()

    assert "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSEFED: ${{ secrets.OPENEO_AUTH_CLIENT_CREDENTIALS_CDSEFED }}" in workflow
