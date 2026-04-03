# Timeseries Statistics

## Description

This algorithm computes temporal statistics from any EO collection for a user-specified spatial and temporal extent. It is designed as a flexible, generic utility targeted at advanced APEx users who are familiar with the available collections and band names on the underlying platform.

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

The output is a single raster with `n_bands × 7` layers, where the stats for each band are stacked in the order: min, max, mean, sd, q10, q50, q90.

## Parameters

| Parameter         | Description |
|-------------------|-------------|
| `collection_id`   | The identifier of the EO collection to use (e.g. `SENTINEL2_L2A`, `SENTINEL1_GRD`). The collection must be available on the target backend. |
| `bands`           | *(optional)* Band names to process (e.g. `["B04", "B08"]` for Sentinel-2 Red and NIR). When `null` (the default) all bands of the collection are loaded. Specifying bands is recommended to reduce data volume and cost. |
| `spatial_extent`  | Bounding box (`west`, `south`, `east`, `north`) in WGS84. |
| `temporal_extent` | Two-element array specifying the start and end date (e.g. `["2023-05-01", "2023-07-31"]`). |
| `resolution`      | *(optional)* Target spatial resolution in the units of the collection's native CRS (metres for projected CRS, degrees for WGS84). When `null` (the default) the native collection resolution is preserved. |

## Usage Notes

- This UDP does **not** apply any pre-processing (e.g. cloud masking or SAR backscatter calibration). Users are responsible for selecting an appropriate collection and temporal window.
- The output band order follows the input bands order. For example, with `bands = ["B04", "B08"]` the output will contain 14 bands ordered as: B04_min, B04_max, B04_mean, B04_sd, B04_q10, B04_q50, B04_q90, B08_min, ...
- Cloud-affected observations in optical collections (e.g. Sentinel-2) will influence the statistics unless a cloud-masked collection variant is used.

## Performance Characteristics

The processing cost depends on the selected collection, number of bands, spatial extent, and temporal range. As a reference point, computing statistics over a 10×10 km area for two Sentinel-2 L2A bands over a 3-month period costs approximately 4 platform credits.

## Example

The example below shows the derived mean and standard deviation for Sentinel-2 L2A bands B04 (Red) and B08 (NIR) calculated for a 10×10 km area of interest near Mol, Belgium, for the summer of 2023.
