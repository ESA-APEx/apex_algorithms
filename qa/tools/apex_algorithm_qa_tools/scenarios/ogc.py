from __future__ import annotations

import dataclasses
from pathlib import Path

import jsonschema

from apex_algorithm_qa_tools.scenarios.scenario import (
    BenchmarkScenario,
    get_benchmark_scenario_schema,
)


@dataclasses.dataclass(kw_only=True)
class OGCAPIAuth:
    url: str
    realm: str


@dataclasses.dataclass(kw_only=True)
class OGCAPIResults:
    s3_endpoint: str


@dataclasses.dataclass(kw_only=True)
class OGCAPIBenchmarkScenario(BenchmarkScenario):
    endpoint: str
    parameters: dict
    namespace: str | None = None
    application: str | None = None
    auth: OGCAPIAuth
    results: OGCAPIResults | None = None

    @classmethod
    def from_dict(
        cls,
        data: dict,
        source: str | Path | None = None,
    ) -> BenchmarkScenario:
        jsonschema.validate(instance=data, schema=get_benchmark_scenario_schema())

        application = data.get("application")
        namespace = data.get("namespace")
        auth = OGCAPIAuth(**data.get("auth", {}))
        results = OGCAPIResults(**data.get("results", {})) if data.get("results") else None

        return cls(
            id=data["id"],
            type=data["type"],
            description=data.get("description"),
            endpoint=data["endpoint"],
            parameters=data.get("parameters", {}),
            auth=auth,
            namespace=namespace,
            application=application,
            reference_data=data.get("reference_data", {}),
            reference_options=data.get("reference_options", {}),
            source=source,
            results=results,
        )
