from .data_processing_strategy import DataProcessingStrategy

class MovingAverageProcessing(DataProcessingStrategy):

    def process_data(self, data):
        data['ma_20'] = self.__sma(data,20)
        data['ma_60'] = self.__sma(data,60)
        data['ma_200'] = self.__sma(data,200)


        # 20 > 60 > 200 정배열 판단
        cond1 = data["ma_20"] > data["ma_60"]
        cond2 = data["ma_60"] > data["ma_200"]
        data["aligned_in_order"] = cond1 & cond2

        return data

    def __sma(self,data,period=20):
        return data['close'].rolling(window=period,min_periods=1).mean()