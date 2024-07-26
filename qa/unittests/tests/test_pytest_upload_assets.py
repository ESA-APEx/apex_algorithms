import uuid

import boto3
import moto.server
import pytest


@pytest.fixture(scope="module")
def moto_server() -> str:
    """Fixture to run a mocked AWS server for testing."""
    # Note: pass `port=0` to get a random free port.
    # TODO avoid the private `_server` attribute https://github.com/getmoto/moto/issues/7894
    server = moto.server.ThreadedMotoServer(port=0)
    server.start()
    host, port = server._server.server_address
    yield f"http://{host}:{port}"
    server.stop()


@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test123")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test456")


@pytest.fixture
def s3_client(moto_server):
    return boto3.client("s3", endpoint_url=moto_server)


@pytest.fixture
def s3_bucket(s3_client) -> str:
    # Unique bucket name for test isolation
    bucket = f"test-bucket-{uuid.uuid4().hex}"
    s3_client.create_bucket(Bucket=bucket)
    return bucket


def test_basic_upload_on_fail(
    pytester: pytest.Pytester, moto_server, s3_client, s3_bucket
):
    pytester.makeconftest(
        """
        pytest_plugins = [
            "apex_algorithm_qa_tools.pytest_upload_assets",
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

    run_result = pytester.runpytest_subprocess(
        "--upload-assets-run-id=test-run-123",
        f"--upload-assets-endpoint-url={moto_server}",
        f"--upload-assets-bucket={s3_bucket}",
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
            r".*`upload_assets` stats: \{'uploaded': 1\}",
            r"\s+-\s+'hello.txt' uploaded to 'http://.*?/test-bucket-\w+/test-run-123!test_file_maker.py__test_fail_and_upload!hello.txt'",
        ]
    )


def test_nop_on_success(pytester: pytest.Pytester, moto_server, s3_client, s3_bucket):
    pytester.makeconftest(
        """
        pytest_plugins = [
            "apex_algorithm_qa_tools.pytest_upload_assets",
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

    run_result = pytester.runpytest_subprocess(
        "--upload-assets-run-id=test-run-123",
        f"--upload-assets-endpoint-url={moto_server}",
        f"--upload-assets-bucket={s3_bucket}",
    )
    run_result.stdout.re_match_lines(
        [r"Plugin `upload_assets` is active, with upload to 'test-bucket-"]
    )
    run_result.assert_outcomes(passed=1)

    object_listing = s3_client.list_objects(Bucket=s3_bucket)
    assert object_listing.get("Contents", []) == []

    run_result.stdout.re_match_lines([r".*`upload_assets` stats: \{'uploaded': 0\}"])
