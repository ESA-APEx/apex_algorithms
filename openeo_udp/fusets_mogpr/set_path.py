#%%

import os
import sys
import zipfile
import requests
import tempfile
import shutil
import functools

from openeo.udf import inspect

def download_file(url, path):
    """
    Downloads a file from the given URL to the specified path.
    """
    response = requests.get(url, stream=True)
    with open(path, "wb") as file:
        file.write(response.content)

def extract_zip_to_temp(zip_path, temp_dir):
    """
    Extracts a zip file into the given temporary directory.
    """
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(temp_dir)  # Use the existing temp_dir
    return temp_dir

def move_top_level_folder_to_destination(temp_dir, destination_dir):
    """
    Moves each top-level folder from the temporary directory to the destination directory.
    Throws an error if the folder already exists at the destination.
    """
    # Find the top-level folders inside the extracted zip
    for item in os.listdir(temp_dir):
        item_path = os.path.join(temp_dir, item)
        
        if os.path.isdir(item_path):
            # Check if the folder already exists at destination
            dest_path = os.path.join(destination_dir, item)

            if os.path.exists(dest_path):
                # Throw an error if the folder already exists
                raise FileExistsError(f"Error: The folder '{item}' already exists in the destination directory: {dest_path}")

            # Move the folder out of temp and into the destination directory
            shutil.move(item_path, dest_path)


def add_to_sys_path(folder_path):
    """
    Adds the folder path to sys.path.
    """
    if folder_path not in sys.path:
        sys.path.append(folder_path)


@functools.lru_cache(maxsize=5)
def setup_dependencies(dependencies_url):
    """
    Main function to download, unzip, move the top-level folder, and add it to sys.path.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Step 1: Download the zip file
        zip_path = os.path.join(temp_dir, "temp.zip")
        download_file(dependencies_url, zip_path)

        inspect(message="Extract dependencies to temp")
        # Step 2: Extract the zip file to the temporary directory
        extracted_dir = extract_zip_to_temp(zip_path, temp_dir) 

        # Step 3: Move the first top-level folder (dynamically) to the destination
        destination_dir = os.getcwd()  # Current working directory
        inspect(message="Move top-level folder to destination")
        moved_folder = move_top_level_folder_to_destination(extracted_dir, destination_dir)

        # Step 4: Add the folder to sys.path
        add_to_sys_path(moved_folder)
        inspect(message="Added to the sys path") 


setup_dependencies("https://artifactory.vgt.vito.be:443/artifactory/auxdata-public/ai4food/fusets_venv.zip")