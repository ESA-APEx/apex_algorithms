# World Agri Commodities (WAC) Processing Pipeline
This repository implements an end-to-end openEO pipeline for agricultural feature extraction and model inference using Sentinel-1 and Sentinel-2 data, a suite of preprocessing steps, vegetation indices, and a sliding-window ONNX model. The ML model was trained to classify agriculture activity for specific commodities in the context of ESA's World Agro Commodities project

## Algorithm and Workflow
### 1 Data Loading

Sentinel-2 L2A (optical) and Scene Classification Layer (SCL) for cloud masking

Sentinel-1 global mosaics (VV and VH)

Digital Elevation Model (COPERNICUS_30)

### 2 Preprocessing

Spatial reprojection & resampling (CRS EPSG:3035, resolution 10 m)

Cloud mask dilation on SCL → mask optical bands

Monthly aggregation (90 percentile) on Sentinel-2 and log-transformed Sentinel-1, DEM temporal mean

Compute vegetation indices (NDVI, NDRE, EVI)

Apply lat/lon UDF to add geographic coordinates

### 3 Normalization

Optical bands: scale, log-transform, nonlinear sigmoid normalization

Linear bands: min–max clipping and scaling for indices, radar backscatter, DEM, lat/lon

### 4 Model Inference

Patch-based sliding window (size 128×128 px, overlap 64 px) via apply_neighborhood UDF

ONNX U-Net model loaded at runtime

### 5 Auxiliary Data

After the Model Inference, A preliminary Tree Cover Density Product is included for the year 2020 


 