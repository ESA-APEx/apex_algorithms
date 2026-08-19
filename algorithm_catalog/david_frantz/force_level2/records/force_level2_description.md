# FORCE level 2

FORCE (Framework for Operational Radiometric Correction for Environmental Monitoring) is a processing framework for Sentinel-2 and Landsat imagery. It supports the generation of Analysis Ready Data Cubes (level 2 processing) and many higher level processing operations such as time series analysis. FORCE is developed by Prof. David Frantz (Geoinformatics - Spatial Data Science, Trier University) and the FORCE Open Source community. Please make sure to [acknowledge their work accordingly](https://force-eo.readthedocs.io/en/latest/policy/citation.html) when processing with FORCE.

This process provides the FORCE [level 2 processing system](https://force-eo.readthedocs.io/en/latest/components/lower-level/level2/index.html) to produce Analysis Ready Data Cubes from Sentinel-2 L1C data.
The process supports [many of the parameters](https://esa-apex.github.io/apex_toolbox_documentation/docs/force/guide/parametrization.html) of the FORCE level 2 processing system.

The FORCE toolbox was cloudified as part of the [APEx toolbox cloudification activity](https://apex.esa.int/services/toolbox-cloudification).

> Please note that this is an experimental integration of FORCE into openEO, which is not suitable for large scale processing. For an overview of features and limitations compared to running FORCE locally, please consult the [official documentation](https://esa-apex.github.io/apex_toolbox_documentation/docs/force/feature_overview.html).

> Please be aware that FORCE processing uses FORCE's native data cube model instead of openEO data cubes. Therefore, further processing of the data in openEO is limited to the FORCE Time Series Analysis
> process.

## Features

- Dedicated openEO process `force_level2` to generate FORCE Analysis Ready Data Cubes
- STAC generation for FORCE data cubes produced by the process
- Automatic Sentinel-2 and Copernicus DEM input data staging
- Asynchronous further processing with FORCE Time Series Analysis on CDSE without download of level 2 products using OpenEO workspaces.


## Example usage


```Python
import openeo
from openeo.rest.stac_resource import StacResource
from openeo.internal.graph_building import PGNode


connection = openeo.connect("openeo.dataspace.copernicus.eu").authenticate_oidc()


# Select a STAC item to process (collections, catalogs and item collections are also supported!)
stac_item_url = "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l1c/items/S2A_MSIL1C_20260419T100711_N0512_R022_T32TPQ_20260419T152521"

# Create the process graph
processing_name = "FORCE_level2"
force_l2_stac_resource = StacResource(
    graph=PGNode(
        process_id="force_level2",
        arguments={
            "stac_url": stac_item_url,
            "name": processing_name,
            "do_brdf": True,
            # other FORCE level 2 parameters
        },
    ),
    connection=connection,
)

# Run processing
l2_job = force_l2_stac_resource.create_job(title=processing_name)
l2_job.start_and_wait()

# Download results (alternatively: Continue processing without download with Time Series Analysis. Check out the guide!)

l2_results = l2_job.get_results()
l2_results.download_files("force-level2-results")
```

## Documentation

- [FORCE on CDSE using openEO](https://esa-apex.github.io/apex_toolbox_documentation/docs/force/): Main documentation site for the FORCE integration into CDSE openEO. Part of the APEx [toolbox documentation portal](https://esa-apex.github.io/apex_toolbox_documentation/docs/)
    - [Features and Limitations](https://esa-apex.github.io/apex_toolbox_documentation/docs/force/feature_overview.html)
    - [User Guide](https://esa-apex.github.io/apex_toolbox_documentation/docs/force/guide/intro.html)

- [FORCE](https://force-eo.readthedocs.io/) Documentation of the FORCE processing engine
- [Example notebooks](https://github.com/bcdev/apex-force-openeo/tree/main/examples)

