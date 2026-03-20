from .data_processing_strategy import DataProcessingStrategy

class MovingAverageProcessing(DataProcessingStrategy):

    def process_data(self, data):
        data['ma_20'] = self.__sma(data,20)
        data['ma_60'] = self.__sma(data,60)
        return data

    def __sma(self,data,period=20):
        return data['close'].rolling(window=period,min_periods=1).mean()