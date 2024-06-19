from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import List

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


@dataclasses.dataclass(kw_only=True)
class UseCase:
    # TODO: need for differentiation between different types of use cases?
    id: str
    description: str | None = None
    backend: str
    process_graph: dict

    @classmethod
    def from_dict(cls, data: dict) -> UseCase:
        # TODO: standardization of these types? What about other types and how to support them?
        assert data["type"] == "openeo"
        return cls(
            id=data["id"],
            description=data.get("description"),
            backend=data["backend"],
            process_graph=data["process_graph"],
        )


def get_use_cases() -> List[UseCase]:
    # TODO: instead of flat list, keep original grouping/structure of "algorithm_invocations" files?
    use_cases = []
    for path in (_PROJECT_ROOT / "algorithm_invocations").glob("*.json"):
        with open(path) as f:
            data = json.load(f)
        # TODO: support single use case files in addition to listings?
        assert isinstance(data, list)
        use_cases.extend(UseCase.from_dict(item) for item in data)
    return use_cases
