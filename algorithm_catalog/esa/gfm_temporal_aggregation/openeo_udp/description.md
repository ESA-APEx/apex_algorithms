# GFM Temporal Aggregation

## Description

This UDP performs temporal aggregation of Copernicus Emergency Management Service Global Flood Monitoring (GFM) products for a user-selected area, time range, set of GFM layers, and temporal statistic. It is intended for rapid flood-event summaries such as maximum observed flood extent, flood frequency, cumulative flooded observations, or counts of valid observations over an analysis period.

The workflow is based on the [openEO Platform Global Flood Monitoring tutorial](https://docs.openeo.cloud/usecases/gfm/) and loads the GFM collection from the EODC STAC API:

https://stac.eodc.eu/api/v1/collections/GFM

## Supported GFM Layers

The `bands` parameter accepts one or more of the following GFM item assets:

| Layer | Description |
|-------|-------------|
| `ensemble_flood_extent` | Ensemble flood extent derived from the individual flood algorithms. This is the default layer and the main layer for mapping observed flood occurrence. |
| `ensemble_water_extent` | Ensemble water extent product. |
| `ensemble_likelihood` | Ensemble likelihood layer expressing confidence in the detected flood or water signal. |
| `reference_water_mask` | Permanent and seasonal reference water bodies, useful for distinguishing known water from flood events. |
| `exclusion_mask` | Areas excluded from flood mapping or interpretation. |
| `advisory_flags` | Advisory quality or interpretation flags. |
| `dlr_flood_extent` | Flood extent output from the DLR algorithm. |
| `list_flood_extent` | Flood extent output from the LIST algorithm. |
| `tuw_flood_extent` | Flood extent output from the TU Wien algorithm. |
| `dlr_likelihood` | Likelihood layer from the DLR algorithm. |
| `list_likelihood` | Likelihood layer from the LIST algorithm. |
| `tuw_likelihood` | Likelihood layer from the TU Wien algorithm. |

When multiple bands are requested, each band is aggregated independently and preserved as a separate output band.

## Temporal Statistics

The `statistic` parameter selects the reducer applied over the full temporal extent:

| Statistic | Typical use |
|-----------|-------------|
| `max` | Maximum value over the period. For binary flood-extent layers this indicates whether a pixel was ever mapped as flooded during the period. This is the default. |
| `min` | Minimum value over the period. Useful for identifying pixels that consistently satisfy a condition, depending on the selected layer encoding. |
| `mean` | Mean value over the period. For binary flood-extent layers this can be interpreted as flood frequency across available observations. |
| `median` | Median value over the period, useful as a robust central tendency for likelihood or flag-like layers. |
| `sum` | Sum over the period. For binary flood-extent layers this represents the number of flooded observations. |
| `count` | Number of valid observations contributing to the temporal aggregation. |

The result has no temporal dimension: each selected GFM layer is reduced to one value per pixel for the requested analysis period.

## References

- openEO Platform GFM tutorial: https://docs.openeo.cloud/usecases/gfm/
- GFM Wiki: https://extwiki.eodc.eu/GFM
- EODC GFM STAC collection: https://stac.eodc.eu/api/v1/collections/GFM
