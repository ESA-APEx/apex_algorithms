from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

# TODO: Flatten apex_algorithm_qa_tools to a single module and push as much functionality to https://github.com/ESA-APEx/esa-apex-toolbox-python


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
            for p in ["algorithm_catalog", "benchmark_scenarios", "qa/tools"]
        ):
            _log.info(f"Detected project root {candidate!r}")
            return candidate

    raise RuntimeError("Could not determine project root directory.")
