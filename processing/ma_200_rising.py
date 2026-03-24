from .data_processing_strategy import DataProcessingStrategy


class MA200RisingProcessing(DataProcessingStrategy):
    def __init__(self, compare_period=4):
        self.compare_period = max(1, int(compare_period))

    def process_data(self, data):
        if 'ma_200' not in data.columns:
            raise KeyError("'ma_200' column is required before MA200RisingProcessing")

        previous_ma_200 = data['ma_200'].shift(self.compare_period)
        data['ma_200_rising'] = (data['ma_200'] > previous_ma_200).fillna(False)
        return data
