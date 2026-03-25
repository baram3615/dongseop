from .data_processing_strategy import DataProcessingStrategy

# 고점만을 필터팅하는 처리 전략
class GetHighPoints(DataProcessingStrategy):
    def __init__(self, data, target_column, threshold_ratio):
        self.data = data
        self.target_column = target_column
        self.threshold_ratio = threshold_ratio
        
    def process_data(self, data):
        #일단 0점인건 전부 제외
        not_high_score_zero_data =data.loc[data['high_score']!=0]
        final_high_point=self.__apply_threshold_with_normalizing_for_high_value(self.data,self.target_column,self.threshold_ratio)
        
        return final_high_point
        
    #df와 타겟 컬럼명을 받아서 해당 %이상의 값만 필터링하는 함수
    def __apply_threshold_with_normalizing_for_high_value(self, target_df, target_column, threshold):
        target_df = target_df.copy()

        #min-max 정규화
        target_df['normalized_value_high'] = (target_df[target_column] - target_df[target_column].min()) / (target_df[target_column].max() - target_df[target_column].min())
        
        threshold = target_df['normalized_value_high'].quantile(threshold)
        print(f"정형화된 기준값은 : {threshold}")
        
        #상위 5%에 포함되는 애들을 별도로 선언
    
        df_calculated = target_df.loc[target_df['normalized_value_high'] >= threshold].copy()
        df_calculated.loc[df_calculated['normalized_value_high'] >= threshold, 'origin_high_score'] = df_calculated[target_column]
        #그래프를 그리기 위한 수단을 벌써 넣으면 안됨
        df_calculated.loc[df_calculated['normalized_value_high'] >= threshold, 'high_for_graph'] = df_calculated['high']
        
        import numpy as np
        df_calculated.loc[df_calculated['normalized_value_high'] < threshold, target_column] = np.nan
        
        return df_calculated
    
    def __merge_high_score_df(self, df_origin, base_score):
        df_calculated = df_origin.loc[df_origin['high_score'] > base_score].copy()
        df_calculated.loc[df_calculated['high_score'] > base_score, 'origin_score'] = df_calculated['high_score']
        df_calculated.loc[df_calculated['high_score'] > base_score, 'high_score'] = df_calculated['high']
    
        import numpy as np
        df_calculated.loc[df_calculated['high_score'] <= base_score, 'high_score'] = np.nan
        
        return df_calculated