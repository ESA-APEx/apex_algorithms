# Multi output gaussian process regression

## Description

Compute an integrated timeseries based on multiple inputs.
For instance, combine Sentinel-2 NDVI with Sentinel-1 RVI into one integrated NDVI.

## Limitations

The spatial extent is limited to a maximum size equal to a Sentinel-2 MGRS tile (100 km x 100 km).

## Configuration & Resource Usage

Run configurations for different ROI/TOI with memory requirements and estimated run durations.

### Synchronous calls

TODO: Replace with actual measurements!!!

| Spatial extent | Run duration |
|----------------|--------------|
| 100 m x 100 m  | 1 minute     |
| 500m x 500 m   | 1 minute     |
| 1 km x 1 km    | 1 minute     |
| 5 km x 5 km    | 2 minutes    |
| 10 km x 10 km  | 3 minutes    |
| 50 km x 50 km  | 9 minutes    |

The maximum duration of a synchronous run is 15 minutes.
For long running computations, you can use batch jobs.

### Batch jobs

TODO: Replace with actual measurements!!!

| Spatial extent  | Temporal extent | Executor memory | Run duration |
|-----------------|-----------------|-----------------|--------------|
| 100 m x 100 m   | 1 month         | default         | 7 minutes    |
| 500 m x 100 m   | 1 month         | default         | 7 minutes    |
| 1 km x 1 km     | 1 month         | default         | 7 minutes    |
| 5 km x 5 km     | 1 month         | default         | 10 minutes   |
| 10 km x 10 km   | 1 month         | default         | 11 minutes   |
| 50 km x 50 km   | 1 month         | 6 GB            | 20 minutes   |
| 100 km x 100 km | 1 month         | 7 GB            | 34 minutes   |
| 100m x 100 m    | 7 months        | default         | 10 minutes   |
| 500 m x 500 m   | 7 months        | default         | 10 minutes   |
| 1 km x 1 km     | 7 months        | default         | 14 minutes   |
| 5 km x 5 km     | 7 months        | default         | 14 minutes   |
| 10 km x 10 km   | 7 months        | default         | 19 minutes   |
| 50 km x 50 km   | 7 months        | 6 GB            | 45 minutes   |
| 100 km x 100 km | 7 months        | 8 GB            | 65 minutes   |
