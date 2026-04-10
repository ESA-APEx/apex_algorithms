# Timeseries Statistics

## Description

This algorithm computes temporal statistics from any EO collection for a user-specified geometry and temporal extent. It is designed as a flexible, generic utility targeted at advanced APEx users who are familiar with the available collections and band names on the underlying platform.

For each requested band, the following statistics are computed along the temporal dimension:

| Statistic | Description |
|-----------|-------------|
| **min**   | Minimum value over the temporal extent |
| **max**   | Maximum value over the temporal extent |
| **mean**  | Arithmetic mean over the temporal extent |
| **sd**    | Standard deviation over the temporal extent |
| **q10**   | 10th percentile over the temporal extent |
| **q50**   | Median (50th percentile) over the temporal extent |
| **q90**   | 90th percentile over the temporal extent |

The output is a CSV file with spatially averaged statistics. Each band is suffixed with the statistic name (e.g. `B04_min`, `B04_max`, `B08_q50`).

## Modes

### Full mode (default)

When `period` is `null` (the default), a single set of 7 statistics is computed over the entire temporal extent. The time dimension is collapsed, producing one row of results.

### Period mode

When `period` is set to a calendar period such as `"month"`, `"dekad"`, or `"year"`, the same 7 statistics are computed for each period, producing a time-series of statistics. This is useful for monitoring temporal trends or seasonal patterns.

## Parameters

| Parameter         | Description |
|-------------------|-------------|
| `collection_id`   | *(optional, default: `SENTINEL2_L2A`)* The identifier of the EO collection to use (e.g. `SENTINEL2_L2A`, `SENTINEL1_GRD`). The collection must be available on the target backend. |
| `bands`           | Band names to process (e.g. `["B04", "B08"]` for Sentinel-2 Red and NIR). Must be provided so that output columns can be labelled (e.g. `B04_min`, `B04_max`, …). |
| `geometry`        | GeoJSON geometry (Polygon or MultiPolygon) defining the area of interest. Statistics are spatially averaged over this geometry. |
| `temporal_extent` | Two-element array specifying the start and end date (e.g. `["2023-05-01", "2023-07-31"]`). |
| `period`          | *(optional, default: `null`)* Temporal aggregation period. One of `"year"`, `"month"`, `"week"`, `"dekad"`, `"day"`, or `null` for full mode. |

## Usage Notes

- This UDP does **not** apply any pre-processing (e.g. cloud masking or SAR backscatter calibration). Users are responsible for selecting an appropriate collection and temporal window.
- Cloud-affected observations in optical collections (e.g. Sentinel-2) will influence the statistics unless a cloud-masked collection variant is used.
- The output columns are named `{band}_{stat}`, e.g. `B04_min`, `B04_max`, `B04_mean`, `B04_sd`, `B04_q10`, `B04_q50`, `B04_q90`, `B08_min`, …
- The spatial aggregation computes the mean of all pixels within the geometry for each statistic.

## Performance Characteristics

The processing cost depends on the selected collection, number of bands, geometry size, and temporal range. As a reference point, computing statistics over a 10×10 km area for two Sentinel-2 L2A bands over a 3-month period costs approximately 4 platform credits.

## Example

Compute monthly statistics for Sentinel-2 L2A bands B04 and B08 over a polygon near Mol, Belgium:

```json
{
  "collection_id": "SENTINEL2_L2A",
  "bands": ["B04", "B08"],
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[4.97, 51.19], [5.07, 51.19], [5.07, 51.28], [4.97, 51.28], [4.97, 51.19]]]
  },
  "temporal_extent": ["2023-05-01", "2023-07-31"],
  "period": "month"
}
```
