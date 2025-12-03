# RAMONA - Herbaceous Rangeland Biomass (HRB) - Country Level Mosaick

For a selected African country, year and month, the process returns a mosaic of the monthly HRB products as a single GeoTIFF.

This is an example output for Benin:

![Benin](https://github.com/ESA-APEx/apex_algorithms/blob/503edd5ef736b740bccb52f946530b33b85f9ee9/algorithm_catalog/dhi/ramona_biomass_extract/openeo_udp/benin_extract.png)

## Methodology

Monthly HRB input files are mosaicked and exported as a GeoTIFF. The RAMONA HRB products have been precomputed. The products were generated for the target year 2022 and specifically from Aug-2021 to January-2023. 

More information can be found at [https://www.ramona.earth/](https://www.ramona.earth/)

## Performance

The table below lists cost and timings of test runs. You may see (small) deviations from this
in your own runs.

| Country  | Wall time   | Credit cost |
|----------|-------------|-------------|
| Benin    | 3.5 minutes | 6           |
| Cameroon | 9 minutes   | 26          |
| Ethiopia | 20 minutes  | 64          |
