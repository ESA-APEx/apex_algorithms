from __future__ import annotations

import dataclasses
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests


class LINK_REL:
    UDP = "application"
    SERVICE = "service"


def _load_json_resource(src: dict | str | Path) -> dict:
    """Load a JSON resource from a file or a string."""
    if isinstance(src, dict):
        return src
    elif isinstance(src, Path):
        with open(src, "r", encoding="utf8") as f:
            return json.load(f)
    elif isinstance(src, str):
        if src.strip().startswith("{"):
            # Assume the string is JSON payload
            return json.loads(src)
        elif src.startswith(("http://", "https://")):
            # Assume the string is a URL to a JSON resource
            resp = requests.get(src)
            resp.raise_for_status()
            return resp.json()
        else:
            # Assume the string is a file path
            return _load_json_resource(Path(src))
    else:
        # TODO: support bytes, file-like objects, etc.
        raise TypeError(f"Unsupported JSON resource type {type(src)}")


def write_json(json_object: object, file_path: str | Path) -> None:
    with open(Path(file_path), "w") as f:
        j_str = json.dumps(json_object, indent=2)
        if not j_str.endswith("\n"):
            j_str += "\n"
        f.write(j_str)


class InvalidMetadataError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class UdpLink:
    href: str
    title: str | None = None

    @classmethod
    def from_link_object(cls, data: dict) -> UdpLink:
        """Parse a link object (dict/mapping) into a UdpLink object."""
        if "rel" not in data:
            raise InvalidMetadataError("Missing 'rel' attribute in link object")
        if data["rel"] != LINK_REL.UDP:
            raise InvalidMetadataError(f"Expected link with rel='{LINK_REL.UDP}' but got {data['rel']!r}")
        if "type" in data and data["type"] != "application/vnd.openeo+json;type=process":
            raise InvalidMetadataError(
                f"Expected link with type='application/vnd.openeo+json;type=process' but got {data['type']!r}"
            )
        if "href" not in data:
            raise InvalidMetadataError("Missing 'href' attribute in link object")
        return cls(
            href=data["href"],
            title=data.get("title"),
        )


@dataclasses.dataclass(frozen=True)
class ServiceLink:
    href: str
    title: str | None = None

    @classmethod
    def from_link_object(cls, data: dict) -> ServiceLink:
        """Parse a link object (dict/mapping) into a ServiceLink object."""
        if "rel" not in data:
            raise InvalidMetadataError("Missing 'rel' attribute in link object")
        if data["rel"] != LINK_REL.SERVICE:
            raise InvalidMetadataError(f"Expected link with rel='{LINK_REL.SERVICE}' but got {data['rel']!r}")
        if "href" not in data:
            raise InvalidMetadataError("Missing 'href' attribute in link object")
        return cls(
            href=data["href"],
            title=data.get("title"),
        )

    def __str__(self):
        return self.title or self.href


@dataclasses.dataclass(frozen=True)
class Algorithm:
    id: str
    title: str | None = None
    description: str | None = None
    udp_link: UdpLink | None = None
    service_links: list[ServiceLink] | None = None
    license: str | None = None
    organization: str | None = None
    provider: str | None = None
    platforms: list[str] = dataclasses.field(default_factory=list)
    keywords: list[str] = dataclasses.field(default_factory=list)

    def _repr_html_(self) -> str:
        from esa_apex_toolbox.notebook import algorithm_html

        return algorithm_html(self)

    @classmethod
    def from_ogc_api_record(cls, src: dict | str | Path) -> Algorithm:
        """
        Load an algorithm from an 'OGC API - Records' record object, specified
        as a dict, a JSON string, a file path, or a URL.
        """
        data = _load_json_resource(src)

        if not data.get("type") == "Feature":
            raise InvalidMetadataError(f"Expected a GeoJSON 'Feature' object, but got type {data.get('type')!r}.")
        data_conforms_to = data.get("conformsTo", [])
        # TODO: Remove http reference once merged to main
        if ("https://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core" not in data_conforms_to) and (
            "https://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core" not in data_conforms_to
        ):
            raise InvalidMetadataError(
                f"Expected an 'OGC API - Records' record object, but got {data.get('conformsTo')!r}."
            )

        properties = data.get("properties", {})
        if properties.get("type") != "service":
            raise InvalidMetadataError(f"Expected an APEX algorithm object, but got type {properties.get('type')!r}.")

        links = data.get("links", [])
        udp_links = [
            UdpLink.from_link_object(link)
            for link in links
            if link.get("rel") == LINK_REL.UDP
            and link.get("type", "application/vnd.openeo+json;type=process")
            == "application/vnd.openeo+json;type=process"
        ]
        if len(udp_links) > 1:
            raise InvalidMetadataError("Multiple UDP links found")
        # TODO: is having a UDP link a requirement? => No, it can also be an application package
        udp_link = udp_links[0] if udp_links else None

        service_links = [ServiceLink.from_link_object(link) for link in links if link.get("rel") == LINK_REL.SERVICE]
        if len(service_links) == 0:
            raise InvalidMetadataError(
                "No service links found, the algorithm requires at least one valid service that is known to execute it."
            )

        pis = [c for c in properties.get("contacts", []) if "principal investigator" in c.get("roles", [])]
        pi_org = pis[0].get("organization", None) if pis else None

        service_license = data.get("license", None)
        return cls(
            id=data["id"],
            title=properties.get("title"),
            description=properties.get("description"),
            udp_link=udp_link,
            service_links=service_links,
            license=service_license,
            organization=pi_org,
            provider=next(
                (link["title"] for link in links if link.get("rel") == "provider" and link.get("title")), None
            ),
            platforms=[link["title"] for link in links if link.get("rel") == "platform" and link.get("title")],
            keywords=properties.get("keywords") or [],
        )


class AlgorithmList(list):
    """A list of algorithms with an expandable HTML representation in notebooks."""

    def widget(self):
        """Build a searchable notebook browser with the optional notebook dependencies."""
        from esa_apex_toolbox.notebook import algorithm_browser

        return algorithm_browser(self)

    def _repr_html_(self) -> str:
        from esa_apex_toolbox.notebook import algorithms_html

        return algorithms_html(self)


class GithubAlgorithmRepository:
    """
    GitHub based algorithm repository.
    """

    def __init__(self, owner: str, repo: str, folder: str = "", branch: str = "main", *, token: str | None = None):
        self.owner = owner
        self.repo = repo
        self.folder = folder
        self.branch = branch
        self._session = requests.Session()
        if token:
            self._session.headers["Authorization"] = f"Bearer {token}"
        self._organizations = list(self._list_organizations())
        self._algorithms: dict | None = None
        self._record_cache: dict[str, Algorithm] = {}

    def _list_organizations(self):
        org_listing, _url = self._get_listing()
        for item in org_listing["entries"]:
            if item["type"] == "dir":
                yield item["name"]

    def _list_algorithms(self, organization):
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{self.folder}/{organization}".strip("/")
        org_listing, url = self._get_listing(url)
        for item in org_listing["entries"]:
            if item["type"] == "dir":
                yield item["name"]

    def _list_files(self, url=None):
        listing, url = self._get_listing(url)
        assert listing["type"] == "dir"
        for item in listing["entries"]:
            if item["type"] == "file" and item["name"].endswith(".json"):
                yield item
            if item["type"] == "dir":
                # Recursively list files in organization subdirectories
                subfolder = f"{url}/{item['name']}"
                yield from self._list_files(url=subfolder)

    def _get_listing(self, url=None):
        if url is None:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{self.folder}".strip("/")
        resp = self._session.get(
            url, headers={"Accept": "application/vnd.github.object+json"}, params={"ref": self.branch}
        )
        resp.raise_for_status()
        listing = resp.json()
        return listing, url

    def list_algorithms(
        self,
        *,
        provider: str | list[str] | None = None,
        platform: str | list[str] | None = None,
        keywords: str | list[str] | None = None,
        details: bool = False,
    ) -> list[str] | list[Algorithm]:
        """List folder IDs, or parsed records with ``details=True``.

        Filters are case-insensitive exact matches, combined with AND. Provider
        and platform lists match any value; keyword lists require all values.
        Listings and records are cached for this repository instance's lifetime.
        Metadata discovery skips missing records (HTTP 404) with a warning.
        """
        if self._algorithms is None:
            self._algorithms = {org: list(self._list_algorithms(org)) for org in self._organizations}
        names = [algorithm_name for algos in self._algorithms.values() for algorithm_name in algos]
        if not details and provider is None and platform is None and keywords is None:
            return names

        def normalize(value):
            if value is None:
                return None
            return {item.casefold() for item in ([value] if isinstance(value, str) else value)}

        providers, platforms, required_keywords = map(normalize, (provider, platform, keywords))

        def load_algorithm(name: str) -> Algorithm | None:
            try:
                return self.get_algorithm(name)
            except requests.HTTPError as error:
                if error.response is None or error.response.status_code != 404:
                    raise       
                return None

        with ThreadPoolExecutor(max_workers=8) as executor:
            algorithms = list(executor.map(load_algorithm, names))
        matches = [
            algorithm if details else name
            for name, algorithm in zip(names, algorithms)
            if algorithm is not None
            and (providers is None or (algorithm.provider is not None and algorithm.provider.casefold() in providers))
            and (platforms is None or platforms.intersection(p.casefold() for p in algorithm.platforms))
            and (required_keywords is None or required_keywords.issubset(k.casefold() for k in algorithm.keywords))
        ]
        return AlgorithmList(matches) if details else matches

    def list_providers(self) -> list[str]:
        """Return sorted, unique provider titles from cached catalog records."""
        return sorted({a.provider for a in self.list_algorithms(details=True) if a.provider})

    def list_platforms(self) -> list[str]:
        """Return sorted, unique platform titles from cached catalog records."""
        return sorted({p for a in self.list_algorithms(details=True) for p in a.platforms})

    def list_keywords(self) -> list[str]:
        """Return sorted, unique keywords from cached catalog records."""
        return sorted({k for a in self.list_algorithms(details=True) for k in a.keywords})

    def get_algorithm(self, name: str) -> Algorithm:
        if name in self._record_cache:
            return self._record_cache[name]
        # TODO: get url from listing from API request, instead of hardcoding this raw url?
        all_algos = self.list_algorithms()
        orgs = [org for org, algos in self._algorithms.items() if name in algos]
        if len(orgs) != 1:
            raise ValueError(f"Algorithm {name!r} not found in {all_algos}")
        url = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/{self.branch}/{self.folder}/{orgs[0]}/{name}/records/{name}.json"
        # TODO: how to make sure GitHub URL is requested with additional headers?
        algorithm = Algorithm.from_ogc_api_record(url)
        self._record_cache[name] = algorithm
        return algorithm
