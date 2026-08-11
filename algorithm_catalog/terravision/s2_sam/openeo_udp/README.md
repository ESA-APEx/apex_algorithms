# Sentinel-2 based Spectral Angle Mapping (S2-SAM)

This service applies Spectral Angle Mapping (SAM) to Sentinel-2 Level-2A reflectance data.
For each pixel, the algorithm compares the pixel spectrum to a spectral reference library and selects the closest match based on the smallest spectral angle.

## What this service does

SAM measures similarity in spectral *shape* (not absolute brightness):

$$
θ = \cos^{-1}\left(\frac{x \cdot y}{\|x\|\|y\|}\right)
$$

where:
- $x$ is the pixel spectrum.
- $y$ is a reference spectrum from the library.
- smaller $\theta$ means a better match.

The output is a raster of class indices, where each pixel value is the index of the best-matching reference signature.

## Sentinel-2 bands used

The service uses only the Sentinel-2 L2A bands provided by the BAP composite input, not all L2A layers.
The band subset is (B01, B02, B03, B04, B05, B06, B07, B08, B8A, B09, B11, B12).

Input compositing is based on the BAP process:
[https://algorithm-catalogue.apex.esa.int/apps/bap_composite](https://algorithm-catalogue.apex.esa.int/apps/bap_composite)

## Reference spectral library

The reference library is based on a Sentinel-2-resampled USGS mineral/material collection.
It includes a broad set of geology and mining-related targets (e.g. iron oxides, clays, sulfates, silicates, carbonates, and related materials).

The CSV used by the service contains:
- 498 named reference signatures (material columns).
- 1 `cwvl` column with central wavelength values.

Examples of included targets are minerals such as Acmite, Actinolite, Alunite, Jarosite, Kaolinite, Hematite, Goethite, Pyrite, Chalcopyrite, and many more variants.

## Notes on interpretation

- The product reports the **closest spectral match** in the selected library, not a definitive mineral identification.
- Similar materials can produce similar spectra at Sentinel-2 spectral resolution.
- Results are most useful when combined with geological context, ancillary data, and expert validation.

## Missing data handling

If some bands are missing (`NaN`) at a pixel, the implementation computes SAM using only the available bands, with a minimum valid-band threshold.
Pixels without enough valid information are marked as no match.

