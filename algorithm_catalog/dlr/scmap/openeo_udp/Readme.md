# SCMaP OpenEO User defined process
## Purpose

DLR's Soil Composite Mapping Processor (ScMAP) generates a collection of different image data products (SoilSuite) that provide information about the spectral and statistical properties of European soils and other bare surfaces such as rocks. SCMaP utilizes the Sentinel-2 data archive and is a specialized processing chain for detecting and analyzing bare soils/surfaces on a large (continental) scale. Bare surface and soil pixels are selected using an index combining the Normalized Difference Vegetation Index (NDVI) and the Normalized Burned Ratio (NBR) that optimizes the exclusion of photosynthetically active and non-active vegetation. The index is calculated and applied for each individual pixel. The resulting products can be used for multiple purposes such as input for spectral and digital soil property mapping approaches (e.g. bare surface composites), soil erosion analyses and monitoring of agricultural practices (e.g. bare surface frequency and mask product). 

## Algorithm
For the specified area of interest and time, Sentinel-2 scenes (bands B02, B03, B04, B05, B06, B07, B08, B8A, B11, B12) with cloud cover below the max_cloud_cover threshold are loaded.
Then, the following steps are executed:

1. Pixels with sun-zenith angles exceeding the specified threshold (default: 70°) are discarded.
2. Clouds and other invalid pixels are removed based on the Scene Classification Layer (SCL).
3. NDVI and NBR indices are computed and compared, on a per-pixel basis, to a pre-computed threshold image; pixels falling below the threshold are classified as bare surface
4. Residual clouds and haze are removed using a Median Absolute Deviation (MAD) outlier detection applied to the B02 band along the temporal axis.
5. For pixels with at least three valid bare-surface observations over time, the temporal mean reflectance is calculated to produce the Soil Reflectance Composite (SRC).
6. Urban areas and permanent water bodies are subsequently masked using the WorldCover dataset.

For a more detailed description of the algorithm and its by-products, please refer to the [Documentation](https://download.geoservice.dlr.de/SOILSUITE/files/EUROPE_5Y/000_Data_Overview/SoilSuite_Data_Description_Europe_V1.pdf) of SoilSuite, or to any of the papers linked below.

## Output
| Band | Full Name | Description | 
| -------- | ------- | ------- |
| SRC_B*XX*  | Bare Surface Reflectance Composite - Mean | It provides the spectral properties of soils that vary due to different soil organic carbon (SOC) content, soil moisture and soil minerology. This product is often used for spectral and digital soil mapping approaches |
| SRC_STD_B*XX* | Bare Surface Reflectance Composite - Standard deviation |It informs about the spectral dynamic of bare surfaces and soils |
| MREF_B*XX* | Reflectance Composite - Mean | It represents the mean reflectance of all valid Sentinel-2 observations including vegetation, bare and other surfaces |
| MREF_STD_B*XX* | Reflectance Composite - Standard deviation | It contains the standard deviation for all valid Sentinel-2 observations |
| VPC | Valid Pixel Count | It provides the total number of valid observations at this pixel |
| BSC | Bare Surface Count | It provides the number of bare soil occurrences at this pixel |
| BSF | Bare Surface Frequency | It provides the number of bare soil occurrences over the total number of valid observations |
| Mask | Mask | The band aggregates simple landcover classes: Pixel may either contain *bare soil* (1), is *permaenently vegetated* (2) or is *another surface* (3) (e.g. water bodies, built-up areas, ..) | 

The computation of MREF and MASK is switched of by default to reduce the consummption of platform credits and speed up computation.
It can be enabled through the parameters. 

## Usage

Please refer to the APEx Documentation [Documentation](https://esa-apex.github.io/apex_documentation/guides/udp_writer_guide.html) and the [GitHub](https://github.com/ESA-APEx/apex_algorithms)

## Literature references
[SoilSuite Europe](https://geoservice.dlr.de/web/datasets/soilsuite_eur_5y)
- Rogge, D., Bauer, A, Zeidler, J., Müller, A., Esch, T. and Heiden, U. (2018). Building an exposed soil composite processor (SCMaP) for mapping spatial and temporal characteristics of soils with Landsat imagery (1984-2014). Remote Sensing of Environment, 205, 1-17. ISSN 0034-4257 DOI: 10.3390/rs14184526
- Heiden, U., d’Angelo, P., Schwind, P., Karlshöfer, P., Müller, R., Zepp, S., Wiesmeier, M., & Reinartz, P. (2022). Soil Reflectance Composites—Improved Thresholding and Performance Evaluation. Remote Sensing, 14(18), 4526. DOI: 10.1016/j.rse.2017.11.004
- Karlshoefer, P., d’Angelo, P., Eberle, J., & Heiden, U. (2025). Evaluation framework for the generation of continental bare surface reflectance composites. Geoderma, 459. DOI: 10.1016/j.geoderma.2025.117340

## License
CC-BY-NC

## Authors / Contact
- Uta Heiden (Producer, Processor) DLR/EOC Imaging Spectroscopy
- - uta.heiden@dlr.de
- Pablo d'Angelo (Producer, Processor) DLR/EOC Photogrammetry and Image Analysis
- - pablo.angelo@dlr.de
- Paul Karlshöfer (Producer, Processor, OpenEO UDP) DLR/EOC Imaging Spectroscopy
- - paul.karlshoefer@dlr.de
EOC Geoservice (Host) DLR/EOC


## Acknowledgments / Funding 
The project received funding under the ESA WORLDSOILS project (Contract No. 400131273/20/I-703 NB) and from the EU FPCUP project CUP4SOIL (FPA 275/G/GRO/COPE/17/10042).

# Known limitations
- The bare surface reflectance quality and availability is lower for areas with spectral mixtures, such as small fields, orchards and agroforestry areas. 
- The spatial resolution is limited by the B12 band of Sentinel, which is available at 20m ground sampling distance.
- The algorihtm requires threshold image that is loaded via *from_stac(...)*. It is currently available for the European continent.
- To obtain stable soil reflectance values, users should integrate observations across multiple seasons or, ideally, several years. As a reference point, SoilSuite Europe employed a five-year time range, while SoilSuite Africa used four years.
- For large areas (> 1000km^2) and long time series (> 2 years), the process might be terminated by the platform. Please consider smaller spatial chunks in that case.
