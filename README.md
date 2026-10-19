# APEx Algorithm Services Catalog

## Overview

This repository serves as a catalog for APEx compliant algorithms that are available as on-demand services on various cloud platforms. It collects and maintains metadata about these services, making them discoverable via the [APEx Algorithm Catalogue](https://algorithm-catalogue.apex.esa.int/).

For more information about the concepts and architecture used in this repository, please refer to the [documentation](https://esa-apex.github.io/apex_algorithms/).

## Discover algorithms with Python

For a step-by-step walkthrough, open the [example notebook](examples/esa_apex_toolbox.ipynb).

```python
from esa_apex_toolbox.algorithms import GithubAlgorithmRepository

repo = GithubAlgorithmRepository(
    owner="ESA-APEx", repo="apex_algorithms", folder="algorithm_catalog"
)

ids = repo.list_algorithms()  # Backwards-compatible list of folder IDs.
vito_ids = repo.list_algorithms(provider="VITO")

for algo in repo.list_algorithms(
    platform="Copernicus Data Space openEO Backend",
    keywords=["Climate"],
    details=True,
):
    print(algo.id, "|", algo.provider, "|", algo.title)
    print(algo.description, algo.platforms, algo.keywords)

# Discover available filter values (sorted, unique strings).
print(repo.list_providers())
print(repo.list_platforms())
print(repo.list_keywords())
```

Filters work with or without `details=True` and combine with AND. All matches
are case-insensitive and exact (not substring matches). A `provider` or `platform`
list matches **any** supplied title; a `keywords` list requires **all** supplied
keywords. An empty provider/platform list matches nothing; an empty keyword list
places no restriction on results.

Providers and platforms come from the record's `rel="provider"` and
`rel="platform"` link titles, not folder names or investigator contacts.
Missing metadata is represented by `provider=None`, `platforms=[]`, and
`keywords=[]`.

Unfiltered ID listing only reads directory listings. Filtering, detailed results,
and discovery helpers fetch records from raw GitHub URLs in parallel (up to eight
downloads), avoiding a GitHub API request per record. Directory discovery still
uses the GitHub API and is subject to its rate limits. Listings and successfully
parsed records are cached on the repository instance, including records loaded
by `get_algorithm()`. Reuse the instance to avoid downloads; create a new one
to refresh the catalog.

Unfiltered ID listing may include auxiliary directories without records.
Filtering, detailed results, and discovery helpers skip record URLs that return
HTTP 404 and log a warning. Other HTTP errors and invalid records still raise
errors, as do direct `get_algorithm()` calls for missing records.

## Contributing

We welcome contributions! To add new algorithms or improve existing records, please follow these steps:

1. Fork the repository.
2. Create a new branch for your changes.
3. Add or update algorithm metadata as needed.
4. Submit a Pull Request (PR) describing your changes.

All PRs will be reviewed by the APEx team before merging. Once your PR is merged, the changes will become visible in the [APEx Algorithm Catalogue](https://algorithm-catalogue.apex.esa.int/).

Please ensure your contributions comply with APEx standards and include sufficient metadata for cataloguing.
