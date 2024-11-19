# Biophysical Parameters 

Calculate various biophysical parameters for an area defined by a polygon. The result is a raster file
containing the parameter values. A strict cloudmask is applied, to avoid cloud contamination.
                    
The **Leaf Area Index (LAI)** is defined as half the total area of a canopy's green elements 
per unit horizontal ground area. The satellite-derived value corresponds to the total green LAI 
of all the canopy layers, including the understory, which may represent a very significant 
contribution, particularly for forests. The LAI distributed by Terrascope is also known as GAI, 
which stands for Green Area Index, and is related to the green part of the vegetation only
 (i.e. not only the leaves, but excluding the non-green parts).

The **Fraction of Absorbed Photosynthetic Active Radiation (fAPAR)** quantifies the fraction 
of solar radiation absorbed by leaves for the photosynthetic activity. It depends on the 
canopy structure, vegetation element optical properties, atmospheric conditions, and angular 
configuration.

The **Fraction of Vegetation Coverage (fCOVER)** corresponds to the fraction of ground 
covered by green vegetation. Practically, it quantifies the vegetation's spatial extent.

The **Canopy Water Content (CWC)** is the water mass per unit ground area and is a key 
vegetation indicator in agriculture and forestry applications.

The **Canopy Chlorophyll Content (CCC)** is defined as the total chlorophyll content per 
unit ground area in a contiguous group of plants. It is well suited for quantifying canopy 
level nitrogen content and gross primary production estimation.

### Methodology

The methodology used to derive the biophysical parameters from Sentinel-2 is developed by INRA-
EMMAH. The methodology was initially developed to generate biophysical products from SPOT-
VEGETATION, ENVISAT-MERIS, SPOT-HRVIR, and LANDSAT-OLI sensors and was later adapted for
Sentinel-2. It mainly consists in simulating a comprehensive data base of canopy (TOC) reflectances
based on vegetation characteristics and observation and illumination geometry. Neural networks are
then trained to estimate a number of these canopy characteristics (BIOPARs) from the simulated TOC
reflectances along with set corresponding angles defining the observational configuration.

### Quality

 [RD1] reports RMSE
values of 0.89 for LAI, 0.05 for FAPAR, 0.4 for FCOVER, 56 µg/cm2 for CCC and 0.03 g/cm2 for CWC
which demonstrate a good performance of the network. FAPAR and FCOVER show the best
performance, with higher RMSE values for mid-range values of the product. LAI is well estimated up
to values of LAI=6, and increasing uncertainties with LAI, and thus also CCC and CWC because of their
dependency on LAI, are observed. Furthermore, the networks are unbiased between the BIOPAR
variables as expected.

### Links

- [RD1] Weiss, M., Baret, F. (2016). S2ToolBox Level 2 products: LAI, FAPAR, FCOVER, version
1.1, 02/05/2016. http://step.esa.int/docs/extra/ATBD_S2ToolBox_L2B_V1.1.pdf