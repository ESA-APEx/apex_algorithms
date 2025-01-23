
# APEx Algorithm Benchmarking

The hosted APEx Algorithms are executed automatically and regularly
following certain benchmark scenarios in order to:

- verify they still complete successfully
  and the output results are as expected (e.g. withing certain tolerance of reference data)
- keep track of certain metrics like execution time,
  resource consumption, credit consumption, etc.

## Algorithm and benchmark definitions

### Algorithm definitions

An APEx algorithm is defined as an openEO process definition
in the form of JSON files in the [`openeo_udp`](../openeo_udp/) folder.
These JSON files follow the standard openEO process definition schema,
for example as used for the `GET /process_graphs/{process_graph_id}` endpoint of the openEO API.

> [!NOTE]
> These openEO process definitions are commonly referred to
> as "UDPs" or "user-defined processes",
> which stems from the original openEO API specification
> with an isolated "user" concept.
> The scope of algorithm publishing and hosting in APEx
> goes well beyond isolated, individual users.
> As such, it can get confusing to overthink the "user-defined" part,
> and it might be better to just think of "openEO process definitions".


Example process definition:

```json
{
  "id": "max_ndvi",
  "parameters": [
    {
      "name": "temporal_extent",
      "schema": {
        "type": "array",
        "subtype": "temporal-interval",
        ...
      },
      ...
    },
    ...
  ],
  "process_graph":{
    "loadcollection1": {
      "process_id": "load_collection",
      ...
    },
    "reducedimension1": {
      "process_id": "reduce_dimension",
      ...
    },
    ...
  }
}
```

Alongside the JSON files, there might be additional resources,
like Markdown files with documentation or descriptions,
Python scripts to (re)generate the JSON files, etc.

### Benchmark definitions

The benchmark scenarios are defined as JSON files
in the [`benchmark_scenarios`](../benchmark_scenarios/) folder.
The schema of these files is defined (as JSON Schema)
in the [`schema/benchmark_scenario.json`](../schemas/benchmark_scenario.json) file.

Example benchmark definition:

```json
[
  {
    "id": "max_ndvi",
    "type": "openeo",
    "backend": "openeofed.dataspace.copernicus.eu",
    "process_graph": {
      "maxndvi1": {
        "process_id": "max_ndvi",
        "namespace": "https://raw.githubusercontent.com/ESA-APEx/apex_algorithms/f99f351d74d291d628e3aaa07fd078527a0cb631/openeo_udp/examples/max_ndvi/max_ndvi.json",
        "arguments": {
          "temporal_extent": ["2023-08-01", "2023-09-30"],
          ...
        },
        "result": true
      }
    },
    "reference_data": {
      "job-results.json": "https://s3.example/max_ndvi.json:max_ndvi:reference:job-results.json",
      "openEO.tif": "https://s3.example/max_ndvi.json:max_ndvi:reference:openEO.tif"
    }
  },
  ...
]
```

Note how each benchmark scenario references
- the target openEO backend to use.
- an openEO process graph to execute.
  The process graph will typically just contain a single node
  pointing with the `namespace` field to the desired process definition
  at a URL, following the [remote process definition extension](https://github.com/Open-EO/openeo-api/tree/draft/extensions/remote-process-definition).
  The URL will typically be a raw GitHub URL to the JSON file in the `openeo_udp` folder, but it can also be a URL to a different location.
- reference data to which actual results should be compared.

## Benchmarking Test Suite

The execution of the benchmarks is currently driven through
a [pytest](https://pytest.org/) test suite
defined at [`qa/benchmarks/`](../qa/benchmarks/).
The test suite code itself is not very complex.
There is basically just one test function that is parametrized
to run over all benchmark scenarios.
There is however additional tooling injected in the test suite
through custom pytest plugins.

### Randomly Pick A Single Benchmark Scenario

There is a simple plugin defined in the test suite's [`conftest.py`](../qa/benchmarks/tests/conftest.py)
to just run a random subset of benchmark scenarios.
It leverages the `pytest_collection_modifyitems` hook and is exposed
through the command line option `--random-subset`.
With `--random-subset=1`, only a single random benchmark scenario is run.

### Automatically Upload Generated Results

The [`apex_algorithm_qa_tools`](../qa/tools/apex_algorithm_qa_tools/) package includes the
[`pytest_upload_assets`](../qa/tools/apex_algorithm_qa_tools/pytest_upload_assets.py) plugin
which defines a `upload_assets_on_fail` fixture to automatically upload
openEO batch job results to an S3 bucket when the test fails.

### Tracking Of Benchmark Metrics

The [`apex_algorithm_qa_tools`](../qa/tools/apex_algorithm_qa_tools/) package includes the
[`pytest_track_metrics`](../qa/tools/apex_algorithm_qa_tools/pytest_track_metrics.py) plugin
which defines a `track_metrics` fixture to records metrics during the benchmark run.

## GitHub Actions Workflow

The benchmarking test suite is executed automatically with GitHub Actions.
This benchmark workflow is defined at [benchmarks.yaml](../.github/workflows/benchmarks.yaml)
and its run history can be viewed at https://github.com/ESA-APEx/apex_algorithms/actions/workflows/benchmarks.yaml
