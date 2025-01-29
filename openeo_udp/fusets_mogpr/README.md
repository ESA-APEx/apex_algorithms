# Sentinel-1 and Sentinel-2 data fusion through Multi-output Gaussian process regression (MOGPR)

This service is designed to enable multi-output regression analysis using Gaussian Process Regression (GPR) on geospatial data. It provides a powerful tool for understanding and predicting spatiotemporal phenomena by filling gaps based on other correlated indicators. This service focuses on fusing Sentinel-1 and Sentinel-2 data, allowing the user to select one of the predefined data sources.

## Parameters

The `fusets_mogpr_s1s2` service requires the following parameters:


| Name            | Description                                                    | Type    | Default |
| --------------- | -------------------------------------------------------------- | ------- | ------- |
| spatial_extent  | Polygon representing the AOI on which to apply the data fusion | GeoJSON |         |
| temporal_extent | Date range for which to apply the data fusion                  | Array   |         |
| s1_collection   | S1 data collection to use for the fusion                       | Text    | RVI     |
| s2_collection   | S2 data collection to use for fusing the data                  | Text    | NDVI    |

## Supported collections

#### Sentinel-1

* RVI
* GRD

#### Sentinel-2

* NDVI
* FAPAR
* LAI
* FCOVER
* EVI
* CCC
* CWC

## Limitations

The spatial extent is limited to a maximum size equal to a Sentinel-2 MGRS tile (100 km x 100 km).

## Dependencies

In addition to various Python libraries, the workflow utilizes the following libraries included in the User-Defined Function (UDF):

* Biopar: The `biopar` package retrieves biophysical parameters like FAPAR, FCOVER, and more, that were passed as the S2_collection. The biopar package is a Python package that calculates biophysical parameters from Sentinel-2 satellite images as described [here](https://step.esa.int/docs/extra/ATBD_S2ToolBox_L2B_V1.1.pdf). The `fusets_mogpr` udp directly uses the biopar udp shared in the APEX Algorithms repository. 

* FuseTS: The `fusets` library was developed to facilitate data fusion and time-series analytics using AI/ML to extract insights about land environments. It functions as a Time Series & Data Fusion toolbox integrated with openEO. For additional information, please refer to the [FuseTS documentation](https://open-eo.github.io/FuseTS/installation.html).



## Output

This User-Defined-Process (UDP) produces a datacube that contains a gap-filled time series for all pixels within the specified temporal and spatial range. This datacube can be seamlessly integrated with other openEO processes.