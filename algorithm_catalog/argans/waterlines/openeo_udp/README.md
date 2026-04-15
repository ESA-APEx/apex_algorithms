# Waterlines openEO UDP

## Purpose
Extract coastline waterlines from Sentinel-2 imagery using a selectable water/land classification method, morphological refinement, and UDF-based vectorization.

---

## Methodology

The algorithm processes Sentinel-2 time series data to generate water/land masks and extract waterlines.

### Water/Land Classification

Water/land masks are derived using one of the following methods:

#### Index-based methods

Water is identified based on spectral indices computed from Sentinel-2 bands:

- **NDWI (Normalized Difference Water Index)**  
  $$
  NDWI = \frac{G - NIR}{G + NIR}
  $$

- **MNDWI (Modified NDWI)**  
  $$
  MNDWI = \frac{G - SWIR}{G + SWIR}
  $$

- **NDVI (Normalized Difference Vegetation Index)**  
  $$
  NDVI = \frac{NIR - R}{NIR + R}
  $$

- **GNDVI (Green NDVI)**  
  $$
  GNDVI = \frac{NIR - G}{NIR + G}
  $$

- **BNDVI (Blue NDVI)**  
  $$
  BNDVI = \frac{NIR - B}{NIR + B}
  $$

Where:
- **B** = Blue band (S2 B02)  
- **G** = Green band (S2 B03)  
- **R** = Red band (S2 B04)  
- **NIR** = Near Infrared (S2 B08)  
- **SWIR** = Shortwave Infrared (S2 B11)

Water classification rules:
- NDWI, MNDWI → water if index > threshold  
- NDVI, GNDVI, BNDVI → water if index < threshold  

Default thresholds are provided for each index but can be overridden via parameters.

---

#### SCL-based method

- Uses the Sentinel-2 Scene Classification Layer (SCL)  
- Water is identified as class `6`  

---

### Morphological Processing

For each timestamp, the water/land mask is refined using morphological operations to:

- remove small isolated objects  
- fill small holes  
- smooth boundaries  
- reduce artifacts such as narrow bridges and estuaries  

This improves the quality and stability of the resulting waterlines.

---

### Waterline Extraction

The cleaned masks are converted into vector waterlines using a UDF, producing geometries for each time step.

---

## Output

The process outputs **FeatureCollections** of coastline waterlines with the following properties:

- **time** – Acquisition timestamp (Sentinel-2 datetime)  
- **type** – Feature type (`waterline_segment`)  
- **sea_direction_8** – Sea direction (N, NE, E, SE, S, SW, W, NW)  
- **sea_azimuth_deg** – Sea direction in degrees (azimuth, clockwise from north)  
- **geometry** – Waterline geometry (LineString or MultiLineString) in EPSG:3857  

---

## Usage

See the APEx documentation and repository:

- [UDP Writer Guide](https://esa-apex.github.io/apex_documentation/guides/udp_writer_guide.html)  
- [APEx Algorithms GitHub](https://github.com/ESA-APEx/apex_algorithms)

---

## Authors / Contact

- **Milena Napiorkowska** (openEO UDP) – Argans Ltd  
  mnapiorkowska@argans.co.uk  

- **Martin Jones** (Project Manager) – Argans Ltd  
  mjones@argans.co.uk  

- **Holly Baxter** (Methodology) – Argans Ltd  
  hbaxtar@argans.co.uk  

- **Cameron Mackenzie** (Methodology)  
  cmackenzie@argans.co.uk  

---

## Acknowledgments

This work was developed as part of an ESA-funded Fast Track project.

---

## Known Limitations

- Results are most reliable for scenes with low cloud coverage  
- NoData areas may introduce artifacts, particularly along boundaries between valid and invalid pixels  