import json
import sys
from pathlib import Path

import openeo
from openeo.api.process import Parameter
from openeo.processes import array_create
from openeo.rest.udp import build_process_dict

# TODO #15 where to put reusable helpers? e.g. load description from README.md, dummy openeo connection, properly write to JSON file, ...


def generate() -> dict:
    # TODO: use/inject dummy connection instead of concrete one? (See cdse_marketplace_services)
    c = openeo.connect("openeofed.dataspace.copernicus.eu")

    spatial_extent = Parameter.spatial_extent()
    temporal_extent = Parameter.temporal_interval(name="temporal_extent")
    schema = {
        "type": "string",
        "enum": ["B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12"],
    }
    bands_param = Parameter.array(
        name="bands",
        description="Sentinel-2 L2A bands to include in the composite.",
        item_schema=schema,
        default=["B04", "B03", "B02"],
        optional=True,
    )

    max_cloud_description = """The maximum cloud cover percentage to filter Sentinel-2 inputs at full product level.
    By reducing the percentage, fewer input products are considered, which also potentially increases the risk of missing valid data.
    We do not recommend setting it higher than 95%, as this decreases performance by reading very cloudy areas with little chance of finding good pixels.

    For composites over large time ranges, a reduced value can help to consider only good quality input products, with few undetected clouds.
    """
    max_cloud_cover_param = Parameter.number(
        name="max_cloud_cover",
        description=max_cloud_description,
        default=75.0,
        optional=True,
    )

    scl = c.load_collection(
        "SENTINEL2_L2A",
        temporal_extent=temporal_extent,
        spatial_extent=spatial_extent,
        bands=["SCL"],
        max_cloud_cover=max_cloud_cover_param,
    )

    def scl_to_masks(scl_layer):
        to_mask = openeo.processes.any(
            array_create(
                [
                    (scl_layer == SCL_LEGEND["cloud_shadows"]),
                    (scl_layer == SCL_LEGEND["cloud_medium_probability"]),
                    (scl_layer == SCL_LEGEND["cloud_high_probability"]),
                    (scl_layer == SCL_LEGEND["thin_cirrus"]),
                    scl_layer == SCL_LEGEND["saturated_or_defective"],
                    scl_layer == SCL_LEGEND["water"],
                    scl_layer == SCL_LEGEND["snow"],
                    scl_layer == SCL_LEGEND["no_data"],
                ]
            ),
        )

        return to_mask

    SCL_LEGEND = {
        "no_data": 0,
        "saturated_or_defective": 1,
        "dark_area_pixels": 2,
        "cloud_shadows": 3,
        "vegetation": 4,
        "not_vegetated": 5,
        "water": 6,
        "unclassified": 7,
        "cloud_medium_probability": 8,
        "cloud_high_probability": 9,
        "thin_cirrus": 10,
        "snow": 11,
    }

    cloud_mask = scl.apply(process=scl_to_masks)

    ndvi_bands = c.load_collection(
        "SENTINEL2_L2A",
        temporal_extent=temporal_extent,
        spatial_extent=spatial_extent,
        bands=["B04", "B08"],
        max_cloud_cover=max_cloud_cover_param,
    )

    ndvi_bands = ndvi_bands.mask(cloud_mask)

    ndvi = ndvi_bands.ndvi(nir="B08", red="B04").add_dimension(
        "bands2", "ndvi", type="bands"
    )

    def max_ndvi_selection(ndvi):
        max_ndvi = ndvi.max()
        return ndvi.array_apply(lambda x: x != max_ndvi)

    rank_mask = ndvi.apply_dimension(dimension="t", process=max_ndvi_selection)
    combined_mask = rank_mask.merge_cubes(cloud_mask, overlap_resolver="max")

    rgb_bands = c.load_collection(
        "SENTINEL2_L2A",
        temporal_extent=temporal_extent,
        spatial_extent=spatial_extent,
        bands=bands_param,  # ,"B8A","B11","B12"
        max_cloud_cover=max_cloud_cover_param,
    )

    composite = rgb_bands.mask(combined_mask).max_time()

    returns = {
        "description": "A data cube with the newly computed values.\n\nAll dimensions stay the same, except for the dimensions specified in corresponding parameters. There are three cases how the dimensions can change:\n\n1. The source dimension is the target dimension:\n   - The (number of) dimensions remain unchanged as the source dimension is the target dimension.\n   - The source dimension properties name and type remain unchanged.\n   - The dimension labels, the reference system and the resolution are preserved only if the number of values in the source dimension is equal to the number of values computed by the process. Otherwise, all other dimension properties change as defined in the list below.\n2. The source dimension is not the target dimension. The target dimension exists with a single label only:\n   - The number of dimensions decreases by one as the source dimension is 'dropped' and the target dimension is filled with the processed data that originates from the source dimension.\n   - The target dimension properties name and type remain unchanged. All other dimension properties change as defined in the list below.\n3. The source dimension is not the target dimension and the latter does not exist:\n   - The number of dimensions remain unchanged, but the source dimension is replaced with the target dimension.\n   - The target dimension has the specified name and the type other. All other dimension properties are set as defined in the list below.\n\nUnless otherwise stated above, for the given (target) dimension the following applies:\n\n- the number of dimension labels is equal to the number of values computed by the process,\n- the dimension labels are incrementing integers starting from zero,\n- the resolution changes, and\n- the reference system is undefined.",
        "schema": {
            "type": "object",
            "subtype": "datacube"
        }
    }

    return build_process_dict(
        process_graph=composite,
        process_id="max_ndvi_composite",
        summary="Sentinel-2 max NDVI composite at 10m resolution.",
        description=(
            Path(__file__).parent / "max_ndvi_composite_description.md"
        ).read_text(),
        parameters=[
            spatial_extent,
            temporal_extent,
            max_cloud_cover_param,
            bands_param,
        ],
        returns=returns,
        categories=["sentinel-2", "composites", "vegetation"]
    )


if __name__ == "__main__":
    # TODO: how to enforce a useful order of top-level keys?
    json.dump(generate(), sys.stdout, indent=2)


def test_run():
    c = openeo.connect("openeofed.dataspace.copernicus.eu").authenticate_oidc()

    bbox = dict(west=7.998047, south=55.804368, east=9.5, north=56.4)
    composite = c.datacube_from_process(
        "max_ndvi_composite",
        namespace="https://raw.githubusercontent.com/ESA-APEx/apex_algorithms/vito/max_ndvi_composite/openeo_udp/max_ndvi_composite.json",
        temporal_extent=["2022-03-01", "2023-06-01"],
        spatial_extent=bbox,
    )
    composite.execute_batch()
