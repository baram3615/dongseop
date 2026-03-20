from .data_processing_strategy import DataProcessingStrategy

#고점을 찾는 처리 전략
class HighPointScoringProcessing(DataProcessingStrategy):
    '''
    메인 df에 'high_score' 라는 컬럼을 추가하고, 외부 변수의 리스트로 들어온 
    밴드 값을 shift 하면서 그중에 가장 큰 가격에 +1 스코어를 한다.
    '''
    
    
    def __init__(self, bandwidth_list):
        self.bandwith_list = bandwidth_list
    
    def process_data(self, data):
        data = self.__get_high_score_by_list(data,self.bandwith_list)
        return data
    
    def __get_high_score_by_list(self, origin_df,lst):
        if(len(lst)==0):
            print("대상이 없습니다.")
            
        else:
            return_df = None
            for idx, i in enumerate(lst):
                if(idx==0):
                    return_df = self.__get_high_score_with_bandwidth(origin_df, 'high', i)
                else:
                    return_df = self.__get_high_score_with_bandwidth(return_df, 'high', i, reset=False)
    
        return return_df
    
    
        
    def __get_high_score_with_bandwidth(self, target_df, column_name, bandwidth, reset=True):
        '''
        df를 제공하면서 밴드 값을 같이 제공하면 이를 반복문으로 돌아가면서 score 를 쌓는 함수
        '''
        #일단 들어온 df 에 high_score 라는 컬럼 값 기본 강제 삽입
        if(reset==True):
            target_df['high_score']=0
        #end_index = len(target_df) - bandwidth
        #for idx,i in enumerate(range(end_index+1)): #이렇게 하니까 맨 뒷쪽 점수가 부여될 수가 없더라
        for idx,i in enumerate(range(len(target_df))):
            
            max_index = target_df.iloc[i:i+bandwidth][column_name].idxmax()
            
            #print(f"진입한 시작 값 : {i}~{i+bandwidth}")
            #print(f"가장 큰 인덱스 : {max_index}")
            #print(f"이때의 이미 기록된 값:{target_df.loc[max_index, 'high_score']} ")
            #print(f"이때의 이미 기록될 값:{target_df.loc[max_index]['high_score']+1} ")
            #print(max_index)
        #
            #print(f"세팅전 값 : {target_df.loc[max_index]['high_score']}")
        #
            #print(f"체크값 :{target_df.loc[max_index]['high_score']+1}")
            #
            target_df.loc[max_index,'high_score'] = target_df.loc[max_index]['high_score']+1
            #print(f"세팅후 값 : {target_df.loc[max_index]['high_score']}")
        
        print(f"가장 높은 점수:{target_df.loc[target_df['high_score'].idxmax()]['high_score']}")
        
        return target_df