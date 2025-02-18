from __future__ import annotations

import json
import logging
from typing import List, Any

from apex_algorithm_qa_tools.common import (
    get_project_root,
)

_log = logging.getLogger(__name__)


def _get_ogc_record_schema() -> dict:
    with open(get_project_root() / "schemas" / "record.json") as f:
        return json.load(f)


def get_ogc_records() -> List[Any]:
    records = []
    for path in (get_project_root() / "algorithm_catalog").glob("**/records/*.json"):
        with open(path) as f:
            data = json.load(f)
            records.append(data)
    return records

