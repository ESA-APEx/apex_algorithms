import os
import site
import sys
import zipfile

import requests

# Fixed directories for dependencies and model files
DEPENDENCIES_DIR = "onnx_dependencies"
MODEL_DIR = "model_files"

def download_file(url, path):
    """
    Downloads a file from the given URL to the specified path.
    """
    response = requests.get(url, stream=True)
    with open(path, "wb") as file:
        file.write(response.content)
    print(f"Downloaded file from {url} to {path}")


def extract_zip(zip_path, extract_to):
    """
    Extracts a zip file from zip_path to the specified extract_to directory.
    """
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)
    os.remove(zip_path)  # Clean up the zip file after extraction
    print(f"Extracted {zip_path} to {extract_to}")


def add_directory_to_sys_path(directory):
    """
    Adds a directory to the Python sys.path if it's not already present.
    """
    if directory not in sys.path:
        site.addsitedir(directory)
        print(f"Added {directory} to sys.path")


def setup_model_and_dependencies(model_url, dependencies_url):
    """
    Main function to set up the model and dependencies by downloading, extracting,
    and adding necessary directories to sys.path.
    """
    # Ensure base directories exist
    os.makedirs(DEPENDENCIES_DIR, exist_ok=True)
    os.makedirs(MODEL_DIR, exist_ok=True)

    # Download and extract dependencies if not already present
    if not os.listdir(DEPENDENCIES_DIR):
        zip_path = os.path.join(DEPENDENCIES_DIR, "temp.zip")
        download_file(dependencies_url, zip_path)
        extract_zip(zip_path, DEPENDENCIES_DIR)

        # Add the extracted dependencies directory to sys.path
        # Assuming only one main subdirectory in dependencies
        extracted_folders = [f.path for f in os.scandir(DEPENDENCIES_DIR) if f.is_dir()]
        if extracted_folders:
            add_directory_to_sys_path(extracted_folders[0])

    # Download and extract model if not already present
    if not os.listdir(MODEL_DIR):
        zip_path = os.path.join(MODEL_DIR, "temp.zip")
        download_file(model_url, zip_path)
        extract_zip(zip_path, MODEL_DIR)
