# Waterlines openEO UDP
## Purpose
Extract coastline waterlines from Sentinel-2 imagery using NDWI-based water detection, morphological refinement, and UDF-based vectorization.

## Methodology
### Water/Land Classification
Water masks are derived using the NDWI (Normalized Difference Water Index):

- **NDWI (Normalized Difference Water Index)**  
  $$
  NDWI = \frac{G - NIR}{G + NIR}
  $$

Where water is classified as:
- **NDWI > threshold**

Where:
- **G** = Green band (S2 B03)  
- **NIR** = Near Infrared (S2 B08)  

Default threshold is equal to **0.01** but can be overridden via parameters.

### Why only NDWI?
This MVP supports only one method (**S2_NDWI**).

Originally, multiple methods were selectable via a parameter, but this required openEO `if_()` logic, which converts the result into a `ProcessBuilder` instead of a `DataCube`.
This breaks the `raster_to_vector()` step needed for waterline extraction.

### Morphological Processing
For each timestamp, the water/land mask is refined using morphological operations to:

- remove small isolated objects  
- fill small holes  
- smooth boundaries  
- reduce artifacts such as narrow bridges and estuaries  

This improves the quality and stability of the resulting waterlines.

### Waterline Extraction
The cleaned masks are converted into vector waterlines using a UDF, producing geometries for each time step.

## Output
The process outputs Vector cube of coastline waterlines with the following properties:
- **time**: Acquisition timestamp (Sentinel-2 datetime)  
- **type**: Feature type (`waterline_segment`)  
- **sea_direction_8**: Sea direction (N, NE, E, SE, S, SW, W, NW)  
- **sea_azimuth_deg**: Sea direction in degrees (azimuth, clockwise from north)  
- **geometry**: Waterline geometry (LineString or MultiLineString) in EPSG:3857  

## Usage
See the APEx documentation and repository:

- [UDP Writer Guide](https://esa-apex.github.io/apex_documentation/guides/udp_writer_guide.html)  
- [APEx Algorithms GitHub](https://github.com/ESA-APEx/apex_algorithms)

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