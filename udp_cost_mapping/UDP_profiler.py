import pandas as pd
import itertools
import json

import time
import logging

from datetime import datetime, timedelta
from typing import Any, Dict, List, Union, Optional, Callable
from pathlib import Path

from openeo import BatchJob
from openeo.rest import OpenEoApiError


_log = logging.getLogger(__name__)

#constants
BASE_SPATIAL_START = {"west": 664000.0, "south": 5611120.0, "crs": "EPSG:32631", "srs": "EPSG:32631"}
BASE_TEMPORAL_START = '2020-01-01'

#class to prepare the dataframe and output csv for the JobManager
class UDPProfilerJobPreparer:
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
                    "spatial_range": size,
                    "spatial_extent": self.create_spatial_extent(size=size),
                    "temporal_range": months,
                    "temporal_extent": self.calculate_temporal_extent(months=months),
                    "process_graph_path": self.process_graph_path,
                    "process_graph_id": self.process_graph["id"],
                })

        return pd.DataFrame(jobs)

    def load_process_graph(self, path: str) -> Dict[str, Any]:
        """Load the process graph from a JSON file."""
        with open(path) as f:
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


