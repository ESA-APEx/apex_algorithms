# LEON-P6 openEO UDPs

These generated openEO User-Defined Processes implement the LEON-P6 forest-loss workflow:

- `forest_baseline` creates a 2020 natural-forest mask.
- `s1_logistic_processing` processes Sentinel-1 backscatter and detects sudden changes.
- `deforestation` identifies forest-loss events from the baseline and Sentinel-1 inputs.
- `KPIs` aggregates forest-loss and forest-loss-to-cropland areas by Uganda ADM-4 unit.
- `leon_p6` composes the four processes into the complete forest-loss KPI workflow.

They are generated from [Assimila/LEON-P6](https://github.com/Assimila/LEON-P6), in its `openeo/` directory.

TODO: switch `refs/heads/LEON-P6` URLs to `refs/heads/main` once merged into ESA-APEx/apex_algorithms.