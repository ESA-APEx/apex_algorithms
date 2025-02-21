---
title: "Visualisation of APEx Service Records in APEx Algorithm Services Catalog"
format: html
---

Each record from the APEx catalog is visualized in the [APEx Algorithm Services Catalogue](https://algorithm-catalogue.apex.esa.int/).
This document provides an overview of how the different components of the service record are translated into catalog's graphical user interface.

## Service Catalog

![APEx Algorithm Services Catalog - Overview](images/catalog.png)

The service catalog provides an overview of all the services. The entries and all of the information are dynamically loaded based on the records inside this repository.
The following table provides an overview of how the different components are mapped to the visualization.


| Component   | Example                        | Record Property          |
|-------------|--------------------------------|--------------------------|
| Title       | Best-Available-Pixel Composite | `properties.title`       |
| Description | A compositing algorithm...     | `properties.description` |
| Tags        | composite                      | `properties.keywords`    | 

## Service Details Page



