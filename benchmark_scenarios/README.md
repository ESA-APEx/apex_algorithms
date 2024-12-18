# Benchmark scenarios

Benchmark scenarios are defined as JSON files in this folder.

> [!WARNING]
> The format of these files is [subject to change](https://github.com/ESA-APEx/apex_algorithms/issues/14).


Each of these files should contain an array of benchmark scenario objects,
which have the following properties:



| Element         | Type         | Description                          |
| --------------- | ------------ | ------------------------------------ |
| id              | string       | **REQUIRED.** Benchmark scenario identifier. |
| type            | string       | **REQUIRED.** Must be set to "openeo" currently. |
| description     | string       | Description of the benchmark scenario.   |
| backend         | string       | **REQUIRED.** The openEO backend URL to be used. |
| process_graph   | object       | **REQUIRED.** The openEO process graph to be executed. |
| reference_data  | object       | Expected/reference data of the benchmark, as a mapping of output names to (e.g. object storage) URLs. |
| reference_options | object     | Optional settings for reference comparisong, e.g. "rtol" for relative tolerance and "atol" for absolute tolerance. |
