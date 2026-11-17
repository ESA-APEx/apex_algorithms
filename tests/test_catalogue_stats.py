import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/generate_catalogue_stats.py"
spec = importlib.util.spec_from_file_location("generate_catalogue_stats", SCRIPT)
catalogue_stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalogue_stats)


def write_record(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_stats_include_only_providers_with_public_records(tmp_path):
    root = tmp_path / "catalogue"
    for provider in ("alpha", "beta", "empty", "private_only"):
        write_record(root / provider / "record.json", {"properties": {"title": provider.title()}})

    public_platform = tmp_path / "public-platform.json"
    private_platform = tmp_path / "private-platform.json"
    write_record(public_platform, {"properties": {"title": "Public platform"}})
    write_record(private_platform, {"properties": {"title": "Private platform"}})

    def algorithm(provider, name, visibility=None, platform=public_platform):
        properties = {"keywords": [name]}
        if visibility is not None:
            properties["visibility"] = visibility
        write_record(root / provider / name / "records" / f"{name}.json", {
            "properties": properties,
            "conformsTo": ["https://example.test/openeo-udp"],
            "links": [{"rel": "platform", "href": str(platform)}],
        })

    algorithm("alpha", "explicit", "public")
    algorithm("alpha", "default")
    algorithm("beta", "another")
    algorithm("alpha", "hidden", "private", private_platform)
    algorithm("private_only", "hidden_only", "private", private_platform)
    algorithm("orphan", "orphaned")
    (root / "empty" / "without_record").mkdir()

    stats = catalogue_stats.build_stats(root, top_n=20)

    assert stats["summary"] == {
        "total_providers": 2,
        "total_algorithms": 3,
        "total_platforms": 1,
        "average_algorithms_per_provider": 1.5,
    }
    assert stats["distributions"] == {
        "algorithms_by_provider": [{"name": "Alpha", "count": 2}, {"name": "Beta", "count": 1}],
        "algorithms_by_interface": [{"name": "openEO UDP", "count": 3}],
        "algorithms_by_platform": [{"name": "Public platform", "count": 3}],
        "top_keywords": [{"name": name, "count": 1} for name in ("another", "default", "explicit")],
    }


def test_stats_with_no_public_algorithms(tmp_path):
    root = tmp_path / "catalogue"
    write_record(root / "provider" / "record.json", {})
    write_record(root / "provider" / "algorithm" / "records" / "algorithm.json", {
        "properties": {"visibility": "private"},
    })

    stats = catalogue_stats.build_stats(root, top_n=20)

    assert stats["summary"] == {
        "total_providers": 0,
        "total_algorithms": 0,
        "total_platforms": 0,
        "average_algorithms_per_provider": 0.0,
    }
    assert all(not distribution for distribution in stats["distributions"].values())