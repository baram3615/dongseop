import pandas as pd
from .data_loader_strategy import DataLoaderStrategy

class BitmexCSVDataLoader(DataLoaderStrategy):

    def __init__(self, base_delta:int, from_date:str=None):
        self.base_delta = base_delta
        self.from_date = from_date

    def load_data(self):
        pass