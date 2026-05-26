#!/usr/bin/env python3
"""Generate dashboard statistics for the APEx algorithm catalog."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Generate JSON statistics from algorithm_catalog records.",
	)
	parser.add_argument(
		"--catalog-root",
		type=Path,
		default=Path("algorithm_catalog"),
		help="Path to the algorithm catalog root directory.",
	)
	parser.add_argument(
		"--output",
		type=Path,
		required=True,
		help="Path to the generated JSON output file.",
	)
	parser.add_argument(
		"--top-n",
		type=int,
		default=20,
		help="Top N values to keep for keyword/theme/platform distributions.",
	)
	return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
	with path.open("r", encoding="utf-8") as handle:
		data = json.load(handle)
	if not isinstance(data, dict):
		raise ValueError(f"Expected JSON object in {path}")
	return data


def counter_to_sorted_list(counter: Counter[str], limit: int | None = None) -> list[dict[str, Any]]:
	items = sorted(counter.items(), key=lambda item: (-item[1], item[0].lower()))
	if limit is not None:
		items = items[:limit]
	return [{"name": name, "count": count} for name, count in items]


def get_algorithm_record_paths(provider_dir: Path) -> list[Path]:
	paths = list(provider_dir.glob("*/records/*.json"))
	return sorted(path for path in paths if path.name != "record.json")


def normalize_interface(conforms_to: Any) -> list[str]:
	if not isinstance(conforms_to, list):
		return []

	interfaces: list[str] = []
	for value in conforms_to:
		if not isinstance(value, str):
			continue
		if "openeo-udp" in value:
			interfaces.append("openEO UDP")
		elif "ogc-api-processes" in value:
			interfaces.append("OGC API - Processes")
	# Preserve order while deduplicating.
	return list(dict.fromkeys(interfaces))


def resolve_platform_title(platform_path: Path) -> str | None:
	if not platform_path.exists() or not platform_path.is_file():
		return None
	try:
		platform_record = load_json(platform_path)
	except Exception:
		return None
	properties = platform_record.get("properties", {})
	if not isinstance(properties, dict):
		return None
	title = properties.get("title")
	if isinstance(title, str) and title.strip():
		return title.strip()
	return None


def extract_platform_names(links: Any, algorithm_record_path: Path, platform_title_cache: dict[str, str]) -> list[str]:
	if not isinstance(links, list):
		return []

	platforms: list[str] = []
	for link in links:
		if not isinstance(link, dict):
			continue
		if link.get("rel") != "platform":
			continue

		href = link.get("href")
		if not isinstance(href, str) or not href.strip():
			continue

		parsed = urlparse(href)
		if parsed.scheme or parsed.netloc:
			# Remote links cannot be resolved from the local workspace.
			continue

		candidate_path = (algorithm_record_path.parent / href).resolve()
		cache_key = str(candidate_path)
		if cache_key in platform_title_cache:
			platforms.append(platform_title_cache[cache_key])
			continue

		resolved_title = resolve_platform_title(candidate_path)
		if resolved_title is not None:
			platform_title_cache[cache_key] = resolved_title
			platforms.append(resolved_title)

	return list(dict.fromkeys(platforms))


def has_rel(links: Any, rel_name: str) -> bool:
	if not isinstance(links, list):
		return False
	return any(isinstance(link, dict) and link.get("rel") == rel_name for link in links)


def is_private_service(properties: dict[str, Any]) -> bool:
	visibility = properties.get("visibility")
	return isinstance(visibility, str) and visibility.strip().lower() == "private"


def build_stats(catalog_root: Path, top_n: int) -> dict[str, Any]:
	provider_record_paths = sorted(catalog_root.glob("*/record.json"))

	provider_counter: Counter[str] = Counter()
	platform_counter: Counter[str] = Counter()
	interface_counter: Counter[str] = Counter()
	keyword_counter: Counter[str] = Counter()
	providers: list[dict[str, Any]] = []
	platform_title_cache: dict[str, str] = {}

	for provider_record_path in provider_record_paths:
		provider_dir = provider_record_path.parent
		provider_slug = provider_dir.name
		provider_record = load_json(provider_record_path)
		provider_title = (
			provider_record.get("properties", {}).get("title")
			if isinstance(provider_record.get("properties"), dict)
			else None
		)
		provider_name = provider_title if isinstance(provider_title, str) and provider_title.strip() else provider_slug

		algorithm_paths = get_algorithm_record_paths(provider_dir)
		public_algorithm_count = 0

		for algorithm_path in algorithm_paths:
			algorithm_record = load_json(algorithm_path)
			properties = algorithm_record.get("properties", {})
			links = algorithm_record.get("links", [])

			if not isinstance(properties, dict):
				properties = {}
			if not isinstance(links, list):
				links = []
			if is_private_service(properties):
				continue

			keywords = [item for item in properties.get("keywords", []) if isinstance(item, str) and item.strip()]

			interfaces = normalize_interface(algorithm_record.get("conformsTo", []))
			platforms = extract_platform_names(links, algorithm_path, platform_title_cache)

			public_algorithm_count += 1
			provider_counter[provider_name] += 1
			for platform in platforms:
				platform_counter[platform] += 1
			for interface in interfaces:
				interface_counter[interface] += 1
			for keyword in keywords:
				keyword_counter[keyword] += 1

		providers.append({"id": provider_slug, "name": provider_name, "algorithm_count": public_algorithm_count})
	total_algorithms = sum(provider_counter.values())
	total_providers = len(providers)
	total_platforms = len(platform_counter)

	return {
		"meta": {
			"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
			"catalog_root": str(catalog_root.as_posix()),
			"generator": ".github/scripts/generate_catalogue_stats.py",
			"top_n": top_n,
		},
		"summary": {
			"total_providers": total_providers,
			"total_algorithms": total_algorithms,
			"total_platforms": total_platforms,
			"average_algorithms_per_provider": round(total_algorithms / total_providers, 2) if total_providers else 0.0,
		},
		"distributions": {
			"algorithms_by_provider": counter_to_sorted_list(provider_counter),
			"algorithms_by_interface": counter_to_sorted_list(interface_counter),
			"algorithms_by_platform": counter_to_sorted_list(platform_counter, limit=top_n),
			"top_keywords": counter_to_sorted_list(keyword_counter, limit=top_n),
		},
	}


def main() -> None:
	args = parse_args()
	catalog_root = args.catalog_root.resolve()
	output_path = args.output.resolve()

	if not catalog_root.exists():
		raise FileNotFoundError(f"Catalog root not found: {catalog_root}")

	stats = build_stats(catalog_root=catalog_root, top_n=args.top_n)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	with output_path.open("w", encoding="utf-8") as handle:
		json.dump(stats, handle, indent=2, sort_keys=False)
		handle.write("\n")


if __name__ == "__main__":
	main()
