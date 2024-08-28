import uuid

import boto3
import moto.server
import pytest

pytest_plugins = [
    "pytester",
]

pytest.register_assert_rewrite("apex_algorithm_qa_tools.scenarios")


@pytest.fixture(scope="module")
def moto_server() -> str:
    """Fixture to run a mocked AWS server for testing."""
    # Note: pass `port=0` to get a random free port.
    server = moto.server.ThreadedMotoServer(port=0)
    server.start()
    host, port = server.get_host_and_port()
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
