from typing import Dict, Any

from shapely.ops import transform
from shapely.geometry import box
from pyproj import Transformer

import datetime
from dateutil.relativedelta import relativedelta

import pandas as pd
import numpy as np
import seaborn as sns

import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm


# spatial
def create_spatial_extent(base_extent: Dict[str, Any], size: float = 100) -> Dict[str, Any]:
        """Create a spatial extent dictionary based on a base extent and size."""
        return {
            "west": base_extent["west"],
            "south": base_extent["south"],
            "east": base_extent["west"] + size,
            "north": base_extent["south"] + size,
            "crs": base_extent["crs"],
            "srs": base_extent["srs"]
        }

def create_bbox(extent: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a Bounding Box (BBox) compatible with openEO from the spatial extent and transform the CRS if necessary.

    Parameters:
    - extent (Dict[str, Any]): A dictionary containing the spatial extent with keys "west", "south", "east", "north", and "crs".

    Returns:
    - Dict[str, Any]: A dictionary representing the bounding box in EPSG:4326 (WGS 84).
    """
    
    # Extract coordinates from extent dictionary
    west = extent["west"]
    south = extent["south"]
    east = extent["east"]
    north = extent["north"]

    # Create a bounding box (as a shapely geometry) from the corner coordinates
    bbox_geom = box(west, south, east, north)

    # Convert to EPSG:4326 (WGS 84) if necessary
    if extent["crs"] != "EPSG:4326":
        transformer = Transformer.from_crs(extent["crs"], "EPSG:4326", always_xy=True).transform
        bbox_geom = transform(transformer, bbox_geom)

    # Extract the transformed coordinates from the bounding box geometry
    minx, miny, maxx, maxy = bbox_geom.bounds

    # Return the bounding box in the format compatible with openEO
    return {
        "west": minx,
        "south": miny,
        "east": maxx,
        "north": maxy
    }


#temporal
def create_temporal_extent(start_date_str: str, nb_months:int):
    """
    Create a temporal extent by adding months to the start date and adjusting for invalid dates.
    
    Args:
    start_date_str (str): The start date as a string in "YYYY-MM-DD" format.
    nb_months (int): The number of months to add.

    Returns:
    list: A list with the start date and end date as strings in "YYYY-MM-DD" format.
    """
    # Convert the start date string to a datetime object
    startdate = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
    
    # Add the number of months using relativedelta
    enddate = startdate + relativedelta(months=nb_months)
    
    # Convert the datetime objects back to strings
    return [startdate.strftime("%Y-%m-%d"), enddate.strftime("%Y-%m-%d")]

# df management
def prepare_jobs_df(spatial_extents, temporal_extents, start_spatial, start_temporal, repetition) -> pd.DataFrame:
    """Prepare a DataFrame containing job configurations for benchmarking."""
    jobs = []

    # Create combinations for the spatial grid
    for spatial in spatial_extents:
            for temporal in temporal_extents:
                 
                spatial_extent = create_bbox(create_spatial_extent(start_spatial, spatial))
                temporal_extent = create_temporal_extent(start_temporal, temporal)

                for ii in range(repetition):

                        jobs.append({
                            "spatial_extent": spatial_extent,
                            "square_km": (spatial / 1000)**2,
                            "temporal_extent": temporal_extent,
                            "months": temporal,
                        })

    return pd.DataFrame(jobs)


def get_job_cost_info(connection, job_id):
        try:
            job = connection.job(job_id).describe_job()
            return float(job["costs"])
        except:
            return None
    
def update_job_costs_dataframe(df, connection):
    df['job_cost'] = df.apply(lambda row: get_job_cost_info(connection, row['id']), axis=1)
    return df

#visualisation
def plot_spatio_temporal_cost_profile(df):
        df_filtered = df[df['job_cost'].notna() & (df['job_cost'] != '')]

        average_modality = df_filtered.groupby(['square_km', 'months'])['job_cost'].mean().reset_index()

        spatial_range = sorted(average_modality['square_km'].unique())[::-1]
        temporal_range = sorted(average_modality['months'].unique())

        job_cost_grid = np.full((len(spatial_range), len(temporal_range)), np.nan)

        for _, row in average_modality.iterrows():
            i = spatial_range.index(row['square_km'])
            j = temporal_range.index(row['months'])
            job_cost_grid[i, j] = int(row['job_cost'])

        # Define the colormap and normalization
        cmap = plt.get_cmap('rainbow', len(np.unique(average_modality['job_cost'])))
        norm = BoundaryNorm(boundaries=np.arange(int(average_modality['job_cost'].min()), 
                                                 int(average_modality['job_cost'].max()) + 2), 
                            ncolors=cmap.N, clip=True)

        # Plotting the heatmap using seaborn
        plt.figure(figsize=(12, 8))
        ax = sns.heatmap(job_cost_grid, cmap=cmap, norm=norm, annot=True, fmt='.1f', 
                         xticklabels=temporal_range, yticklabels=spatial_range, 
                         cbar_kws={'label': f'Average {'job_cost'}'})

        plt.xlabel('Temporal Range (square km)')
        plt.ylabel('Spatial Range (months)')
        plt.title('Credit Consumption as a function of the spatial-temporal extent')
        plt.show()


def scatter_cost_vs_input_pixel(df):
        df_filtered = df[df['job_cost'].notna() & (df['job_cost'] != '')]
        df_filtered['input_pixel'] = df['input_pixel'].str.replace(' mega-pixel', '').astype(float)

        plt.figure(figsize=(10, 6))
        sns.regplot(x='input_pixel', y='job_cost', data=df_filtered, scatter_kws={'s': 50}, line_kws={'color': 'red'})

        plt.xlabel('Input Pixel (Mega-Pixel)')
        plt.ylabel(f'{'job_cost'}')
        plt.title('Scatter Plot with Regression Line: Input Pixel vs Job Cost')

        plt.grid(True)
        plt.show()