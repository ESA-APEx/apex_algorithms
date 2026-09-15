import xarray
import numpy as np
import pandas as pd

from openeo.udf import inspect

"""Spectral Angle Mapping UDF for Sentinel-2 based material matching.

This UDF compares each pixel spectrum against a USGS-derived reference library
and returns the index of the best matching reference signature.
"""


def compute_sam_w_nan(
    img: np.ndarray,
    usgs_df: pd.DataFrame,
    min_bands: int=12,
) -> np.ndarray:
    """Compute SAM

    Only overlapping finite bands are used for each pixel-reference pair.
    Pixels with fewer than min_bands valid overlaps are marked as no match.
    """
    bands, height, width = img.shape
    # Flatten spatial dimensions so SAM can be computed in matrix form.
    pixel_spectra = img.reshape(bands, -1).T
    # Transpose library so each row corresponds to one reference signature.
    usgs_matrix = usgs_df.T.values

    n_pix = pixel_spectra.shape[0]
    n_mat = usgs_matrix.shape[0]

    # Pre-fill with +inf so non-computable matches remain easy to detect.
    angles = np.full((n_pix, n_mat), np.inf, dtype=np.float32)

    # Compute pixel finite mask once and reuse it for all reference signatures.
    Xfinite = np.isfinite(pixel_spectra)

    for j in range(n_mat):
        y = usgs_matrix[j]
        yfinite = np.isfinite(y)

        valid = Xfinite & yfinite[None, :]
        n_valid = valid.sum(axis=1)

        # Enforce a minimum number of overlapping bands per pixel-match pair.
        ok = n_valid >= min_bands
        if not np.any(ok):
            continue

        # Compute dot product and norms only over valid overlap.
        Xv = np.where(valid, pixel_spectra, 0.0)
        yv = np.where(yfinite, y, 0.0)

        dot = (Xv * yv[None, :]).sum(axis=1)
        nx = np.sqrt((Xv * Xv).sum(axis=1))
        ny = np.sqrt((yv * yv).sum())

        # Add a small epsilon to keep the denominator numerically safe.
        denom = nx * ny + 1e-12
        cosang = np.clip(dot / denom, -1.0, 1.0)

        # Convert cosine similarity to spectral angle in radians.
        ang = np.arccos(cosang).astype(np.float32)
        angles[ok, j] = ang[ok]

    # Select the reference with minimum angle for each pixel.
    best = np.argmin(angles, axis=1).reshape(height, width)
    # Pixels that never reached the min_bands threshold remain as no match.
    best[np.isinf(angles).all(axis=1).reshape(height, width)] = -1
    return best

def compute_sam_wo_nan(img: np.ndarray, usgs_df: pd.DataFrame) -> np.array:
    """Compute SAM for fully valid arrays without missing values."""
    bands, height, width = img.shape
    inspect(data=img.shape, message="SAM no-NaN path: input image shape", level='debug')
    # Flatten to [pixels, bands] to vectorize pairwise comparisons.
    pixel_spectra = img.reshape(bands, -1).T

    # Normalize each pixel vector so comparison focuses on spectral shape.
    pixel_norms = np.linalg.norm(pixel_spectra, axis=1, keepdims=True)
    inspect(data=pixel_norms.shape, message="SAM no-NaN path: pixel norms shape", level='debug')
    pixel_spectra_norm = pixel_spectra / (pixel_norms + 1e-10)
    inspect(data=pixel_spectra_norm.shape, message="SAM no-NaN path: normalized pixel spectra shape", level='debug')

    # Normalize each reference signature with the same convention.
    inspect(data=usgs_df.shape, message="SAM no-NaN path: USGS dataframe shape", level='debug')
    usgs_matrix = usgs_df.T.values
    inspect(data=usgs_matrix.shape, message="SAM no-NaN path: USGS matrix shape", level='debug')
    usgs_norms = np.linalg.norm(usgs_matrix, axis=1, keepdims=True)
    inspect(data=usgs_norms.shape, message="SAM no-NaN path: USGS norms shape", level='debug')
    usgs_matrix_norm = usgs_matrix / (usgs_norms + 1e-10)
    inspect(data=usgs_matrix_norm.shape, message="SAM no-NaN path: normalized USGS matrix shape", level='debug')
    # Compute cosine similarity between each pixel and each reference spectrum.
    dot_product = np.dot(
        pixel_spectra_norm, usgs_matrix_norm.T
    )
    inspect(data=dot_product.shape, message="SAM no-NaN path: dot product shape", level='debug')
    # Convert similarities to angles for SAM-based ranking.
    angles = np.arccos(np.clip(dot_product, -1.0, 1.0))
    inspect(data=angles.shape, message="SAM no-NaN path: angle matrix shape", level='debug')
    # Lower angle means closer spectral match.
    best_match_indices = np.argmin(angles, axis=1)
    inspect(data=best_match_indices.shape, message="SAM no-NaN path: best match index vector shape", level='debug')
    # Restore the original 2D spatial layout.
    match_index_map = best_match_indices.reshape(height, width)
    inspect(data=match_index_map.shape, message="SAM no-NaN path: output map shape", level='debug')
    return match_index_map



# UDF entry point
def apply_datacube(cube: xarray.DataArray, context: dict) -> xarray.DataArray:
    """openEO UDF entry point.

    Expects an input cube with band-first layout and returns a 2D class-index map.
    """
    inspect(data=cube.dims, message="SAM UDF: input cube dimensions", level='debug')
    inspect(data=cube.shape, message="SAM UDF: input cube shape", level='debug')
    # External reference library used for spectral matching.
    csv_url = "https://artifactory.vgt.vito.be/artifactory/auxdata-public/openEO_terravision/S2_USGS_library498.csv"
    usgs_df = pd.read_csv(csv_url, sep=";")
    inspect(data=usgs_df.shape, message="SAM UDF: loaded USGS dataframe shape", level='debug')

    # Use the NaN-aware path only when needed.
    if np.isnan(cube.values).any():
        result_cube = compute_sam_w_nan(cube.values, usgs_df, 12)
    else:
        result_cube = compute_sam_wo_nan(cube.values, usgs_df)

    # Return only spatial dimensions, with class index per pixel.
    return xarray.DataArray(result_cube, dims=cube.dims[1:], coords={dim: cube.coords[dim] for dim in cube.dims[1:]})