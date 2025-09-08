from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import List, Optional, Union

import requests


class LINK_REL:
    UDP = "application"
    SERVICE = "service"


def _load_json_resource(src: Union[dict, str, Path]) -> dict:
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
        elif src.startswith("http://") or src.startswith("https://"):
            # Assume the string is a URL to a JSON resource
            resp = requests.get(src)
            resp.raise_for_status()
            return resp.json()
        else:
            # Assume the string is a file path
            return _load_json_resource(Path(src))
    else:
        # TODO: support bytes, file-like objects, etc.
        raise ValueError(f"Unsupported JSON resource type {type(src)}")


class InvalidMetadataError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class UdpLink:
    href: str
    title: Optional[str] = None

    @classmethod
    def from_link_object(cls, data: dict) -> UdpLink:
        """Parse a link object (dict/mapping) into a UdpLink object."""
        if "rel" not in data:
            raise InvalidMetadataError("Missing 'rel' attribute in link object")
        if data["rel"] != LINK_REL.UDP:
            raise InvalidMetadataError(f"Expected link with rel='{LINK_REL.UDP}' but got {data['rel']!r}")
        if "type" in data and data["type"] != "application/vnd.openeo+json;type=process":
            raise InvalidMetadataError(f"Expected link with type='application/vnd.openeo+json;type=process' but got {data['type']!r}")
        if "href" not in data:
            raise InvalidMetadataError("Missing 'href' attribute in link object")
        return cls(
            href=data["href"],
            title=data.get("title"),
        )


@dataclasses.dataclass(frozen=True)
class ServiceLink:
    href: str
    title: Optional[str] = None

    @classmethod
    def from_link_object(cls, data: dict) -> ServiceLink:
        """Parse a link object (dict/mapping) into a UdpLink object."""
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
    title: Optional[str] = None
    description: Optional[str] = None
    udp_link: Optional[UdpLink] = None
    service_links: List[ServiceLink] = None
    license: Optional[str] = None
    organization: Optional[str] = None
    # TODO more fields

    @classmethod
    def from_ogc_api_record(cls, src: Union[dict, str, Path]) -> Algorithm:
        """
        Load an algorithm from an 'OGC API - Records' record object, specified
        as a dict, a JSON string, a file path, or a URL.
        """
        data = _load_json_resource(src)

        if not data.get("type") == "Feature":
            raise InvalidMetadataError(f"Expected a GeoJSON 'Feature' object, but got type {data.get('type')!r}.")
        if "http://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core" not in data.get("conformsTo", []):
            raise InvalidMetadataError(
                f"Expected an 'OGC API - Records' record object, but got {data.get('conformsTo')!r}."
            )

        properties = data.get("properties", {})
        if properties.get("type") != "service":
            raise InvalidMetadataError(f"Expected an APEX algorithm object, but got type {properties.get('type')!r}.")

        links = data.get("links", [])
        udp_links = [UdpLink.from_link_object(link) for link in links if link.get("rel") == LINK_REL.UDP]
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
        )


class GithubAlgorithmRepository:
    """
    GitHub based algorithm repository.
    """

    # TODO: caching

    def __init__(self, owner: str, repo: str, folder: str = "", branch: str = "main"):
        self.owner = owner
        self.repo = repo
        self.folder = folder
        self.branch = branch
        self._session = requests.Session()
        self._organizations = list(self._list_organizations())
        self._algorithms = None


    def _list_organizations(self):
        org_listing, url = self._get_listing()
        for item in org_listing["entries"]:
            if item["type"] == "dir" :
                yield item['name']

    def _list_algorithms(self, organization):
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{self.folder}/{organization}".strip("/")
        org_listing, url = self._get_listing(url)
        for item in org_listing["entries"]:
            if item["type"] == "dir" :
                yield item['name']




    def _list_files(self,url = None):
        listing, url = self._get_listing(url)
        assert listing["type"] == "dir"
        for item in listing["entries"]:
            if item["type"] == "file" and item["name"].endswith(".json"):
                yield item
            if item["type"] == "dir":
                # Recursively list files in organization subdirectories
                subfolder = f"{url}/{item['name']}"
                for subitem in self._list_files(url = subfolder):
                    yield subitem

    def _get_listing(self, url=None):
        if url is None:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{self.folder}".strip("/")
        resp = self._session.get(url, headers={"Accept": "application/vnd.github.object+json"})
        resp.raise_for_status()
        listing = resp.json()
        return listing, url

    def list_algorithms(self) -> List[str]:
        # TODO: method to list names vs method to list parsed Algorithm objects?
        if self._algorithms is None:
            self._algorithms = {org: list(self._list_algorithms(org)) for org in self._organizations}
        return [ algorithm_name for algos in self._algorithms.values() for algorithm_name in algos]

    def get_algorithm(self, name: str) -> Algorithm:
        # TODO: get url from listing from API request, instead of hardcoding this raw url?
        all_algos = self.list_algorithms()
        orgs = [ org for org, algos in self._algorithms.items() if name in algos]
        if len(orgs) != 1:
            raise ValueError(f"Algorithm {name!r} not found in {all_algos}")
        url = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/{self.branch}/{self.folder}/{orgs[0]}/{name}/records/{name}.json"
        # TODO: how to make sure GitHub URL is requested with additional headers?
        return Algorithm.from_ogc_api_record(url)
