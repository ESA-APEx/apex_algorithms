# FORCE Time Series Analysis (TSA)

FORCE (Framework for Operational Radiometric Correction for Environmental Monitoring) is a processing framework for Sentinel-2 and Landsat imagery. It supports the generation of Analysis Ready Data Cubes (level 2 processing) and many higher level processing operations such as time series analysis. FORCE is developed by Prof. David Frantz (Geoinformatics - Spatial Data Science, Trier University) and the FORCE Open Source community. Please make sure to [acknowledge their work accordingly](https://force-eo.readthedocs.io/en/latest/policy/citation.html) when processing with FORCE.

This process provides the FORCE Time Series Analysis, part of the [Higher Level Processing System](https://force-eo.readthedocs.io/en/latest/components/higher-level/index.html) to produce
Time Series Statistics and other analysis products in the FORCE data cube format.
The process supports [many of the parameters](https://esa-apex.github.io/apex_toolbox_documentation/docs/force/guide/parametrization.html) of the FORCE Time Series Analysis module.

As an input, the `force_tsa` process requires a STAC catalog referring to FORCE level 2 data cube as produced by the `force_level2` process.

The FORCE toolbox was cloudified as part of the [APEx toolbox cloudification activity](https://apex.esa.int/services/toolbox-cloudification).

> Please note that this is an experimental integration of FORCE into openEO, which is not suitable for large scale processing. For an overview of features and limitations compared to running FORCE locally, please consult the [official documentation](https://esa-apex.github.io/apex_toolbox_documentation/docs/force/feature_overview.html).

> Please be aware that FORCE processing uses FORCE's native data cube model instead of openEO data cubes. Therefore, further processing of the data in openEO is limited to the FORCE Time Series Analysis
> process.

## Features

- Dedicated openEO process `force_tsa` to generate FORCE Analysis Ready Data Cubes
- STAC generation for FORCE data cubes produced by the process


## Example usage


```Python
import openeo
from openeo.rest.stac_resource import StacResource
from openeo.internal.graph_building import PGNode


connection = openeo.connect("openeo.dataspace.copernicus.eu").authenticate_oidc()



# Select a FORCE level2 data cube to process. You must run the `force_level2` process first to create such a cube.
# See the user guide and example notebook for a full example on how to do this.
WORKSPACE_URL = "https://s3.waw4-1.cloudferro.com/apex-force-results-waw4-1-exotc5yuexi2c5tvwqhoivj62fz8v0uupy0me"

# merge = <insert the merge path to your data cube here>
l2_catalog_url = f"{WORKSPACE_URL}/{merge}/catalog.json"

# Create the process graph
processing_name = "FORCE_TSA"

tsa_stac_resource = openeo.rest.stac_resource.StacResource(
    graph=openeo.internal.graph_building.PGNode(
        process_id="force_tsa",
        arguments={
            "stac_url": l2_catalog_url
            "name": processing_name,
            "date_range": temporal_extent,
            "output_stm": True,
            # update process parameters
            "x_tile_range": [30, 32],
            "y_tile_range": [30, 30],
            "stm": ["AVG", "MAX"],
        },
    ),
    connection=connection,
)

# Run processing
tsa_job = tsa_stac_resource.create_job(title=processing_name)
tsa_job.start_and_wait()

# Download results (alternatively: Continue processing without download with Time Series Analysis. Check out the guide!)

tsa_results = tsa_job.get_results()
tsa_results.download_files("force-tsa-results")
```

## Documentation

- [FORCE on CDSE using openEO](https://esa-apex.github.io/apex_toolbox_documentation/docs/force/): Main documentation site for the FORCE integration into CDSE openEO. Part of the APEx [toolbox documentation portal](https://esa-apex.github.io/apex_toolbox_documentation/docs/)
    - [Features and Limitations](https://esa-apex.github.io/apex_toolbox_documentation/docs/force/feature_overview.html)
    - [User Guide](https://esa-apex.github.io/apex_toolbox_documentation/docs/force/guide/intro.html)

- [FORCE](https://force-eo.readthedocs.io/) Documentation of the FORCE processing engine
- [Example notebooks](https://github.com/bcdev/apex-force-openeo/tree/main/examples)

