# /// script
# dependencies = [
# "onnxruntime",
# ]
# ///

import functools
from typing import Dict

import numpy as np
import xarray as xr
import onnxruntime as ort
from openeo.udf import inspect


@functools.lru_cache(maxsize=1)
def load_onnx_model(model_name: str) -> ort.InferenceSession:
    """
    Loads an ONNX model from the onnx_models folder and returns an ONNX runtime session.

    """
    # The onnx_models folder contains the content of the model archive provided in the job options
    return ort.InferenceSession(f"onnx_models/{model_name}")



def preprocess_input(
    input_xr: xr.DataArray, ort_session: ort.InferenceSession
) -> tuple:
    """
    Preprocess the input DataArray by ensuring the dimensions are in the correct order,
    reshaping it, and returning the reshaped numpy array and the original shape.
    """
    input_xr = input_xr.transpose("y", "x", "bands")
    input_shape = input_xr.shape
    input_np = input_xr.values.reshape(-1, ort_session.get_inputs()[0].shape[1])
    input_np = input_np.astype(np.float32)
    return input_np, input_shape


def run_inference(input_np: np.ndarray, ort_session: ort.InferenceSession) -> tuple:
    """
    Run inference using the ONNX runtime session and return predicted labels and probabilities.
    """
    ort_inputs = {ort_session.get_inputs()[0].name: input_np}
    ort_outputs = ort_session.run(None, ort_inputs)
    predicted_labels = ort_outputs[0]
    return predicted_labels


def postprocess_output(predicted_labels: np.ndarray, input_shape: tuple) -> tuple:
    """
    Postprocess the output by reshaping the predicted labels and probabilities into the original spatial structure.
    """
    predicted_labels = predicted_labels.reshape(input_shape[0], input_shape[1])

    return predicted_labels


def create_output_xarray(
    predicted_labels: np.ndarray, input_xr: xr.DataArray
) -> xr.DataArray:
    """
    Create an xarray DataArray with predicted labels and probabilities stacked along the bands dimension.
    """

    return xr.DataArray(
        predicted_labels,
        dims=["y", "x"],
        coords={"y": input_xr.coords["y"], "x": input_xr.coords["x"]},
    )


def apply_model(input_xr: xr.DataArray) -> xr.DataArray:
    """
    Run inference on the given input data using the provided ONNX runtime session.
    This method is called for each timestep in the chunk received by apply_datacube.
    """

    # Step 1: Load the ONNX model
    inspect(message="load onnx model")
    ort_session = load_onnx_model("EURAC_pvfarm_rf_1_median_depth_15.onnx")

    # Step 2: Preprocess the input
    inspect(message="preprocess input")
    input_np, input_shape = preprocess_input(input_xr, ort_session)

    # Step 3: Perform inference
    inspect(message="run model inference")
    predicted_labels = run_inference(input_np, ort_session)

    # Step 4: Postprocess the output
    inspect(message="post process output")
    predicted_labels = postprocess_output(predicted_labels, input_shape)

    # Step 5: Create the output xarray
    inspect(message="create output xarray")
    return create_output_xarray(predicted_labels, input_xr)


def apply_datacube(cube: xr.DataArray, context: Dict) -> xr.DataArray:
    """
    Function that is called for each chunk of data that is processed.
    The function name and arguments are defined by the UDF API.
    """
    # Define how you want to handle nan values
    cube = cube.fillna(-999999)

    # Apply the model for each timestep in the chunk
    output_data = apply_model(cube)

    return output_data
