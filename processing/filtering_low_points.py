from .data_processing_strategy import DataProcessingStrategy

# 저점만을 필터팅하는 처리 전략
class GetLowPoints(DataProcessingStrategy):
    def __init__(self, data, target_column, threshold_ratio):
        self.data = data
        self.target_column = target_column
        self.threshold_ratio = threshold_ratio
        
    
    def process_data(self, data):
        #일단 0점인건 전부 제외
        not_high_score_zero_data =data.loc[data['low_score']!=0]
        final_low_point=self.__apply_threshold_with_normalizing_for_low_value(self.data,self.target_column,self.threshold_ratio)
        
        return final_low_point
    
    def __apply_threshold_with_normalizing_for_low_value(self, target_df, target_column, threshold):
        target_df = target_df.copy()

        #min-max 정규화
        target_df['normalized_value_low'] = (target_df[target_column] - target_df[target_column].min()) / (target_df[target_column].max() - target_df[target_column].min())
        
        threshold = target_df['normalized_value_low'].quantile(threshold)
        print(f"정형화된 기준값은 : {threshold}")
        
        #threshold 로 적은 수 이하로 포함되는 애들을 별도로 선언
    
        df_calculated = target_df.loc[target_df['normalized_value_low'] >= threshold].copy()
        df_calculated.loc[df_calculated['normalized_value_low'] >= threshold, 'origin_low_score'] = df_calculated[target_column]
        #그래프를 그리기 위한 수단을 벌써 넣으면 안됨
        df_calculated.loc[df_calculated['normalized_value_low'] >= threshold, 'low_for_graph'] = df_calculated['low']
        
        import numpy as np
        df_calculated.loc[df_calculated['normalized_value_low'] < threshold, target_column] = np.nan
        
        return df_calculated
    
    def __merge_low_score_df(self, df_origin, base_score):
        df_calculated = df_origin.loc[df_origin['low_score'] > base_score].copy()
        df_calculated.loc[df_calculated['low_score'] > base_score, 'origin_score'] = df_calculated['low_score']
        df_calculated.loc[df_calculated['low_score'] > base_score, 'low_score'] = df_calculated['low']
    
        import numpy as np
        df_calculated.loc[df_calculated['low_score'] <= base_score, 'low_score'] = np.nan
        
        return df_calculated