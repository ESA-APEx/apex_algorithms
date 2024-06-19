

# APEx Algorithms unittests

This is pytest-based unittest suite to verify the validity of resources
hosted in this repository.


## Set up

Make sure to work in a virtual environment
(e.g. with `python -m venv venv`),
to ensure isolation from other projects.

Install the test dependencies, including the reusable tools from `apex-algorithm-qa-tools`,
e.g. when working from the `qa/unittests` folder:

```bash
# Install apex-algorithm-qa-tools
pip install ../tools
# Install general test requirements
pip install -r requirements.txt
```

When intending to do development on `apex-algorithm-qa-tools`,
make sure to include the `-e` flag to install in editable mode.

## Run benchmarks

From `qa/unittests` folder, run:

```bash
pytest
```
