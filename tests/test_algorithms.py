import re
from pathlib import Path

import pytest

from esa_apex_toolbox.algorithms import (
    Algorithm,
    GithubAlgorithmRepository,
    InvalidMetadataError,
    ServiceLink,
    UdpLink,
)

DATA_ROOT = Path(__file__).parent / "data"


class TestUdpLink:
    def test_from_link_object_basic(self):
        data = {
            "rel": "application",
            "href": "https://esa-apex.test/udp/basic.json",
        }
        link = UdpLink.from_link_object(data)
        assert link.href == "https://esa-apex.test/udp/basic.json"
        assert link.title is None

    def test_from_link_object_with_title(self):
        data = {
            "rel": "application",
            "href": "https://esa-apex.test/udp/basic.json",
            "title": "My basic UDP",
        }
        link = UdpLink.from_link_object(data)
        assert link.href == "https://esa-apex.test/udp/basic.json"
        assert link.title == "My basic UDP"

    def test_from_link_object_missing_rel(self):
        data = {
            "href": "https://esa-apex.test/udp/basic.json",
        }
        with pytest.raises(InvalidMetadataError, match="Missing 'rel' attribute"):
            _ = UdpLink.from_link_object(data)

    def test_from_link_object_wrong_rel(self):
        data = {
            "rel": "self",
            "href": "https://esa-apex.test/udp/basic.json",
        }
        with pytest.raises(InvalidMetadataError, match="Expected link with rel='application'"):
            _ = UdpLink.from_link_object(data)

    def test_from_link_object_no_href(self):
        data = {
            "rel": "application",
        }
        with pytest.raises(InvalidMetadataError, match="Missing 'href' attribute"):
            _ = UdpLink.from_link_object(data)

    def test_from_link_object_wrong_type(self):
        data = {
            "rel": "application",
            "href": "https://esa-apex.test/udp/basic.json",
            "type": "application/xml",
        }
        with pytest.raises(InvalidMetadataError, match="Expected link with type='application/json'"):
            _ = UdpLink.from_link_object(data)


class TestAlgorithm:
    def test_from_ogc_api_record_minimal(self):
        data = {
            "id": "minimal",
            "type": "Feature",
            "conformsTo": ["http://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core"],
            "properties": {
                "type": "service",
            },
            "links": [
                {"rel": "service", "href": "https://openeo.test/"},
            ],
        }
        algorithm = Algorithm.from_ogc_api_record(data)
        assert algorithm.id == "minimal"

    def test_from_ogc_api_record_wrong_type(self):
        data = {
            "id": "wrong",
            "type": "apex_algorithm",
            "conformsTo": ["http://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core"],
        }
        with pytest.raises(
            InvalidMetadataError, match="Expected a GeoJSON 'Feature' object, but got type 'apex_algorithm'."
        ):
            _ = Algorithm.from_ogc_api_record(data)

    def test_from_ogc_api_record_wrong_conform(self):
        data = {
            "id": "wrong",
            "type": "Feature",
            "conformsTo": ["http://nope.test/"],
            "properties": {
                "type": "service",
            },
        }
        with pytest.raises(
            InvalidMetadataError,
            match=re.escape("Expected an 'OGC API - Records' record object, but got ['http://nope.test/']."),
        ):
            _ = Algorithm.from_ogc_api_record(data)

    def test_from_ogc_api_record_wrong_properties_type(self):
        data = {
            "id": "wrong",
            "type": "Feature",
            "conformsTo": ["http://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core"],
            "properties": {
                "type": "udp",
            },
        }
        with pytest.raises(InvalidMetadataError, match="Expected an APEX algorithm object, but got type 'udp'"):
            _ = Algorithm.from_ogc_api_record(data)

    def test_from_ogc_api_record_basic(self):
        data = {
            "id": "basic",
            "type": "Feature",
            "conformsTo": ["http://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core"],
            "properties": {
                "type": "service",
                "title": "Basic",
                "description": "The basics.",
            },
            "links": [
                {
                    "rel": "application",
                    "type": "application/vnd.openeo+json;type=process",
                    "title": "Basic UDP",
                    "href": "https://esa-apex.test/udp/basic.json",
                },
                {
                    "rel": "service",
                    "type": "application/json",
                    "title": "openEO service",
                    "href": "https://openeo.test/",
                },
            ],
        }
        algorithm = Algorithm.from_ogc_api_record(data)
        assert algorithm.id == "basic"
        assert algorithm.title == "Basic"
        assert algorithm.description == "The basics."
        assert algorithm.udp_link == UdpLink(
            href="https://esa-apex.test/udp/basic.json",
            title="Basic UDP",
        )
        assert algorithm.service_links == [ServiceLink(href="https://openeo.test/", title="openEO service")]

    @pytest.mark.parametrize("path_type", [str, Path])
    def test_from_ogc_api_record_path(self, path_type):
        path = path_type(DATA_ROOT / "ogcapi-records/algorithm01.json")
        algorithm = Algorithm.from_ogc_api_record(path)
        assert algorithm.id == "algorithm01"
        assert algorithm.title == "Algorithm One"
        assert algorithm.description == "A first algorithm."
        assert algorithm.udp_link == UdpLink(
            href="https://esa-apex.test/udp/algorithm01.json",
            title="UDP One",
        )
        assert algorithm.service_links == [ServiceLink(href="https://openeo.test/", title="openEO service")]

    def test_from_ogc_api_record_str(self):
        dump = (DATA_ROOT / "ogcapi-records/algorithm01.json").read_text()
        algorithm = Algorithm.from_ogc_api_record(dump)
        assert algorithm.id == "algorithm01"
        assert algorithm.title == "Algorithm One"
        assert algorithm.description == "A first algorithm."
        assert algorithm.udp_link == UdpLink(
            href="https://esa-apex.test/udp/algorithm01.json",
            title="UDP One",
        )
        assert algorithm.service_links == [ServiceLink(href="https://openeo.test/", title="openEO service")]

    def test_from_ogc_api_record_url(self, requests_mock):
        url = "https://esa-apex.test/algorithms/a1.json"
        dump = (DATA_ROOT / "ogcapi-records/algorithm01.json").read_text()
        requests_mock.get(url, text=dump)
        algorithm = Algorithm.from_ogc_api_record(url)
        assert algorithm.id == "algorithm01"
        assert algorithm.title == "Algorithm One"
        assert algorithm.description == "A first algorithm."
        assert algorithm.udp_link == UdpLink(
            href="https://esa-apex.test/udp/algorithm01.json",
            title="UDP One",
        )
        assert algorithm.service_links == [ServiceLink(href="https://openeo.test/", title="openEO service")]


class TestGithubAlgorithmRepository:
    @pytest.fixture
    def repo(self) -> GithubAlgorithmRepository:
        # TODO: avoid depending on an actual GitHub repository. Mock it instead?
        #       Or run this as an integration test?
        #       https://github.com/ESA-APEx/esa-apex-toolbox-python/issues/4
        return GithubAlgorithmRepository(
            owner="ESA-APEx",
            repo="apex_algorithms",
            folder="algorithm_catalog",
        )

    def test_list_algorithms(self, repo):
        listing = repo.list_algorithms()
        assert listing
        assert all(re.fullmatch(r"[a-z0-9_]+", item) for item in listing)

    def test_get_algorithm(self, repo):
        algorithm = repo.get_algorithm("max_ndvi_composite")
        assert algorithm == Algorithm(
            id="max_ndvi_composite",
            title="Max NDVI Composite based on Sentinel-2 data",
            description="A compositing algorithm for Sentinel-2 L2A data, ranking observations by their maximum NDVI. The cost depends on both the area and number of input observations.",
            udp_link=UdpLink(
                href="https://raw.githubusercontent.com/ESA-APEx/apex_algorithms/main/algorithm_catalog/vito/max_ndvi_composite/openeo_udp/max_ndvi_composite.json",
                title="openEO Process Definition",
            ),
            organization="VITO",
            service_links=[
                ServiceLink(
                    href="https://openeofed.dataspace.copernicus.eu",
                    title="CDSE openEO federation",
                )
            ],
        )
