# Sen2like

The Sen2Like processor was developed by ESA as part of the EU Copernicus program. It creates Sentinel-2 like harmonized (Level-2H) or fused (Level-2F) surface reflectances by harmonizing Sentinel-2 and Landsat 8/Landsat 9 to increase the temporal revisits. The fusion involves the upscaling of Landsat 8/Landsat 9 data to Sentinel-2 resolution. Furthermore, the resulting sen2like L2H/ L2F data can be processed using openEO to generate statistics, vegetation indices, do comparisons with other datasets, etc.

### Methodology

The processing of the incoming Landsat and Sentinel-2 L1C data includes the following main processing steps: Geometric Processing, Stitching, Geometric Check, Inter-calibration, Atmospheric correction, BRDF Adjustment, SBAF, Topographic Correction, Data Fusion. If Sentinel-2 L2A data is provided, sen2like processing will not include Atmospheric and Topographic Correction. In the geometric processing step, the input images are co-registered to a Sentinel-2 reference image. The atmospheric correction step makes use of the sen2cor processor and additionally relies on Copernicus Atmosphere Monitoring Service (CAMS) Near Real Time and Reanalysis data as well as the Copernicus Digital Elevation Model. The Data Fusion step alignes Landsat 8 image pixel spacing fully with Sentinel2 image pixel spacing. Depending on the band, the resolution of the Landsat L2F product is 10 m, 20 m or 30 m.

### Quality

The geometric check process is a Quality Control step of the product. For further information, see Sen2like User Manual. 

### Links

- [RD1] openEO platform Sen2like documentation https://docs.openeo.cloud/usecases/ard/sen2like

- [RD1] Saunier, S. (2025). Sen2like User Manual https://github.com/senbox-org/sen2like/blob/master/sen2like/docs/source/S2-SEN2LIKE-UM-V1.10.pdf"