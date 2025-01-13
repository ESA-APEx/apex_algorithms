#######################################################################################################################
#   S1 collection implementation
#######################################################################################################################
from openeo.processes import process, if_, eq

def _load_s1_grd_bands(connection, polygon, date, bands):
    """
    Create an S1 datacube containing a selected set of bands from the SENTINEL1_GRD data collection.
    :param connection: openEO connection
    :param polygon: Area of interest
    :param date: Time of interest
    :param bands: Bands to load
    :return:
    """
    s1_grd = connection.load_collection('SENTINEL1_GRD',
                                        spatial_extent=polygon,
                                        temporal_extent=date,
                                        bands=bands)
    s1_grd = s1_grd.sar_backscatter(coefficient='sigma0-ellipsoid')
    s1_grd = s1_grd.rename_labels(dimension="bands", target=bands)
    return s1_grd


def _load_rvi(connection, polygon, date):
    """
    Create an RVI datacube based on the S1 VV and VH bands.
    :param connection: openEO connection
    :param polygon: Area of interest
    :param date: Time of interest
    :return:
    """
    base_s1 = _load_s1_grd_bands(connection, polygon, date, ['VV', 'VH'])

    VH = base_s1.band('VH')
    VV = base_s1.band('VV')
    rvi = (VH + VH) / (VV + VH)
    return rvi.add_dimension(name="bands", label="RVI", type="bands")


#######################################################################################################################
#   S2 collection implementation
#######################################################################################################################

def _load_ndvi(connection, polygon, date):
    """
    Create an NDVI datacube based on the SENTINEL2_L2A data collection.
    :param connection: openEO connection
    :param polygon: Area of interest
    :param date:
    :return:
    """
    base_s2 = connection.load_collection('SENTINEL2_L2A',
                                         spatial_extent=polygon,
                                         temporal_extent=date,
                                         bands=["B04", "B08"])
    scl = connection.load_collection('SENTINEL2_L2A',
                                        spatial_extent=polygon,
                                        temporal_extent=date,
                                        bands=["SCL"])
    mask = scl.process("mask_scl_dilation", data=scl, scl_band_name="SCL")
    masked_s2 = base_s2.mask(mask)
    ndvi = masked_s2.ndvi(red="B04", nir="B08", target_band='NDVI')
    ndvi_filtered = ndvi.filter_bands(bands=['NDVI'])
    return ndvi_filtered


def _load_biopar(polygon, date, biopar):
    """
    Create a BIOPAR datacube. This is done by using the existing BIOPAR service:
    https://portal.terrascope.be/catalogue/app-details/21

    :param polygon: Area of interest
    :param date: Time of interest
    :param biopar: BIOPAR type (see documentation of service on portal)
    :return:
    """
    base_biopar = process(
        process_id="BIOPAR",
        namespace="https://openeo.dataspace.copernicus.eu/openeo/1.1/processes/u:3e24e251-2e9a-438f-90a9-d4500e576574/BIOPAR",
        date=date,
        polygon=polygon,
        biopar_type=biopar
    )
    return base_biopar


def _load_evi(connection, polygon, date):
    """
    Create an EVI datacube. More information is available at https://en.wikipedia.org/wiki/Enhanced_vegetation_index
    :param connection: openEO connection
    :param polygon: Area of interest
    :param date: Time of interest
    :return:
    """
    base_s2 = connection.load_collection(
        collection_id='SENTINEL2_L2A',
        spatial_extent=polygon,
        temporal_extent=date,
        bands=['B02', 'B04', 'B08'],
    )
    scl = connection.load_collection('SENTINEL2_L2A',
                                        spatial_extent=polygon,
                                        temporal_extent=date,
                                        bands=["SCL"])
    mask = scl.process("mask_scl_dilation", data=scl, scl_band_name="SCL")
    masked_s2 = base_s2.mask(mask)

    B02 = masked_s2.band('B04')
    B04 = masked_s2.band('B04')
    B08 = masked_s2.band('B08')

    evi = (2.5 * (B08 - B04)) / ((B08 + 6.0 * B04 - 7.5 * B02) + 1.0)
    return evi.add_dimension(name="bands", label="EVI", type="bands")


#######################################################################################################################
# OpenEO UDP implementation
#######################################################################################################################
def _build_collection_graph(collection, label, callable, reject):
    """
    Helper function that will construct an if-else structure using the if_ openEO process. If the value of the
    collection parameter matches with the given label, the callable is executed. If not the reject function is
    executed.

    :param collection: openEO collection parameter
    :param label: String representing the text with which the collection should match
    :param callable: Function that is executed when the collection matches the label
    :param reject: Function that is executed when the collection does not match the label
    :return:
    """
    return if_(eq(collection, label, case_sensitive=False), callable, reject)


def load_s1_collection(connection, collection, polygon, date):
    """
    Create a S1 input data cube based on the collection selected by the user. This achieved by building an
    if-else structure through the different openEO processes, making sure that the correct datacube is selected
    when executing the UDP.

    :param connection: openEO connection
    :param collection: One of the supported collection (S1_COLLECTIONS)
    :param polygon: Area of interest
    :param date:  Time of interest
    :return:
    """
    collections = None
    for option in [
        {
            'label': 'grd',
            'function': _load_s1_grd_bands(connection=connection, polygon=polygon, date=date, bands=['VV', 'VH'])
        },
        {
            'label': 'rvi',
            'function': _load_rvi(connection=connection, polygon=polygon, date=date)
        }
    ]:
        collections = _build_collection_graph(collection=collection,
                                              label=option['label'],
                                              callable=option['function'],
                                              reject=collections)
    return collections


def load_s2_collection(connection, collection, polygon, date):
    """
    Create a S2 input data cube based on the collection selected by the user. This achieved by building an
    if-else structure through the different openEO processes, making sure that the correct datacube is selected
    when executing the UDP.

    :param connection: openEO connection
    :param collection: One of the supported collection (S2_COLLECTIONS)
    :param polygon: Area of interest
    :param date:  Time of interest
    :return:
    """
    collections = None
    for option in [
        {
            'label': 'ndvi',
            'function': _load_ndvi(connection=connection, polygon=polygon, date=date)

        },
        {
            'label': 'fapar',
            'function': _load_biopar(polygon=polygon, date=date, biopar='FAPAR')
        },
        {
            'label': 'lai',
            'function': _load_biopar(polygon=polygon, date=date, biopar='LAI')
        },
        {
            'label': 'fcover',
            'function': _load_biopar(polygon=polygon, date=date, biopar='FCOVER')
        },
        {
            'label': 'evi',
            'function': _load_evi(connection=connection, polygon=polygon, date=date)
        },
        {
            'label': 'ccc',
            'function': _load_biopar(polygon=polygon, date=date, biopar='CCC')
        },
        {
            'label': 'cwc',
            'function': _load_biopar(polygon=polygon, date=date, biopar='CWC')
        }
    ]:
        collections = _build_collection_graph(collection=collection,
                                              label=option['label'],
                                              callable=option['function'],
                                              reject=collections)
    return collections