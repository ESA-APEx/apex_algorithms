
# APEx Algorithms Benchmark suite

This is pytest-based benchmark suite for APEx algorithms.
The goal is to run hosted algorithms according to pre-defined scenarios
against real openEO backends and observe their outcome and performance.


## Set up

Make sure to work in a virtual environment
(e.g. with `python -m venv venv`),
to ensure isolation from other projects.

Install the test dependencies, including the reusable tools from `apex-algorithm-qa-tools`,
e.g. when working from the `qa/benchmarks` folder:

```bash
# Install general test requirements
pip install -r requirements.txt
# Install apex-algorithm-qa-tools
pip install ../tools
```

When intending to do development on `apex-algorithm-qa-tools`,
make sure to include the `-e` flag to install in editable mode.

## Run benchmarks

From `qa/benchmarks` folder, run:

```
pytest
```
