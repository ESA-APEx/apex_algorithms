---
title: "Creating APEx Service Records"
format: html
---
Each APEx Service is defined as an OGC API Record, following the [APEx Service - OGC API Record JSON schema](https://github.com/ESA-APEx/apex_algorithms/blob/main/schemas/record.json). This standardized approach ensures consistency across APEx Services, facilitating seamless integration with other tools such as the [APEx Algorithm Services Catalogue](https://algorithm-catalogue.apex.esa.int/).

## Creating a New OGC API Record

To define a new APEx service as an OGC API Record, follow these steps:

1. Start by creating a new branch for your service.

2. Create the JSON record for your service:
    * Use the following folder structure: `algorithm_catalog/<organization>/<service_id>/records/<service_id.json>`
    * Structure your JSON record according to the [APEx Service - OGC API Record JSON schema](https://github.com/ESA-APEx/apex_algorithms/blob/main/schemas/record.json). 
    * More tips on how you can ensure the proper visualization in the [APEx Algorithm Services Catalogue](https://algorithm-catalogue.apex.esa.int/) are available [here](./visualise.md).

3. Before submission, ensure your record is compliant:
    * Use an online validator like [JSON Schema Validator](https://www.jsonschemavalidator.net/).
    * Alternatively, run unit test validation using [test_records.py](../../qa/unittests/tests/test_records.py).

4. Submit your service record:
   * Once validated, push your changes to your branch and create a GitHub pull request.
   * After review and a successful GitHub Actions build, the APEx team will merge your pull request, officially integrating your record into the APEx catalog.
