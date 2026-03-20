from abc import ABC, abstractmethod

class DataProcessingStrategy(ABC):

    @abstractmethod
    def process_data(self, data):
        pass