from .data_processing_strategy import DataProcessingStrategy
import numpy as np
import pandas as pd

class RSIProcessing(DataProcessingStrategy):

    def process_data(self,data):
        data['RSI'] = self.__rsi(data)
        return data

    def __rsi(self, data, period=14):
    
        import numpy as np
        
        delta = data['close'].diff(1)  # 종가의 변화량 계산
        gain = np.where(delta > 0, delta, 0)  # 상승분
        loss = np.where(delta < 0, -delta, 0)  # 하락분
    
        avg_gain = pd.Series(gain).rolling(window=period, min_periods=1).mean()
        avg_loss = pd.Series(loss).rolling(window=period, min_periods=1).mean()
        
        rs = avg_gain / (avg_loss + 1e-10)  # 0으로 나누는 오류 방지
        rsi = 100 - (100 / (1 + rs))
        
        rsi.index = data.index
        
        return rsi