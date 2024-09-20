import os
import uuid

_DEFAULT_RUN_ID = uuid.uuid4().hex


def get_run_id() -> str:
    if "APEX_ALGORITHMS_RUN_ID" in os.environ:
        return os.environ["APEX_ALGORITHMS_RUN_ID"]
    elif "GITHUB_RUN_ID" in os.environ:
        return "gh-" + os.environ["GITHUB_RUN_ID"]

    return _DEFAULT_RUN_ID
