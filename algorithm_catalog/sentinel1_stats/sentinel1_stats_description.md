# Description

This algorithm derives statistical insights from the Sentinel-1 GRD collection for a selected area and temporal extent. 
It computes temporal statics (e.g., mean, minimum, and maximum backscatter) through openEO processes.


# Performance characteristics

The process computes the temporal statiscts for both  "VH" and "VV" polarization bands. In the workflow, `sigma0-ellipsoid` has been applied to the raw sar data to quantify the backscatter intensity. 

# Examples

Below we show the derived temporal mean for both VV and VH bands, calculated for the area of interest. 

![s1_stats](mean2.png)