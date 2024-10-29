# Description

This algorithm derives temporal statistics from the Sentinel-1 GRD collection for the selected spatial- and temporal extent of interest. In order to callibrate the SAR backscatter signal, `sigma0-ellipsoid` has been applied within this workflow. 


# Performance characteristics
The algorithm was evaluated for a spatial extent of 20x20km, for a temporal period of 3 months. The total cost for the performed evaluation was equal to 4 credits, thereby highlighting the efficiency of the underlying algorithm.


# Examples

Below we show the derived minimum and maximum values for both VV and VH bands, calculated for the 20x20 km2 area of interest. 

![s1_stats](https://raw.githubusercontent.com/ESA-APEx/apex_algorithms/main/algorithm_catalog/sentinel1_stats/sentinel1.png)