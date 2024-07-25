"""
Pytest plugin to collect files generated during benchmark/test
and upload them to S3 (e.g. on test failure).
"""

import logging
import os
import re
import uuid
from pathlib import Path
from typing import Callable, Dict, Union

import boto3
import pytest

_log = logging.getLogger(__name__)

_PLUGIN_NAME = "upload_assets"


def pytest_addoption(parser):
    # TODO: options for S3 bucket, credentials, ...
    # TODO: option to always upload (also on success).
    parser.addoption(
        "--upload-assets-runid",
        metavar="ID",
        action="store",
        help="The run ID to use for building the S3 key.",
    )


def pytest_configure(config: pytest.Config):
    if (
        # TODO only register if enough config is available for setup
        # Don't register on xdist worker nodes
        not hasattr(config, "workerinput")
    ):
        s3_client = boto3.client(
            service_name="s3",
            aws_access_key_id=os.environ.get("UPLOAD_ASSETS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("UPLOAD_ASSETS_SECRET_ACCESS_KEY"),
            # TODO Option for endpoint url
            endpoint_url=os.environ.get("UPLOAD_ASSETS_ENDPOINT_URL"),
        )
        bucket = os.environ.get("UPLOAD_ASSETS_BUCKET")
        config.pluginmanager.register(
            S3UploadPlugin(
                run_id=config.getoption("upload_assets_runid"),
                s3_client=s3_client,
                bucket=bucket,
            ),
            name=_PLUGIN_NAME,
        )


class _Collector:
    """
    Collects test outcomes and files to upload for a single test node.
    """

    def __init__(self, nodeid: str) -> None:
        self.nodeid = nodeid
        self.outcomes: Dict[str, str] = {}
        self.assets: Dict[str, Path] = {}

    def set_outcome(self, when: str, outcome: str):
        self.outcomes[when] = outcome

    def collect(self, path: Path, name: str):
        self.assets[name] = path


class S3UploadPlugin:
    def __init__(self, *, run_id: str | None = None, s3_client, bucket: str) -> None:
        self.run_id = run_id or uuid.uuid4().hex
        self.collector: Union[_Collector, None] = None
        self.s3_client = s3_client
        self.bucket = bucket

    def pytest_runtest_logstart(self, nodeid, location):
        self.collector = _Collector(nodeid=nodeid)

    def pytest_runtest_logreport(self, report: pytest.TestReport):
        self.collector.set_outcome(when=report.when, outcome=report.outcome)

    def pytest_runtest_logfinish(self, nodeid, location):
        # TODO: option to also upload on success?
        if self.collector.outcomes.get("call") == "failed":
            self._upload(self.collector)

        self.collector = None

    def _upload(self, collector: _Collector):
        for name, path in collector.assets.items():
            nodeid = re.sub(r"[^a-zA-Z0-9_.-]", "_", collector.nodeid)
            key = f"{self.run_id}!{nodeid}!{name}"
            # TODO: get upload info in report?
            _log.info(f"Uploading {path} to {self.bucket}/{key}")
            self.s3_client.upload_file(
                Filename=str(path),
                Bucket=self.bucket,
                Key=key,
                # TODO: option to override ACL, or ExtraArgs in general?
                ExtraArgs={"ACL": "public-read"},
            )


@pytest.fixture
def upload_assets(pytestconfig, tmp_path) -> Callable[[Path], None]:
    """
    Fixture to register a file (under `tmp_path`) for S3 upload
    after the test failed.
    """
    uploader = pytestconfig.pluginmanager.get_plugin(_PLUGIN_NAME)

    def collect(*paths: Path):
        for path in paths:
            assert path.is_relative_to(tmp_path)
            name = str(path.relative_to(tmp_path))
            uploader.collector.collect(path=path, name=name)

    return collect
