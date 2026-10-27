import re
import sys
from pathlib import Path

import pytest
import requests

from esa_apex_toolbox.algorithms import (
    Algorithm,
    AlgorithmList,
    GithubAlgorithmRepository,
    InvalidMetadataError,
    ServiceLink,
    UdpLink,
)

DATA_ROOT = Path(__file__).parent / "data"


class TestNotebookDisplay:
    @pytest.fixture
    def searchable_algorithms(self):
        return AlgorithmList([
            Algorithm(
                id="forest_monitor", title="Forest Change", provider="VITO",
                platforms=["CDSE federation"], keywords=["Climate", "Land Cover"],
            ),
            Algorithm(id="water", title="Water Quality", provider="Eurac", keywords=["Water"]),
            Algorithm(id="minimal"),
        ])

    @pytest.mark.parametrize("query, expected", [
        ("forest", ["forest_monitor"]),
        ("MONITOR", ["forest_monitor"]),
        ("vItO", ["forest_monitor"]),
        ("FEDERATION", ["forest_monitor"]),
        ("climate", ["forest_monitor"]),
        ("vito land cover", ["forest_monitor"]),
        ("  water   eurac ", ["water"]),
        ("forest water", []),
        ("not specified", []),
        ("", ["forest_monitor", "water", "minimal"]),
        ("   ", ["forest_monitor", "water", "minimal"]),
    ])
    def test_search(self, searchable_algorithms, query, expected):
        from esa_apex_toolbox.notebook import _filter_algorithms

        assert [algorithm.id for algorithm in _filter_algorithms(searchable_algorithms, query)] == expected
        assert len(searchable_algorithms) == 3

    def test_search_widget(self, searchable_algorithms):
        pytest.importorskip("ipywidgets")
        browser = searchable_algorithms.widget()
        search, results = browser.children
        assert "3 algorithms</caption>" in results.value
        search.value = "climate vito"
        assert "1 algorithm</caption>" in results.value
        assert "forest_monitor" in results.value
        assert "Water Quality" not in results.value
        search.value = "no matches"
        assert "No algorithms found" in results.value
        search.value = ""
        assert "3 algorithms</caption>" in results.value
        assert "No algorithms found" in AlgorithmList().widget().children[1].value

    def test_search_widget_missing_dependency(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "ipywidgets", None)
        with pytest.raises(ImportError, match="notebook extra"):
            AlgorithmList().widget()

    def test_algorithm_details(self):
        algorithm = Algorithm(
            id="example", title="Example", description="First line\nSecond line", provider="VITO",
            organization="Research team", platforms=["Backend"], keywords=["Climate"], license="Apache-2.0",
            service_links=[ServiceLink("https://example.test/service", "Service")],
            udp_link=UdpLink("https://example.test/process", "Process definition"),
        )
        html = algorithm._repr_html_()
        values = ["Example", "First line\nSecond line", "VITO", "Research team", "Backend", "Climate", "Apache-2.0"]
        for value in values:
            assert value in html
        assert 'href="https://example.test/service"' in html
        assert 'href="https://example.test/process"' in html
        assert 'rel="noopener noreferrer"' in html

    def test_missing_metadata_and_empty_results(self):
        assert "Not specified" in Algorithm(id="minimal")._repr_html_()
        assert "Not available" in Algorithm(id="minimal")._repr_html_()
        assert "No algorithms found" in AlgorithmList()._repr_html_()

    def test_catalogue_is_still_a_list(self):
        algorithm = Algorithm(id="example", title="Example")
        algorithms = AlgorithmList([algorithm])
        assert isinstance(algorithms, list)
        assert algorithms == [algorithm]
        assert algorithms[0] is algorithm
        assert list(iter(algorithms)) == [algorithm]
        html = algorithms._repr_html_()
        assert "1 algorithm</caption>" in html
        assert "<details>" in html
        assert "<summary>Example</summary>" in html

    @pytest.mark.parametrize("href", ["javascript:alert(1)", "data:text/html,unsafe", "//example.test", "https://["])
    def test_unsafe_links_and_metadata(self, href):
        algorithm = Algorithm(
            id='<script>alert("id")</script>', title="<img src=x onerror=alert(1)>",
            description="<script>alert(1)</script>", provider="<b>provider</b>",
            service_links=[ServiceLink(href, "<img src=x>")], udp_link=UdpLink(href),
        )
        for html in [algorithm._repr_html_(), AlgorithmList([algorithm])._repr_html_()]:
            assert "<script>" not in html
            assert "<img" not in html
            assert "<b>provider</b>" not in html
            assert "<a href=" not in html
            assert "&lt;script&gt;" in html


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
        with pytest.raises(InvalidMetadataError, match="Expected link with type='application/vnd.openeo\+json;type=process' .*"):
            _ = UdpLink.from_link_object(data)


class TestAlgorithm:
    def test_from_ogc_api_record_minimal(self):
        data = {
            "id": "minimal",
            "type": "Feature",
            "conformsTo": ["https://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core"],
            "properties": {
                "type": "service",
            },
            "links": [
                {"rel": "service", "href": "https://openeo.test/"},
            ],
        }
        algorithm = Algorithm.from_ogc_api_record(data)
        assert algorithm.id == "minimal"
        assert algorithm.provider is None
        assert algorithm.platforms == []
        assert algorithm.keywords == []

    def test_discovery_metadata(self):
        data = {
            "id": "discovery",
            "type": "Feature",
            "conformsTo": ["https://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core"],
            "properties": {
                "type": "service",
                "keywords": ["Climate", "Land Cover"],
                "contacts": [{"roles": ["principal investigator"], "organization": "Other organization"}],
            },
            "links": [
                {"rel": "service", "href": "https://openeo.test/"},
                {"rel": "provider", "title": "VITO"},
                {"rel": "platform", "title": "Backend One"},
                {"rel": "platform", "title": "Backend Two"},
                {"rel": "platform"},
            ],
        }
        algorithm = Algorithm.from_ogc_api_record(data)
        assert algorithm.provider == "VITO"
        assert algorithm.organization == "Other organization"
        assert algorithm.platforms == ["Backend One", "Backend Two"]
        assert algorithm.keywords == ["Climate", "Land Cover"]

    def test_application_package_is_not_a_udp(self):
        data = {
            "id": "cwl",
            "type": "Feature",
            "conformsTo": ["https://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core"],
            "properties": {"type": "service"},
            "links": [
                {"rel": "service", "href": "https://processing.test/"},
                {"rel": "application", "type": "application/cwl+yaml", "href": "https://processing.test/app.cwl"},
            ],
        }
        assert Algorithm.from_ogc_api_record(data).udp_link is None
        data["links"].append(
            {"rel": "application", "type": "application/vnd.openeo+json;type=process", "href": "https://openeo.test/udp"}
        )
        assert Algorithm.from_ogc_api_record(data).udp_link == UdpLink(href="https://openeo.test/udp")

    def test_from_ogc_api_record_wrong_type(self):
        data = {
            "id": "wrong",
            "type": "apex_algorithm",
            "conformsTo": ["https://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core"],
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
            "conformsTo": ["https://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core"],
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
            "conformsTo": ["https://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core"],
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
    def repo(self, requests_mock) -> GithubAlgorithmRepository:
        root = "https://api.github.com/repos/ESA-APEx/apex_algorithms/contents/algorithm_catalog"
        requests_mock.get(root, json={"entries": [{"type": "dir", "name": "vito"}]})
        requests_mock.get(
            f"{root}/vito", json={"entries": [{"type": "dir", "name": "max_ndvi_composite"}]}
        )
        record = (
            Path(__file__).parent.parent
            / "algorithm_catalog/vito/max_ndvi_composite/records/max_ndvi_composite.json"
        )
        requests_mock.get(
            "https://raw.githubusercontent.com/ESA-APEx/apex_algorithms/main/"
            "algorithm_catalog/vito/max_ndvi_composite/records/max_ndvi_composite.json",
            text=record.read_text(),
        )
        return GithubAlgorithmRepository(
            owner="ESA-APEx",
            repo="apex_algorithms",
            folder="algorithm_catalog",
        )

    def test_list_algorithms(self, repo):
        listing = repo.list_algorithms()
        assert listing
        assert all(re.fullmatch(r"[a-zA-Z0-9_-]+", item) for item in listing)

    @pytest.mark.parametrize("token", [None, "test-token"])
    def test_api_authentication(self, repo, requests_mock, token):
        history_start = len(requests_mock.request_history)
        authenticated_repo = GithubAlgorithmRepository(
            owner="ESA-APEx", repo="apex_algorithms", folder="algorithm_catalog", token=token
        )
        assert authenticated_repo.get_algorithm("max_ndvi_composite").id == "max_ndvi_composite"

        history = requests_mock.request_history[history_start:]
        assert len(history) == 3
        for request in history[:2]:
            assert request.headers.get("Authorization") == (f"Bearer {token}" if token else None)
            assert request.headers["Accept"] == "application/vnd.github.object+json"
            assert request.qs == {"ref": ["main"]}
        assert "Authorization" not in history[2].headers

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
            provider="VITO",
            platforms=["CDSE openEO federation"],
            keywords=["Vegetation", "Normalized Difference Vegetation Index (NDVI)", "Sentinel-2"],
            service_links=[
                ServiceLink(
                    href="https://openeofed.dataspace.copernicus.eu",
                    title="CDSE openEO federation",
                )
            ],
        )


class TestGithubAlgorithmDiscovery:
    @pytest.fixture
    def repo(self, requests_mock):
        root = "https://api.github.com/repos/test/catalog/contents/algorithm_catalog"
        requests_mock.get(root, json={"entries": [{"type": "dir", "name": "folder"}]})
        requests_mock.get(
            f"{root}/folder",
            json={"entries": [{"type": "dir", "name": name} for name in ["first", "second", "missing"]]},
        )
        for name, provider, platforms, keywords in [
            ("first", "VITO", ["Backend One", "Backend Two"], ["Climate", "Land Cover"]),
            ("second", "Eurac Research", ["Backend Two"], ["Climate"]),
            ("missing", None, [], []),
        ]:
            record = {
                "id": name,
                "type": "Feature",
                "conformsTo": ["https://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core"],
                "properties": {"type": "service", "title": name.title(), "description": f"About {name}."},
                "links": [{"rel": "service", "href": "https://openeo.test/"}],
            }
            if provider:
                record["links"].append({"rel": "provider", "title": provider})
                record["links"].extend({"rel": "platform", "title": platform} for platform in platforms)
                record["properties"]["keywords"] = keywords
            requests_mock.get(
                f"https://raw.githubusercontent.com/test/catalog/custom/algorithm_catalog/folder/{name}/records/{name}.json",
                json=record,
            )
        return GithubAlgorithmRepository("test", "catalog", folder="algorithm_catalog", branch="custom")

    def test_default_ids_without_record_downloads(self, repo, requests_mock):
        assert repo.list_algorithms() == ["first", "second", "missing"]
        assert requests_mock.call_count == 2
        assert repo.list_algorithms() == ["first", "second", "missing"]
        assert requests_mock.call_count == 2
        assert all(request.qs == {"ref": ["custom"]} for request in requests_mock.request_history)

    @pytest.mark.parametrize("details", [False, True])
    @pytest.mark.parametrize(
        "filters, expected",
        [
            ({}, ["first", "second", "missing"]),
            ({"provider": "vItO"}, ["first"]),
            ({"provider": ["unknown", "EURAC RESEARCH"]}, ["second"]),
            ({"provider": "folder"}, []),
            ({"provider": "VIT"}, []),
            ({"platform": "BACKEND TWO"}, ["first", "second"]),
            ({"platform": ["unknown", "backend one"]}, ["first"]),
            ({"keywords": "CLIMATE"}, ["first", "second"]),
            ({"keywords": ["climate", "LAND COVER"]}, ["first"]),
            ({"keywords": "Land"}, []),
            ({"provider": "VITO", "platform": "backend two", "keywords": ["climate"]}, ["first"]),
            ({"provider": "VITO", "platform": "unknown", "keywords": "Climate"}, []),
            ({"keywords": ["Climate", "unknown"]}, []),
            ({"provider": []}, []),
            ({"platform": []}, []),
            ({"keywords": []}, ["first", "second", "missing"]),
        ],
    )
    def test_filters(self, repo, filters, expected, details):
        result = repo.list_algorithms(**filters, details=details)
        ids = [a.id for a in result] if details else result
        assert ids == expected

    def test_details(self, repo):
        algorithms = repo.list_algorithms(details=True)
        assert isinstance(algorithms, AlgorithmList)
        assert "3 algorithms</caption>" in algorithms._repr_html_()
        assert type(repo.list_algorithms()) is list
        assert type(repo.list_algorithms(provider="VITO")) is list
        first, second, missing = repo.list_algorithms(details=True)
        assert first.id == "first"
        assert first.title == "First"
        assert first.description == "About first."
        assert first.provider == "VITO"
        assert first.organization is None
        assert first.platforms == ["Backend One", "Backend Two"]
        assert first.keywords == ["Climate", "Land Cover"]
        assert second.provider == "Eurac Research"
        assert missing.provider is None
        assert missing.platforms == []
        assert missing.keywords == []

    def test_cache_and_discovery_helpers(self, repo, requests_mock):
        first = repo.get_algorithm("first")
        assert requests_mock.call_count == 3
        algorithms = repo.list_algorithms(details=True)
        assert requests_mock.call_count == 5
        assert algorithms[0] is first
        assert repo.get_algorithm("first") is first
        assert repo.list_algorithms(provider="VITO") == ["first"]
        assert repo.list_algorithms(details=True) == algorithms
        assert repo.list_providers() == ["Eurac Research", "VITO"]
        assert repo.list_platforms() == ["Backend One", "Backend Two"]
        assert repo.list_keywords() == ["Climate", "Land Cover"]
        assert requests_mock.call_count == 5

    def test_unknown_algorithm(self, repo, requests_mock):
        with pytest.raises(ValueError, match="not found"):
            repo.get_algorithm("unknown")
        assert requests_mock.call_count == 2

    def test_discovery_skips_directories_without_records(self, repo, requests_mock):
        root = "https://api.github.com/repos/test/catalog/contents/algorithm_catalog"
        requests_mock.get(
            f"{root}/folder",
            json={"entries": [{"type": "dir", "name": name} for name in ["first", "second", "missing", "images"]]},
        )
        url = (
            "https://raw.githubusercontent.com/test/catalog/custom/"
            "algorithm_catalog/folder/images/records/images.json"
        )
        requests_mock.get(url, status_code=404)

        assert repo.list_algorithms() == ["first", "second", "missing", "images"]
        assert [algorithm.id for algorithm in repo.list_algorithms(details=True)] == ["first", "second", "missing"]
        assert repo.list_algorithms(provider="VITO") == ["first"]
        assert repo.list_providers() == ["Eurac Research", "VITO"]
        assert repo.list_platforms() == ["Backend One", "Backend Two"]
        assert repo.list_keywords() == ["Climate", "Land Cover"]
        with pytest.raises(requests.HTTPError):
            repo.get_algorithm("images")

    @pytest.mark.parametrize("status_code", [403, 503])
    def test_discovery_propagates_http_errors(self, repo, requests_mock, status_code):
        requests_mock.get(
            "https://raw.githubusercontent.com/test/catalog/custom/"
            "algorithm_catalog/folder/first/records/first.json",
            status_code=status_code,
        )
        with pytest.raises(requests.HTTPError):
            repo.list_providers()

    def test_failed_record_is_not_cached(self, repo, requests_mock):
        url = (
            "https://raw.githubusercontent.com/test/catalog/custom/"
            "algorithm_catalog/folder/first/records/first.json"
        )
        record = {
            "id": "first",
            "type": "Feature",
            "conformsTo": ["https://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core"],
            "properties": {"type": "service"},
            "links": [{"rel": "service", "href": "https://openeo.test/"}],
        }
        requests_mock.get(url, [{"status_code": 503}, {"json": record}])
        with pytest.raises(requests.HTTPError):
            repo.get_algorithm("first")
        assert repo.get_algorithm("first").id == "first"
