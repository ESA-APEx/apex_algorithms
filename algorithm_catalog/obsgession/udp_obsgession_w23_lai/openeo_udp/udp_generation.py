"""
UDP to generate obsgession W23 LAI datasets.
A few manual stepes need to be executed
On resolution are e few checks which need to be circumvented
replace 1001 with
{
            "from_parameter": "resolution"
          }
same for temporal aggregation function
replace median with
{
            "from_parameter": "temp_aggregator"
          }
concat does not work with the current version of openeo. So the filename prefix is adapted manually in the json.
"textconcat1": {
      "process_id": "text_concat",
      "arguments": {
        "data": [
          "EO4Diversity_LAI_",
          {"from_parameter": "binning_period"},
          "_",
          {"from_parameter": "param_temp_aggregator"},
          "_"]
      }
    }

"""
import json
import openeo
from openeo.api.process import Parameter
from openeo.processes import if_, eq
from openeo.rest.udp import build_process_dict
import os
import pathlib
from eo_processing.openeo.preprocessing import extract_S2_datacube
from eo_processing.config.settings import get_job_options, get_collection_options, get_advanced_options
from eo_processing.utils.metadata import get_base_metadata
from openeo.processes import array_create
from openeo.processes import ProcessBuilder
from typing import Any, Union


# we use the base functionality of openEO
def compute_LAI(bands):
    # select bands
    B2 = bands["B02"] * 0.0001
    B4 = bands["B04"] * 0.0001
    B8 = bands["B08"] * 0.0001

    # create EVI
    EVI = 2.5 * (B8 - B4) / (B8 + 6.0 * B4 - 7.5 * B2 + 1.0)

    # create LAI
    LAI = 4.0543 * EVI + 1.7901
    return array_create([LAI])

def build_collection_condition(variable: Union[str, Parameter], label: str, accept: Any, reject: Any) -> ProcessBuilder:
    """
    Helper function that will construct an if-else structure using the `if_` openEO process. If the value of the
    variable parameter matches with the given label, the accept function is executed. If not the reject function is
    executed.

    :param variable: Variable that will be used to check if it matches the `label`
    :param label: String representing the text with which the collection should match
    :param accept: Function that is executed when the collection matches the label
    :param reject: Function that is executed when the collection does not match the label
    :return:
    """
    return if_(eq(variable, label, case_sensitive=False), accept, reject)

def generate() -> dict:
    """
    Generate the UDP process graph for CropSAR1d.
    """
    eoconn = openeo.connect("openeo.vito.be").authenticate_oidc()

    # define input parameters
    print("defining parameters")
    param_start_date = Parameter.string(
    name="start_date",
    description="Start date of the observation period in format YYYY-MM-DD.",
    )
    param_end_date = Parameter.string(
        name="end_date",
        description="End date of the observation period in format YYYY-MM-DD.",
    )
    param_binning_period= Parameter.string(
        name="binning_period",
        default='monthly',
        #allowed_values=['hour','day','week','dekad','month','season','tropical-season','year','decade','decade-ad'],
        description="The temporal binning period. Please have a look at openeo documentation of the process "
                    "aggregate_temporal_period for more information",
    )

    param_temp_aggregator = Parameter.string(
        name="temp_aggregator",
        description="The temporal aggregation function. Please have a look at openeo documentation of the process "
                    "aggregate_temporal_period for more information",
        values=["min", "max", "mean", "median"],
        default="mean"
    )

    # set up the UDP parameters
    param_AOI = Parameter(name="aoi",
        description="""the AOI should be stet as an openEO BBOX dict. It defines the boundaries of the area of interest.
        The coordinates are given in the order of west, south, east, north.""",
        schema= {"title": "Bounding Box",
            "type": "object",
            "subtype": "bounding-box",
            "required": ["west", "south","east","north"],
            "properties": {
                "west": {
                "description": "West (lower left corner, coordinate axis 1).",
                "type": "number"
                },
                "south": {
                "description": "South (lower left corner, coordinate axis 2).",
                "type": "number"
                },
                "east": {
                "description": "East (upper right corner, coordinate axis 1).",
                "type": "number"
                },
                "north": {
                "description": "North (upper right corner, coordinate axis 2).",
                "type": "number"
                },
                "crs": {
                "description": "Coordinate reference system of the extent, specified as as [EPSG code](http://www.epsg-registry.org/) or [WKT2 CRS string](http://docs.opengeospatial.org/is/18-010r7/18-010r7.html).",
                "anyOf": [
                    {
                    "title": "EPSG Code",
                    "type": "integer",
                    "subtype": "epsg-code",
                    "minimum": 1000,
                    "examples": [
                        3035
                    ]
                    },
                    {
                    "title": "WKT2",
                    "type": "string",
                    "subtype": "wkt2-definition"
                    }
                ],
                "default": 3035
                }
            }
            },)
    param_epsg = Parameter.number(
        name="epsg",
        description="The desired output projection system.",
    )

    provider = 'cdse'
    resolution = 20.0

    # use the eo_processing package to prepare the Sentinel-2 time series for the LAI calculation
    processing_options = get_advanced_options(
        provider=provider,
        target_crs=param_epsg,
        resolution=resolution,
        ts_interpolation=False,
        ts_interval=None,
        slc_masking='mask_scl_dilation',
        S2_max_cloud_cover=95,
        S2_bands=["B02", "B04", "B08"],
        skip_check_S2=True,
    )

    collection_options = get_collection_options(provider=provider)
    job_options = get_job_options(provider=provider, task='raw_extraction')
    s2_cube = extract_S2_datacube(eoconn,
                                param_AOI,
                                param_start_date,
                                param_end_date,
                                **collection_options,
                                **processing_options
                                )

    LAI_cube = s2_cube.apply_dimension(
        dimension="bands",
        process=compute_LAI,
        context={"parallel": True,
                "TileSize": 128}
    ).rename_labels("bands", ["LAI"])

    # mask out values above 7.5
    lai_mask = (LAI_cube < 0) | (LAI_cube > 7.5)
    LAI_cube = LAI_cube.mask(lai_mask)

    # temporal aggregation depending on the parameter value
    LAI_cube_agg = eoconn.datacube_from_process(
        process_id="if",
        value=eq(param_temp_aggregator, "median", case_sensitive=False),
        accept=LAI_cube.aggregate_temporal_period(period=param_binning_period, reducer='median'),
        reject=eoconn.datacube_from_process(
            process_id="if",
            value=eq(param_temp_aggregator, "mean", case_sensitive=False),
            accept=LAI_cube.aggregate_temporal_period(period=param_binning_period, reducer='mean'),
            reject=eoconn.datacube_from_process(
                process_id="if",
                value=eq(param_temp_aggregator, "max", case_sensitive=False),
                accept=LAI_cube.aggregate_temporal_period(period=param_binning_period, reducer='max'),
                reject=LAI_cube.aggregate_temporal_period(period=param_binning_period, reducer='min')
            )
        ),
    )
    
    # load the WorldCover 2021 for masking to tree cover
    tree_cube = eoconn.load_collection("ESA_WORLDCOVER_10M_2021_V2",
                                        spatial_extent=param_AOI,
                                        bands=["MAP"]
                                        )
    tree_cube = tree_cube.resample_spatial(projection=param_epsg,
                             resolution=resolution)
    tree_cube = tree_cube.drop_dimension("t")

    tree_mask = ~ (tree_cube == 10)

    LAI_cube_mask_tree = LAI_cube_agg.mask(tree_mask)

    # load vector file for temperate forests and also mask
    mask_url = 'https://s3.waw4-1.cloudferro.com/swift/v1/obsgession-waw4-1-b2rm8flkntfkatia3zzm7av6pzt3dsmrd2uc87dbvhnml/udp_data/EU_temperate_forests_distribution.parquet'
    LAI_cube_mask_url = LAI_cube_mask_tree.mask_polygon(mask_url)
 
    # force Uint8 and scaling (scal_factor = 1./32)
    LAI_cube_mask_url = LAI_cube_mask_url.linear_scale_range(0, 7.5, 0, 240)
 
    # prepare metadata
    file_meta  = get_base_metadata(project='OBSGESSION')
    file_meta.update(description=f'Generation of EO4Diversity conform high-resolution temperate forests optimized LAI products based on Sentinel-2 following the OBSGESSION W2.3 benchmarking.',
                    tiling_grid='LAEA',
                    time_start=param_start_date,
                    time_end=param_end_date)
    bands_meta = {"LAI": {"description": "LAI",
                                "unit": "m2*m-2",
                                "valid_range": '[0, 240]',
                                "scale": 1./32.,
                                "offset": 0,
                                "nodata_value": 255}}

    saved_result = LAI_cube_mask_url.save_result(
        format="GTiff",
        options={
        "file_metadata":file_meta,
        "bands_metadata":bands_meta}
    )
    return build_process_dict(
        process_graph=saved_result.flat_graph(),
        process_id="noplaceholder",
        description=(pathlib.Path(__file__).parent / "README.md").read_text(),
        parameters=[param_AOI, param_start_date, param_end_date, param_binning_period, param_temp_aggregator, param_epsg],
        default_job_options=job_options
    )


if __name__ == "__main__":
    process_graph = generate()

    flat_graph = process_graph["process_graph"]

    # Add a text_concat node for dynamic filename prefixes. The GTiff backend expects a string for the filename prefix, so we need to concatenate the different parameters into a single string.
    flat_graph["textconcat1"] = {
        "process_id": "text_concat",
        "arguments": {
            "data": [
                "EO4Diversity_LAI_",
                {"from_parameter": "binning_period"},
                "_",
                {"from_parameter": "temp_aggregator"},
                "_",
            ]
        },
    }

    for node in flat_graph.values():
        if node.get("process_id") == "save_result":
            node["arguments"]["options"]["filename_prefix"] = {"from_node": "textconcat1"}
            break

    # dump to json file to be usable as UDP
    json_str = json.dumps(process_graph, indent=2)
    
    # Replace the literal resolution value with parameter reference
    json_str = json_str.replace(': 20.0', ': {"from_parameter": "resolution"}')

    with open("udp_obsgession_w23_lai.json", "w") as f:
        f.write(json_str)
    print("Process graph saved to udp_obsgession_w23_lai.json")