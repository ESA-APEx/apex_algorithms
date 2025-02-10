from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterator

# TODO #15 Flatten apex_algorithm_qa_tools to a single module and push as much functionality to https://github.com/ESA-APEx/esa-apex-toolbox-python


_log = logging.getLogger(__name__)


def get_project_root() -> Path:
    """Try to find project root for common project use cases and CI situations."""

    def candidates() -> Iterator[Path]:
        # TODO: support a environment variable to override the project root detection?
        # Running from project root?
        yield Path.cwd()

        # Running from qa/tools, qa/benchmarks, qa/unittests?
        yield Path.cwd().parent.parent

        # Search from current file
        yield Path(__file__).parent.parent.parent.parent

    for candidate in candidates():
        if candidate.is_dir() and all(
            (candidate / p).is_dir()
            for p in ["algorithm_catalog", "qa/tools"]
        ):
            _log.info(f"Detected project root {candidate!r}")
            return candidate

    raise RuntimeError("Could not determine project root directory.")


def assert_no_github_feature_branch_refs(href: str) -> None:
    """
    Check that GitHub links do not point to (ephemeral) feature branches.
    """
    # TODO: automatically suggest commit hash based fix?
    allowed_branches = {"main", "master"}

    # Check for feature branches with explicit "refs/heads" prefix in the URL
    if match := re.search("//raw.githubusercontent.com/.*/refs/heads/(.*?)/", href):
        if match.group(1) not in allowed_branches:
            # TODO: automatically suggest commit hash based fix?
            raise ValueError(
                f"Links should not point to ephemeral feature branches: found {match.group(1)!r} in {href!r}"
            )

    # Also check shorthand URLs without "refs/heads"
    if match := re.search(
        "//raw.githubusercontent.com/ESA-APEx/apex_algorithms/(.*?)/", href
    ):
        ref = match.group(1)
        # Only, allow main/master and commit hashes
        if (
            not re.fullmatch("[0-9a-f]+", ref)
            and ref != "refs"
            and ref not in allowed_branches
        ):
            raise ValueError(
                f"Links should not point to ephemeral feature branches: found {match.group(1)!r} in {href!r}"
            )
