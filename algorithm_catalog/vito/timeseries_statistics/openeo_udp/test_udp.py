import openeo

connection = openeo.connect("openeo.dataspace.copernicus.eu").authenticate_oidc()

geometry = {
    "type": "Polygon",
    "coordinates": [[[4.97, 51.19], [5.07, 51.19], [5.07, 51.28], [4.97, 51.28], [4.97, 51.19]]],
}
temporal_extent = ["2025-05-01", "2025-07-31"]

collection_id = "SENTINEL2_L2A"
bands = ["B04", "B08"]
period = "month"

cube = connection.datacube_from_json(
    "./timeseries_statistics.json",
    parameters={
        "geometry": geometry,
        "temporal_extent": temporal_extent,
        "collection_id": collection_id,
        "bands": bands,
        "period": period,
    },
)
cube

job = cube.create_job()
job.start_and_wait()
