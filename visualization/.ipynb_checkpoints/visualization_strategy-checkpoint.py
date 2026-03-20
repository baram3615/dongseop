from abc import ABC, abstractmethod

# 데이터 시각화 인터페이스
class Visualization(ABC):
    
    @abstractmethod
    def make_figure(self):
        pass
    
    @abstractmethod
    def visualize(self):
        pass
    
    
    @abstractmethod
    def add_trace(self, trace):
        pass
    #self.price_trace_list.append(trace)