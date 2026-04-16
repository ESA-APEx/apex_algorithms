# Waterlines openEO UDP
## Purpose
Extract coastline waterlines from Sentinel-2 imagery using NDWI-based water detection, morphological refinement, and UDF-based conversion from water polygons to coast waterlines.

## Methodology
### Water/Land Classification
Water masks are generated using the **Normalized Difference Water Index (NDWI)**, where pixels are classified as water when **NDWI > threshold**. The default threshold is **0.01**, but it can be adjusted using the `ndwi_threshold` parameter.

NDWI is computed as the normalized difference between the Sentinel-2 **Green** band (B03) and **Near-Infrared** band (B08), defined as the difference between these bands divided by their sum.

*This MVP supports only one method (**S2_NDWI**). Originally, multiple methods were selectable via a parameter, but this required openEO `if_()` logic, which converts the result into a `ProcessBuilder` instead of a `DataCube`.
This breaks the `raster_to_vector()` step needed for waterline extraction.*

### Morphological Processing
For each timestamp, the water/land mask is refined using morphological operations to remove small isolated objects, fill small holes, smooth boundaries and reduce artifacts such as narrow bridges and estuaries. This improves the quality and stability of the resulting waterlines.

### Waterline Extraction
The cleaned masks are vectorized using the built-in openEO function `raster_to_vector()`. The resulting water polygons are then transformed into waterlines via a UDF, producing time-resolved geometries for each timestep.

The output is a vector cube of coastline waterlines with the following properties:
- **time**: Acquisition timestamp (Sentinel-2 datetime)  
- **type**: Feature type (`waterline_segment`)  
- **sea_direction_8**: Sea direction (N, NE, E, SE, S, SW, W, NW)  
- **sea_azimuth_deg**: Sea direction in degrees (azimuth, clockwise from north)  
- **geometry**: Waterline geometry (LineString or MultiLineString) in EPSG:3857  

The **sea_azimuth_deg** property is particularly useful for downstream processing, as it can be used to shift the waterline and derive a shoreline (*a waterline normalized for beach slope and tidal conditions*).

## Authors / Contact
- **Milena Napiorkowska** (openEO UDP) Argans Ltd  
  mnapiorkowska@argans.co.uk  

- **Martin Jones** (Project Manager) Argans Ltd  
  mjones@argans.co.uk  

- **Holly Baxter** (Methodology) Argans Ltd  
  hbaxtar@argans.co.uk  

- **Cameron Mackenzie** (Methodology) Argans Ltd
  cmackenzie@argans.co.uk  

## Acknowledgments
This work was developed as part of an ESA-funded **Fast Track** project.

## Known Limitations
- Results are most reliable for scenes with low cloud coverage  
- NoData areas may introduce artifacts, particularly along boundaries between valid and invalid pixels  
- NDWI might be less reliable in turbid waters