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
# Establish connection to OpenEO instance (note that authentication is not necessary to just build the UDP)
connection = openeo.connect(url="openeo.vito.be")

# set up the UDP parameters
#temporal
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
                "aggregate_temporal_period for more information"
)

param_temp_aggregator = Parameter.string(
    name="temp_aggregator",
    default='mean',
    #allowed_values=['min', 'max', 'mean', 'median'],
    description="The temporal aggregation function. Please have a look at openeo documentation of the process "
                "aggregate_temporal_period for more information",
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


param_resolution = Parameter.number(
    name="resolution",
    description="The desired output resolution, specified in units of the projection system.",
)

param_epsg = Parameter.number(
    name="epsg",
    description="The desired output projection system.",
)

provider = 'cdse'
resolution = 1001
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

s2_cube = extract_S2_datacube(connection,
                              param_AOI,
                              param_start_date,
                              param_end_date,
                              **collection_options,
                              **processing_options)


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

LAI_cube = s2_cube.apply_dimension(
    dimension="bands",
    process=compute_LAI,
    context={"parallel": True,
             "TileSize": 128}
).rename_labels("bands", ["LAI"])

# mask out values above 7.5
lai_mask = (LAI_cube < 0) | (LAI_cube > 7.5)
LAI_cube = LAI_cube.mask(lai_mask)


LAI_cube = if_(eq(param_temp_aggregator,'median'), LAI_cube.aggregate_temporal_period(period=param_binning_period, reducer='median'),
    if_(eq(param_temp_aggregator,'mean'), LAI_cube.aggregate_temporal_period(period=param_binning_period, reducer='mean'),
        if_(eq(param_temp_aggregator,'max'), LAI_cube.aggregate_temporal_period(period=param_binning_period, reducer='max'),
            if_(eq(param_temp_aggregator,'min'), LAI_cube.aggregate_temporal_period(period=param_binning_period, reducer='min')))))

#LAI_cube = LAI_cube.aggregate_temporal_period(period=param_binning_period, reducer='mean')

# load the WorldCover 2021 for masking to tree cover
tree_cube = connection.load_collection("ESA_WORLDCOVER_10M_2021_V2",
                                       spatial_extent=param_AOI,
                                       bands=["MAP"]
                                       )
tree_cube = tree_cube.resample_spatial(projection=param_epsg,
                             resolution=resolution)
tree_cube = tree_cube.drop_dimension('t')
tree_mask = ~ (tree_cube == 10)
LAI_cube = LAI_cube.mask(tree_mask)

# load vector file for temperate forests and also mask
mask_url = 'https://s3.waw4-1.cloudferro.com/swift/v1/obsgession-waw4-1-b2rm8flkntfkatia3zzm7av6pzt3dsmrd2uc87dbvhnml/udp_data/EU_temperate_forests_distribution.parquet'
LAI_cube = LAI_cube.mask_polygon(mask_url)

# force Uint8 and scaling (scal_factor = 1./32)
LAI_cube = LAI_cube.linear_scale_range(0, 7.5, 0, 240)

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
#concat =  text_concat([param_binning_period,param_temp_aggregator],separator="_").__str__()
saved_result = LAI_cube.save_result(
    format="GTiff",
    options={
    "file_metadata":file_meta,
    "bands_metadata":bands_meta,
    "filename_prefix":f"_concat_"}
)

description = """
EO4Diversity EVI-LAI algorithm to produce the Leaf Area Index product.
"""

spec = build_process_dict(
    process_id="udp_obsgession_w23_lai",
    summary="calculates the LAI datasets for wa certain temporal spatial domain, aggregated to a specific temporal binning period and temporal aggregation function.",
    description=description.strip(),
    parameters=[
        param_start_date,
        param_end_date,
        param_binning_period,
        param_temp_aggregator,
        param_AOI,
        param_epsg,
        param_resolution,
    ],
    process_graph=saved_result,
    default_job_options=job_options
)

# dump to json file to be usable as UDP
this_script = pathlib.Path(__file__)
json_file = os.path.normpath(os.path.join(this_script.parent, 'json', this_script.name.lower().split('.')[0] + '.json'))
print(f"Writing UDP to {json_file}")
with open(json_file, "w", encoding="UTF8") as f:
    json.dump(spec, f, indent=2)
