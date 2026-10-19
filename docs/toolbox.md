---
title: Python Toolbox
---

The `esa_apex_toolbox` Python package provides programmatic access to the
[APEx Algorithm Catalogue](https://algorithm-catalogue.apex.esa.int/). Use it to
discover algorithms, filter their metadata, and find service endpoints and
openEO process definitions. It does not itself process satellite imagery or
submit processing jobs.

For an interactive walkthrough, open the
[example notebook on GitHub](https://github.com/ESA-APEx/apex_algorithms/blob/main/examples/esa_apex_toolbox.ipynb).
After cloning the repository, open `examples/esa_apex_toolbox.ipynb` in VS Code
or Jupyter and select your Python environment as the kernel.

## Installation

Install the toolbox from a checkout to use the APIs documented here:

```bash
git clone https://github.com/ESA-APEx/apex_algorithms.git
cd apex_algorithms
python -m pip install -e .
```

The distribution name is `esa-apex-algorithms`; the Python import name is
`esa_apex_toolbox`. Catalogue discovery requires internet access, but no
credentials are needed to read this public repository.

## Connect to the Catalogue

```python
import os

from esa_apex_toolbox.algorithms import Algorithm, GithubAlgorithmRepository

repo = GithubAlgorithmRepository(
    owner="ESA-APEx",
    repo="apex_algorithms",
    folder="algorithm_catalog",
    branch="main",
    token=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"),
)

algorithm_ids = repo.list_algorithms()
print(algorithm_ids[:10])
```

`list_algorithms()` returns folder IDs by default, which can include auxiliary
directories without algorithm records. Set `branch` to another
branch or revision to read that version of the catalogue. Repository access
reads remote GitHub content, not local catalogue changes.

## GitHub Authentication

### Why Use a Token?

A token is optional for the public APEx catalogue, but helps avoid
`403 rate limit exceeded` errors. GitHub normally allows **60 unauthenticated
REST API requests per hour per IP address**, shared with other users and tools
on that IP. Directory discovery uses this API, so repeatedly creating repository
instances or rerunning the notebook can exhaust the allowance.

Authenticating with a personal access token normally raises the primary limit
to **5,000 requests per hour per user**, shared with other authenticated
applications. It does not remove rate limits or authenticate you to an openEO
backend. Reuse a repository instance to benefit from its cache. See
[GitHub's rate-limit documentation](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
for details and exceptions.

### Create a Token

For this public catalogue, use a fine-grained personal access token with the
minimum access needed:

1. Sign in to GitHub and open **Settings > Developer settings > Personal access tokens > Fine-grained tokens**, then **Generate new token**. You can also open the [token creation page](https://github.com/settings/personal-access-tokens/new) directly.
2. Choose a descriptive name, such as `APEx catalogue`, and a short expiration appropriate for your work.
3. Keep your own account as the **Resource owner** and select **Public repositories** under **Repository access**. Public read-only access is included; you do not need membership in `ESA-APEx`.
4. Leave additional repository and account permissions unset. Reading this public catalogue does not require private-repository access or write permissions.
5. Select **Generate token** and keep the value in a password manager or secret store. GitHub only shows the token value when it is created.

See [GitHub's token creation instructions](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-fine-grained-personal-access-token)
for the current settings and security guidance.

### Use the Token Safely

The connection example above explicitly reads `GITHUB_TOKEN`, falling back to
`GH_TOKEN`, from the Python process's environment and passes it as `token=`.
The repository class does not automatically read these variables. Configure
one through your environment or secret manager before starting Python or the
notebook kernel.

The [example notebook](https://github.com/ESA-APEx/apex_algorithms/blob/main/examples/esa_apex_toolbox.ipynb)
also offers a hidden `getpass` prompt when neither variable is set. Enter the
token there, not in notebook source or chat. Press Enter to continue without a
token if your anonymous quota is still available. Restart the kernel after
upgrading the toolbox to load support for the `token` argument.

Treat a token like a password: never print it, put it in a committed file, or
include it in notebook outputs. Revoke and replace it immediately if exposed;
replace it when it expires. Authentication is applied to GitHub API directory
requests, not raw catalogue or process-definition downloads.

If you still hit a rate limit, stop retrying until the reset time reported in
the response's `X-RateLimit-Reset` header (UTC epoch seconds), or follow
`Retry-After` when supplied. A token cannot bypass an exhausted authenticated
quota or secondary rate limits. A `401 Bad credentials` response instead means
the token may be invalid, expired, or revoked.

## Discover and Filter Algorithms

Discover the available filter values before choosing a provider, platform,
or keyword:

```python
print(repo.list_providers())
print(repo.list_platforms())
print(repo.list_keywords())
```

These helpers return sorted, unique strings. Provider and platform values are
the titles of the record's `rel="provider"` and `rel="platform"` links, not
directory names or investigator contacts.

```python
vito_ids = repo.list_algorithms(provider="VITO")

matches = repo.list_algorithms(
    provider=["VITO"],
    platform="Copernicus Data Space openEO Backend",
    keywords=["Climate"],
    details=True,
)
for algorithm in matches:
    print(algorithm.id, "|", algorithm.provider, "|", algorithm.title)
```

Filters work with either return format. Without `details=True`, results are
folder IDs; with it, results are parsed `Algorithm` objects. An empty result
means that no algorithms match the selected values.

| Argument | Matching rule |
| :--- | :--- |
| `provider` | One provider title, or any title in a list. |
| `platform` | One platform title, or any title in a list. |
| `keywords` | One keyword, or all keywords in a list. |
| `details` | Defaults to `False`; use `True` to return metadata objects. |

All string matches are case-insensitive and exact, not substring matches.
Different filters combine with AND. `None` leaves a filter unrestricted.
An empty provider or platform list matches nothing; an empty keyword list
places no restriction on results.

## Inspect Algorithm Metadata

Use a folder ID returned by `list_algorithms()` to retrieve one record:

```python
algorithm = repo.get_algorithm("max_ndvi_composite")
print(algorithm.title)
print(algorithm.description)
print(algorithm.provider, algorithm.platforms, algorithm.keywords)

for service in algorithm.service_links or []:
    print(service.title, service.href)
```

An `Algorithm` exposes the following metadata:

| Attribute | Meaning |
| :--- | :--- |
| `id` | ID stored in the record. Use folder IDs from the listing for lookups. |
| `title`, `description` | Human-readable algorithm metadata, or `None`. |
| `provider` | Provider link title, or `None`. |
| `platforms`, `keywords` | Lists of platform titles and keywords; empty when absent. |
| `organization` | Principal investigator's organization, or `None`; not necessarily the provider. |
| `license` | Top-level record license, or `None`. |
| `service_links` | Service endpoints, each with `href` and an optional `title`. |
| `udp_link` | An openEO process-definition link with `href` and optional `title`, or `None`. |

### Inspect an openEO Process Definition

Not every algorithm provides an openEO user-defined process (UDP). For example,
an algorithm that publishes only a CWL application package has no `udp_link`.
Check the link before downloading:

```python
import requests

if algorithm.udp_link is not None:
    response = requests.get(algorithm.udp_link.href, timeout=30)
    response.raise_for_status()
    process_definition = response.json()
    for parameter in process_definition.get("parameters", []):
        print(parameter["name"], parameter.get("description", ""))
else:
    print("No openEO process definition is advertised for this algorithm.")
```

Downloading a definition does not execute it. Execution requires a suitable
client, a supported backend, authentication, input parameters, and potentially
processing credits. Consult the algorithm's service documentation before
submitting a job.

## Read a Record Directly

`Algorithm.from_ogc_api_record()` accepts a `pathlib.Path`, a path string,
an HTTP(S) URL, a JSON string, or an already parsed dictionary. For example,
from the repository root:

```python
from pathlib import Path

record_path = Path(
    "algorithm_catalog/vito/max_ndvi_composite/records/max_ndvi_composite.json"
)
local_algorithm = Algorithm.from_ogc_api_record(record_path)
print(local_algorithm.id, local_algorithm.title)
```

Reading a local record works offline and includes uncommitted metadata changes.
See [Record Mapping](catalogue.md#record-mapping) for catalogue metadata details.

## Network Access, Caching, and Errors

Unfiltered ID listing reads directory listings through the GitHub API and is
subject to its rate limits. Filtering, detailed listing, and discovery helpers
also fetch records from raw GitHub URLs in parallel, with up to eight downloads
at a time. The first metadata discovery call can therefore take longer than
listing IDs.

Listings and successfully parsed records, including records fetched by
`get_algorithm()`, are cached on the repository instance. Reuse the instance
to avoid repeat downloads; create a new instance to refresh the catalogue.

During filtering, detailed listing, and discovery helpers, directories whose
record URL returns HTTP 404 are skipped with a logged warning. This allows
auxiliary directories such as `images` to coexist with algorithms. Missing
records are not cached, so subsequent calls retry them. Unfiltered ID listing
still includes those directories because it does not fetch records.

Other HTTP and connection errors propagate from `requests`. Direct
`get_algorithm()` calls also propagate HTTP 404 errors. `get_algorithm()` raises
`ValueError` if a folder ID is missing or occurs under multiple providers.
Record validation errors raise `InvalidMetadataError`, a subclass of
`ValueError`, available from `esa_apex_toolbox.algorithms`. A record must be an
OGC API - Records service record and include at least one service link.
Invalid records and HTTP failures other than 404 are not skipped.