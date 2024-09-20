from pathlib import Path

import pandas as pd
import itertools
import json
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm

import seaborn as sns
import numpy as np


from datetime import datetime, timedelta
from typing import Any, Dict, List, Union


#constants
BASE_SPATIAL_START = {"west": 664000.0, "south": 5611120.0, "crs": "EPSG:32631", "srs": "EPSG:32631"}
BASE_TEMPORAL_START = '2020-01-01'

#class to prepare the dataframe and output csv for the JobManager
class JobPreparer:
    def __init__(self, process_graph_path: str):
        self.process_graph_path = process_graph_path
        self.process_graph = self.load_process_graph(process_graph_path)

    def create_spatial_extent(self, base_extent: Dict[str, Any] = BASE_SPATIAL_START, size: float = 100) -> Dict[str, Any]:
        """Create a spatial extent dictionary based on a base extent and size."""
        return {
            "west": base_extent["west"],
            "south": base_extent["south"],
            "east": base_extent["west"] + size,
            "north": base_extent["south"] + size,
            "crs": base_extent["crs"],
            "srs": base_extent["srs"]
        }

    def calculate_temporal_extent(self, start_date: str = BASE_TEMPORAL_START, months: int = 1) -> List[str]:
        """Calculate the temporal extent given a start date and number of months."""
        start_date_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_date_dt = start_date_dt + timedelta(days=30 * months)
        return [start_date_dt.strftime('%Y-%m-%d'), end_date_dt.strftime('%Y-%m-%d')]

    def prepare_jobs_df(
        self,
        temporal_range: Union[List[int], int],
        spatial_range: Union[List[float], float],
        repetition: int = 1
    ) -> pd.DataFrame:
        """Prepare a DataFrame containing job configurations for benchmarking."""
        jobs = []

        temporal_range = self.ensure_list(temporal_range)
        spatial_range = self.ensure_list(spatial_range)

        for _ in range(repetition):
            combinations = itertools.product(spatial_range, temporal_range)
            for size, months in combinations:
                jobs.append({
                    "spatial_extent": self.create_spatial_extent(size=size),
                    "temporal_extent": self.calculate_temporal_extent(months=months),
                    "process_graph_path": self.process_graph_path,
                    "process_graph_id": self.process_graph["id"],
                })

        return pd.DataFrame(jobs)

    def load_process_graph(self, path: str) -> Dict[str, Any]:
        """Load the process graph from a JSON file."""
        if(path.startswith("http")):
            from upath import UPath
            path = UPath(path)
        else:
            path = Path(path)

        with path.open() as f:
            return json.load(f)
        
    @staticmethod    
    def generate_output_filename(prefix: str, process_graph_id: str) -> str:
        """Generate a unique output file name based on the prefix and process graph ID."""
        time_stamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        return f"{prefix}_{process_graph_id}_{time_stamp}.csv"

    @staticmethod
    def ensure_list(item: Union[List[Any], Any]) -> List[Any]:
        """Ensure the item is a list."""
        if not isinstance(item, (list, tuple)):
            return [item]
        return item
    

class DataProcessor:
    @staticmethod
    def get_job_cost_info(connection, job_id):
        try:
            job = connection.job(job_id).describe_job()
            return float(job["costs"])
        except:
            return None
    
    def update_job_costs(self, df, connection):
        df['job_cost (credits)'] = df.apply(lambda row: self.get_job_cost_info(connection, row['id']), axis=1)
        return df

    def add_units_to_column_headers(self, df):
        df = df.rename(columns={
            'input_pixel': 'input_pixel (mega-pixel)',
            'cpu': 'cpu (cpu-seconds)',
            'memory': 'memory (mb-seconds)',
            'duration': 'duration (seconds)',
            'max_executor_memory': 'max_executor_memory (gb)',
            'network_received': 'network_received (b)'
        })
        return df

    @staticmethod
    def remove_unit(value, unit):
        """Remove unit from the value and convert to float."""
        if pd.isna(value):
            return None
        try:
            return float(str(value).replace(unit, '').strip())
        except ValueError:
            return None

    def clean_units(self, df):
        df['input_pixel (mega-pixel)'] = df['input_pixel (mega-pixel)'].apply(lambda x: self.remove_unit(x, ' mega-pixel'))
        df['cpu (cpu-seconds)'] = df['cpu (cpu-seconds)'].apply(lambda x: self.remove_unit(x, ' cpu-seconds'))
        df['memory (mb-seconds)'] = df['memory (mb-seconds)'].apply(lambda x: self.remove_unit(x, ' mb-seconds'))
        df['duration (seconds)'] = df['duration (seconds)'].apply(lambda x: self.remove_unit(x, ' seconds'))
        df['max_executor_memory (gb)'] = df['max_executor_memory (gb)'].apply(lambda x: self.remove_unit(x, ' gb'))
        df['network_received (b)'] = df['network_received (b)'].apply(lambda x: self.remove_unit(x, ' b'))
        return df

class Plotter:
    def plot_heatmap(self, df, output_modality):
        df_filtered = df[df[output_modality].notna() & (df[output_modality] != '')]

        average_modality = df_filtered.groupby(['spatial_range', 'temporal_range'])[output_modality].mean().reset_index()

        spatial_range = sorted(average_modality['spatial_range'].unique())[::-1]
        temporal_range = sorted(average_modality['temporal_range'].unique())

        job_cost_grid = np.full((len(spatial_range), len(temporal_range)), np.nan)

        for _, row in average_modality.iterrows():
            i = spatial_range.index(row['spatial_range'])
            j = temporal_range.index(row['temporal_range'])
            job_cost_grid[i, j] = int(row[output_modality])

        # Define the colormap and normalization
        cmap = plt.get_cmap('rainbow', len(np.unique(average_modality[output_modality])))
        norm = BoundaryNorm(boundaries=np.arange(int(average_modality[output_modality].min()), 
                                                 int(average_modality[output_modality].max()) + 2), 
                            ncolors=cmap.N, clip=True)

        # Plotting the heatmap using seaborn
        plt.figure(figsize=(12, 8))
        ax = sns.heatmap(job_cost_grid, cmap=cmap, norm=norm, annot=True, fmt='.1f', 
                         xticklabels=temporal_range, yticklabels=spatial_range, 
                         cbar_kws={'label': f'Average {output_modality}'})

        plt.xlabel('Temporal Range')
        plt.ylabel('Spatial Range')
        plt.title('Heatmap of Temporal and Spatial Range vs. Credit Consumption')
        plt.legend(loc='upper right')
        plt.show()
    
    def plot_scatter_with_fit(self, df, output_modality):
        df_filtered = df[df[output_modality].notna() & (df[output_modality] != '')]
        df_filtered['input_pixel (mega-pixel)'] = df_filtered['input_pixel (mega-pixel)'].astype(float)

        plt.figure(figsize=(10, 6))
        sns.regplot(x='input_pixel (mega-pixel)', y=output_modality, data=df_filtered, scatter_kws={'s': 50}, line_kws={'color': 'red'})

        plt.xlabel('Input Pixel (Mega-Pixel)')
        plt.ylabel(f'{output_modality}')
        plt.title('Scatter Plot with Regression Line: Input Pixel vs Job Cost')

        plt.grid(True)
        plt.show()

