# Description

Accurate delineation of agricultural field boundaries from satellite imagery is vital for land
management and crop monitoring. This service implements the **Delineate Anything** model — a
resolution-agnostic YOLOv11 instance-segmentation network trained on the large-scale FBIS-22M
dataset (672,909 satellite image patches from 0.25 m to 10 m, containing 22,926,427 instance masks).

The processing pipeline is encapsulated as an openEO User-Defined Process (UDP) with two
`apply_neighborhood` stages:

1. **BAP composite + ONNX inference** (512×512 px chunks with 128 px overlap):
   - Generates a Best-Available Pixel (BAP) RGB composite from Sentinel-2, reusing the existing
     APEx [BAP Composite](https://algorithm-catalogue.apex.esa.int/apps/bap_composite) service.
   - Scales pixel values to [0, 1] via `linear_scale_range(0, 3000, 0, 1)`.
   - Runs YOLOv11 ONNX inference producing per-pixel detection confidence and mask probability.

2. **Post-processing** (2000×2000 px chunks):
   - Thresholds mask probabilities into a binary field mask.
   - Labels connected components to produce individual field instances.
   - Filters out small fields below a configurable minimum area.

## Inputs

- `spatial_extent`: GeoJSON geometry (Polygon) defining the area of interest.
- `temporal_extent`: ISO-8601 date range `[start, end]` for BAP input scenes.
- `processing_options` (optional): dictionary with keys `confidence_threshold`, `mask_threshold`,
  `min_area_px`, `min_hole_area_px`.
- `max_cloud_cover` (optional): maximum cloud cover percentage for BAP input (default: 75).

## Outputs

A 3-band raster:

- `mask_probability` (float32) — per-pixel field boundary probability from the model.
- `binary_mask` (uint8) — thresholded binary field mask.
- `instances` (int32) — integer instance labels (0 = background, each field gets a unique ID).

# Examples

The model generalises across diverse resolutions (0.25 m–10 m) and geographic regions, including
zero-shot predictions on unseen areas with different climates, terrains, and agricultural practices.

# Known limitations

- The ONNX model is hosted on CloudFerro S3 as a `udf-dependency-archive`. 

- Post-processing uses simple connected-component labelling. Fields spanning tile boundaries may
  not be perfectly merged in all cases.
- The model is trained primarily on agricultural fields. Non-agricultural land parcels may produce
  unreliable results.
- The AGPL-3.0 licence allows research use but restricts commercial use.

# References

- Paper: [Delineate Anything: Resolution-Agnostic Field Boundary Delineation](https://arxiv.org/abs/2504.02534)
- Source repository: https://github.com/Lavreniuk/Delineate-Anything
- Project page: https://lavreniuk.github.io/Delineate-Anything/
- Dataset: https://huggingface.co/datasets/MykolaL/FBIS-22M
- UDP definition: https://raw.githubusercontent.com/Lavreniuk/Delineate-Anything/1d3241be444f46e8c9fe4e8b8de2b2366d17be3b/openeo_udp/process_graph/delineate_anything_udp.json
