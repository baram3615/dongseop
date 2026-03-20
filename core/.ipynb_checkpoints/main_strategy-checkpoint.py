from abc import ABC, abstractmethod

class PatternDetector(ABC):
    
    @abstractmethod
    def load(self,base_delta, from_date):
        pass
    
    @abstractmethod
    def add_sub_indicator(self,indicator_instance_list):
        pass
    
    @abstractmethod
    def execute(self):
        pass