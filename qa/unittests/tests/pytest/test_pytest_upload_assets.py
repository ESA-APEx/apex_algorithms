import pytest


def test_basic_upload_on_fail(
    pytester: pytest.Pytester, moto_server, s3_client, s3_bucket, monkeypatch
):
    pytester.makeconftest(
        """
        pytest_plugins = [
            "apex_algorithm_qa_tools.pytest.pytest_upload_assets",
        ]
        """
    )
    pytester.makepyfile(
        test_file_maker="""
            def test_fail_and_upload(upload_assets_on_fail, tmp_path):
                path = tmp_path / "hello.txt"
                path.write_text("Hello world.")
                upload_assets_on_fail(path)
                assert 3 == 5
        """
    )

    monkeypatch.setenv("APEX_ALGORITHMS_S3_ENDPOINT_URL", moto_server)
    monkeypatch.setenv("APEX_ALGORITHMS_RUN_ID", "test-run-123")

    run_result = pytester.runpytest_subprocess(
        f"--upload-assets-s3-bucket={s3_bucket}",
    )
    run_result.stdout.re_match_lines(
        [r"Plugin `upload_assets` is active, with upload to 'test-bucket-"]
    )
    run_result.assert_outcomes(failed=1)

    object_listing = s3_client.list_objects(Bucket=s3_bucket)
    assert len(object_listing["Contents"])
    keys = [obj["Key"] for obj in object_listing["Contents"]]
    expected_key = "test-run-123!test_file_maker.py__test_fail_and_upload!hello.txt"
    assert keys == [expected_key]

    actual = s3_client.get_object(Bucket=s3_bucket, Key=expected_key)
    assert actual["Body"].read().decode("utf8") == "Hello world."

    run_result.stdout.re_match_lines(
        [
            r".*upload_assets summary",
            r"- stats: \{'uploaded': 1\}",
            r"\s+-\s+'hello.txt' uploaded to 'http://.*?/test-bucket-\w+/test-run-123!test_file_maker.py__test_fail_and_upload!hello.txt'",
        ]
    )


def test_nop_on_success(
    pytester: pytest.Pytester, moto_server, s3_client, s3_bucket, monkeypatch
):
    pytester.makeconftest(
        """
        pytest_plugins = [
            "apex_algorithm_qa_tools.pytest.pytest_upload_assets",
        ]
        """
    )
    pytester.makepyfile(
        test_file_maker="""
            def test_success(upload_assets_on_fail, tmp_path):
                path = tmp_path / "hello.txt"
                path.write_text("Hello world.")
                upload_assets_on_fail(path)
                assert 3 == 3
        """
    )

    monkeypatch.setenv("APEX_ALGORITHMS_S3_ENDPOINT_URL", moto_server)
    monkeypatch.setenv("APEX_ALGORITHMS_RUN_ID", "test-run-123")

    run_result = pytester.runpytest_subprocess(
        f"--upload-assets-s3-bucket={s3_bucket}",
    )
    run_result.stdout.re_match_lines(
        [r"Plugin `upload_assets` is active, with upload to 'test-bucket-"]
    )
    run_result.assert_outcomes(passed=1)

    object_listing = s3_client.list_objects(Bucket=s3_bucket)
    assert object_listing.get("Contents", []) == []

    run_result.stdout.re_match_lines(
        [
            r".*upload_assets summary",
            r"- stats: \{'uploaded': 0\}",
        ]
    )
