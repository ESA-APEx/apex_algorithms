"""
This is an UDP to run the parcel delineation.
"""

import openeo


# Establish connection
connection = openeo.connect("openeo.dataspace.copernicus.eu").authenticate_oidc()

# Load the process graph from JSON file
_process_graph = "parcel_delineation.json"
job = connection.datacube_from_json(_process_graph)

# job options to manage memory
job_options = {
    "driver-memory": "500m",
    "driver-memoryOverhead": "1000m",
    "executor-memory": "1000m",
    "executor-memoryOverhead": "500m",
    "python-memory": "4000m"
}

# excute the job
job.execute_batch(job_options=job_options)
