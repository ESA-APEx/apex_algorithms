"""
Pytest plugin to collect files generated during benchmark/test
and upload them to S3 (e.g. on test failure).

Usage:

-  Enable the plugin in `conftest.py`:

    ```python
    pytest_plugins = [
        "apex_algorithm_qa_tools.pytest.pytest_upload_assets",
    ]

-  Use the `upload_assets_on_fail` fixture to register files for upload
   when the test fails:

    ```python
    def test_dummy(upload_assets_on_fail, tmp_path):
        path = tmp_path / "hello.txt"
        path.write_text("Hello world.")
        upload_assets_on_fail(path)
    ```

- Run the tests with with desired configuration through CLI options and env vars:
    - CLI option to set S3 bucket: `--upload-assets-s3-bucket={BUCKET}`
    - S3 credentials with env vars `APEX_ALGORITHMS_S3_ACCESS_KEY_ID`
      and `APEX_ALGORITHMS_S3_SECRET_ACCESS_KEY`
      (Note that the classic `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
      are also supported as fallback)
    - S3 endpoint URL with env var `APEX_ALGORITHMS_S3_ENDPOINT_URL`
      (Note that the classic `AWS_ENDPOINT_URL` is also supported as fallback).
"""

import collections
import logging
import os
import re
import warnings
from pathlib import Path
from typing import Callable, Dict

import boto3
import botocore.config
import pytest
from apex_algorithm_qa_tools.pytest import get_run_id

_log = logging.getLogger(__name__)

_UPLOAD_ASSETS_PLUGIN_NAME = "upload_assets"
_USER_PROPERTY = "upload_assets"


def pytest_addoption(parser: pytest.Parser):
    # TODO #22: option to always upload (also on success).
    parser.addoption(
        "--upload-assets-s3-bucket",
        metavar="BUCKET",
        help="The S3 bucket to upload to.",
    )


def pytest_configure(config: pytest.Config):
    bucket = config.getoption("--upload-assets-s3-bucket")
    if bucket:
        s3_client = boto3.client(
            service_name="s3",
            aws_access_key_id=os.environ.get("APEX_ALGORITHMS_S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get(
                "APEX_ALGORITHMS_S3_SECRET_ACCESS_KEY"
            ),
            endpoint_url=os.environ.get("APEX_ALGORITHMS_S3_ENDPOINT_URL"),
            config=botocore.config.Config(
                # Disable new checksum validation feature
                # (not supported yet by third-party S3 implementations)
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )
        config.pluginmanager.register(
            S3UploadPlugin(s3_client=s3_client, bucket=bucket),
            name=_UPLOAD_ASSETS_PLUGIN_NAME,
        )


class S3UploadPlugin:
    def __init__(self, *, run_id: str | None = None, s3_client, bucket: str) -> None:
        self.run_id = run_id or get_run_id()
        self.collected_assets: Dict[str, Path] | None = None
        self.s3_client = s3_client
        self.bucket = bucket
        self.upload_stats = collections.defaultdict(int, uploaded=0)
        self.upload_reports: Dict[str, dict] = {}

    def collect(self, path: Path, name: str):
        """Collect assets to upload"""
        assert self.collected_assets is not None, "No active collection of assets"
        self.collected_assets[name] = path
        # TODO: this stat won't work properly in pytest-xdist context
        #       because incrementing stat happens on xdist workers,
        #       while summary is done from xdist controller).
        self.upload_stats["collected"] += 1

    def pytest_runtest_logstart(self, nodeid):
        # Start new collection of assets for current test node
        self.collected_assets = {}

    def pytest_runtest_logreport(self, report: pytest.TestReport):
        # TODO #22: option to upload on other outcome as well?
        if report.when == "call" and report.outcome == "failed":
            self._upload_collected_assets(nodeid=report.nodeid, report=report)

        # Merge stats
        for upload_info in (
            v for k, v in report.user_properties if k == _USER_PROPERTY
        ):
            for k, v in upload_info["stats"].items():
                self.upload_stats[k] += v
            if upload_info["uploads"]:
                self.upload_reports[report.nodeid] = upload_info["uploads"]

    def pytest_runtest_logfinish(self, nodeid):
        # Reset collection of assets
        self.collected_assets = None

    def _upload_collected_assets(self, nodeid: str, report: pytest.TestReport):
        upload_info = {
            "stats": {"uploaded": 0, "failed": 0},
            "uploads": {},
        }
        for name, path in self.collected_assets.items():
            try:
                url = self._upload_asset(nodeid=nodeid, name=name, path=path)
                upload_info["uploads"][name] = {"url": url}
                upload_info["stats"]["uploaded"] += 1
            except Exception as e:
                _log.error(
                    f"Failed to upload asset {name=} from {path=}: {e=}", exc_info=True
                )
                upload_info["uploads"][name] = {"error": str(e)}
                upload_info["stats"]["failed"] += 1

        # Pass upload info through user_properties to be xdist-compatible
        report.user_properties.append([_USER_PROPERTY, upload_info])

    def _upload_asset(self, nodeid: str, name: str, path: Path) -> str:
        safe_nodeid = re.sub(r"[^a-zA-Z0-9_.-]", "_", nodeid)
        key = f"{self.run_id}!{safe_nodeid}!{name}"
        # TODO: is this manual URL building correct? And isn't there a boto utility for that?
        url = f"{self.s3_client.meta.endpoint_url.rstrip('/')}/{self.bucket}/{key}"
        _log.info(f"Uploading asset {name=} from {path=} to {url=}")
        self.s3_client.upload_file(
            Filename=str(path),
            Bucket=self.bucket,
            Key=key,
            # TODO: option to override ACL, or ExtraArgs in general?
            ExtraArgs={"ACL": "public-read"},
        )
        return url

    def pytest_report_header(self):
        return f"Plugin `upload_assets` is active, with upload to {self.bucket!r}"

    def pytest_terminal_summary(self, terminalreporter):
        terminalreporter.write_sep("=", "upload_assets summary")
        terminalreporter.write_line(f"- stats: {dict(self.upload_stats)}")
        for nodeid, upload_report in self.upload_reports.items():
            terminalreporter.write_line(f"- {nodeid}:")
            for name, report in sorted(upload_report.items()):
                if "url" in report:
                    terminalreporter.write_line(
                        f"  - {name!r} uploaded to {report['url']!r}"
                    )
                elif "error" in report:
                    terminalreporter.write_line(
                        f"  - {name!r} failed with: {report['error']!r}"
                    )


@pytest.fixture
def upload_assets_on_fail(pytestconfig: pytest.Config, tmp_path) -> Callable:
    """
    Fixture to register a file (under `tmp_path`) for S3 upload
    after the test failed. The fixture is a function that
    can be called with one or more `Path` objects to upload.
    """
    uploader: S3UploadPlugin | None = pytestconfig.pluginmanager.get_plugin(
        _UPLOAD_ASSETS_PLUGIN_NAME
    )

    if uploader:

        def collect(*paths: Path):
            for path in paths:
                # TODO: option to make relative from other root
                #       (e.g. when test uses an `actual` folder for actual results)
                assert path.is_relative_to(tmp_path)
                name = str(path.relative_to(tmp_path))
                uploader.collect(path=path, name=name)

    else:
        warnings.warn("Fixture `upload_assets` is a no-op (incomplete set up).")

        def collect(*paths: Path):
            pass

    return collect
