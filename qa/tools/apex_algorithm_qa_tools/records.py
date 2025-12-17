from __future__ import annotations

import json
import logging
from typing import Any, List

from apex_algorithm_qa_tools.common import get_project_root

_log = logging.getLogger(__name__)


def _get_ogc_record_schema(name: str) -> dict:
    with open(get_project_root() / "schemas" / name) as f:
        return json.load(f)


def get_service_ogc_record_schema() -> dict:
    return _get_ogc_record_schema("record.json")


def get_platform_ogc_record_schema() -> dict:
    return _get_ogc_record_schema("platform.json")


def get_provider_ogc_record_schema() -> dict:
    return _get_ogc_record_schema("provider.json")


def _get_ogc_records(folder: str, glob: str) -> List[Any]:
    records = []
    for path in (get_project_root() / folder).glob(glob):
        with open(path) as f:
            data = json.load(f)
            records.append(data)
    return records


def get_service_ogc_records() -> List[Any]:
    return _get_ogc_records("algorithm_catalog", "**/records/*.json")


def get_platform_ogc_records() -> List[Any]:
    return _get_ogc_records("platform_catalog", "*.json")


def get_provider_ogc_records() -> List[Any]:
    return _get_ogc_records("algorithm_catalog", "*/record.json")
