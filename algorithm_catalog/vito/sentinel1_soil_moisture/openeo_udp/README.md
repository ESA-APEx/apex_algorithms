Computes surface soil moisture (SSM) from Sentinel‑1 GRD data (VV polarisation) based on the change detection method described in the Sentinel‑1 for Surface Soil Moisture project.

**Formula**: 
SSM = (σ⁰_current - σ⁰_min) / (σ⁰_max - σ⁰_min)

where σ⁰_min and σ⁰_max are the minimum and maximum backscatter over the reference period (typically 3 years).
            
**References**:
-https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-1/soil_moisture_estimation/"
-https://doi.org/10.1016/j.dib.2021.107647"
