from abc import ABC, abstractmethod

class DataLoaderStrategy(ABC):

    @abstractmethod
    def load_data(self):
        pass