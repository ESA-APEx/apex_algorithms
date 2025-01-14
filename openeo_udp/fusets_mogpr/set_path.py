import os
import sys
import zipfile
import requests
import functools

from openeo.udf import inspect


def download_file(url, path):
    """
    Downloads a file from the given URL to the specified path.
    """
    response = requests.get(url, stream=True)
    with open(path, "wb") as file:
        file.write(response.content)


def extract_zip(zip_path, extract_to):
    """
    Extracts a zip file from zip_path to the specified extract_to directory.
    """
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)


def add_directory_to_sys_path(directory):
    """
    Adds a directory to the Python sys.path if it's not already present.
    """
    if directory not in sys.path:
        sys.path.insert(0, directory)

@functools.lru_cache(maxsize=5)
def setup_dependencies(dependencies_url,DEPENDENCIES_DIR):
    """
    Main function to set up the dependencies by downloading, extracting,
    and adding necessary directories to sys.path.
    """

    inspect(message="Create directories")
    # Ensure base directories exist
    os.makedirs(DEPENDENCIES_DIR, exist_ok=True)

    # Download and extract dependencies if not already present
    if not os.listdir(DEPENDENCIES_DIR):

        inspect(message="Extract dependencies")
        zip_path = os.path.join(DEPENDENCIES_DIR, "temp.zip")
        download_file(dependencies_url, zip_path)
        extract_zip(zip_path, DEPENDENCIES_DIR)
        os.remove(zip_path)

        # Add the extracted dependencies directory to sys.path
        add_directory_to_sys_path(DEPENDENCIES_DIR)
        inspect(message="Added to the sys path")

setup_dependencies("https://artifactory.vgt.vito.be:443/artifactory/auxdata-public/ai4food/fusets_venv.zip", 'venv')
setup_dependencies("https://artifactory.vgt.vito.be:443/artifactory/auxdata-public/ai4food/fusets.zip", 'venv_static')