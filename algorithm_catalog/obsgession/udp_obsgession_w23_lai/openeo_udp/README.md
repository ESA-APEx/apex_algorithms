# EO4Diversity EVI-LAI 

Calculate **Leaf Area Index (LAI)** at 10m spatial resolution based on Sentinel-2 time series, optimized for forested areas in temperate zones. Users can define spatial area-of-interest, the temporal interval, the temporal binning period and algorithm, and output spatial resolution and coordinate system. A cloud and tree cover mask are applied. The result is a Cloud Optimized GeoTIFF (COG) raster file.

The **LAI** provides a one-sided green leaf area, hence half the total area of a canopy’s green elements, per unit of horizontal ground area. The satellite-derived value corresponds to the total green LAI of all the canopy layers, including the understory, which may represent a very significant contribution, particularly for forests. LAI is a remote sensing-based candidate for the Essential Biodiversity Variable (EBV) *Live cover fraction* in the EBV class *Ecosystem structure*, and provides relevant information for the EBV classes Ecosystem functioning and Ecosystem phenology. 

Sentinel-2 time series provides opportunities for medium-resolution LAI mapping due to its spectral configuration, which includes multiple red-edge and shortwave infrared (SWIR) bands.

# Methodology

The empirical algorithm to derive the LAI from Sentinel-2 is developed and validated by the ESA-funded EO4Diversity project. It relates in-situ LAI measurements to the enhanced vegetation index (EVI) by adapting the approach developed by Boegh et al. (2002), optimized for and demonstrating robust performance over temperate forest sites. The method is computationally efficient and validated over temperate forest ecosystems. In principle, it could be transferable to other vegetated ecosystems with appropriate re-calibration. The method was identified as a benchmark approach in the OBSGESSION project, funded by the European Union under the Horizon Europe research and innovation programme.

# Quality

Abdullah et al. (2025) reports RMSE values varying between 0.85 and 2.28 m²m⁻² and a correlation coefficient varying between 0.55 and 0.78 when comparing measured and sentinel-2 retrieved LAI values across different years and forest sites (coniferous, deciduous and mixed) in northwestern Europe. Tests demonstrated a stable relationship between estimated and measured LAI and reliable capture of inter-annual and inter-site variability in canopy structure of diverse temperate forests with a single set of calibrated regression. Slightly higher uncertainty was observed in coniferous plots, likely due to clumping effects and strong background reflectance, whereas deciduous stands showed tighter correlations with ground observations. Overall, the results confirm that the LAI algorithm provides an accurate and transferable measure of vegetation canopy density suitable for regional-scale monitoring and ecosystem-condition applications.

# Limitations

* Input is Sentinel-2 L2A data sourced from CDSE. Usage of other data sources like existing Sentinel-2 composites is not yet supported. 
* The applied forest mask is based on the WorldCover2021 dataset. Usage of an annual Land Cover dataset (e.g. CCI) is not yet supported.

# Links

* Abdullah et al. (2025). Deliverable D2.3. Algorithm Theoretical Baseline Document. Deliverable D2.3 EU Horizon Europe OBSGESSION Project, Grant agreement No. 101134954
* Boegh, E., et al (2002). Airborne multispectral data for quantifying leaf area index, nitrogen concentration, and photosynthetic efficiency in agriculture. Remote Sens Environ 81(2-3): 179-193. https://doi.org/10.1016/S0034-4257(01)00342-X 
* OBSGESSION project [https://obsgession.eu/](https://obsgession.eu/)
* EO4Diversity project [https://www.eo4diversity.info/](https://www.eo4diversity.info/)
