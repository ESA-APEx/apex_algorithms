# Description

Predicts wind turbine locations for a given area and year. It analyzes Sentinel-2 images from October of the previous year to March of the requested year to generate results. The output is a GeoJSON file containing bounding boxes that indicate detected wind turbines. Each bounding box includes the date of the Sentinel-2 image in which the turbine was identified and the model’s confidence probability for the detection.

Restriction:_ This service can only be executed as a batch service. Please pay attention to the job_options that are provided in the example as these are required to execute the service.



# Performance characteristics

...

# Examples

Below we overlay a Sentinel2-RGB image with the ML classification, thereby highlighting the detected areas.

![wind_turbine_output](wind_turbine_example.png)

# Literature references

...

# Known limitations

...

# Known artifacts

...