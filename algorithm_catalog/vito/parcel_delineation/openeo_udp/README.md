# Parcel Delineation
Parcel delineation refers to the identification and marking of agricultural boundaries. 
This process is *essential* for tasks such as crop yield estimation and land management. 
Accurate delineation also aids in classifying crop types and managing farmland more effectively.
 
## Algorithm for Parcel Delineation Using Sentinel-2 Data  

This algorithm performs parcel delineation using Sentinel-2 data and a pre-trained`U-Net machine learning model. The process involves the following steps:
1. **Pre-processing Sentinel-2 Data:**
   1. Filter data to ensure a maximum of 10% cloud coverage.  
   2. Apply a cloud mask based on the SCL layer.  
2. **Compute NDVI:**
   1. The Normalized Difference Vegetation Index (NDVI) is calculated from the pre-processed data.
   2. The NDVI serves as input to the U-Net model. 
3. **Predict Delineation:**
   1. The U-Net model predicts parcel delineation boundaries. 
4. **Optimization and Labeling:**
   1. Apply a Sobel filter to enhance edge detection.  
   2. Use Felzenszwalb's algorithm for segmentation and labeling of delineated parcels.
 