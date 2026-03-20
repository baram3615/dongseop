from .data_processing_strategy import DataProcessingStrategy

# 고점/저점이 오르/내리는 구간을 구하는 처리 전략
class GetTrendSections(DataProcessingStrategy):
    
    def __init__(self, direction, target_column, minimum_interval, tolerate_interval):
        self.direction = direction
        self.target_column = target_column
        self.minimum_interval = minimum_interval
        self.tolerate_interval = tolerate_interval
        
    def process_data(self, data): 
        self.resource_df = data
        
        if(self.direction=='high'): #고점일 경우
            #이전 값보다 높거나 같으면 True찍기
            self.resource_df['increasing'] = self.resource_df['high_for_graph'] >= self.resource_df['high_for_graph'].shift()
        
            #이전 값보다 낮거나 같으면 Ture찍기
            self.resource_df['decreasing'] = self.resource_df['high_for_graph'] <= self.resource_df['high_for_graph'].shift()
            
        else:#저점일 경우
            #이전 값보다 높높거나 같으면으면 True찍기
            self.resource_df['increasing'] = self.resource_df['low_for_graph'] >= self.resource_df['low_for_graph'].shift()
            
            #이전 값보다 낮거나 같으면으면 True찍기
            self.resource_df['decreasing'] = self.resource_df['low_for_graph'] <= self.resource_df['low_for_graph'].shift()
        
        #다이버전스에서 처리하기
    
        #final_high_point['RSI_decreasing'] = final_high_point['RSI'] <= final_high_point['RSI'].shift()
        
        return self.__get_increase_sections(self.target_column, self.resource_df, self.minimum_interval,self.tolerate_interval)
        
        
    
    def __get_increase_sections(self,target_column_name, resource_df, minimum_interval, tolerate_interval):
        current_true_count = 0
        current_false_count = 0
        
        validated_index_list = [] #유효한 인덱스만 담는 리스트
        validated_group_list = [] #유효한 인덱스를 묶은 리스트
        
        start_index = 0
        end_index = 1
        
        for idx, i in enumerate(range(len(resource_df))):
            
            #첫번째는 무조건 False이므로 무시
            if (i==0):
                continue
        
            
            current_vaidate_count = 0
            current_invalidate_count = 0
            
            start_index = None
            end_index = None
            
            # 1. 일단 현재 값이 True 여야하고 
            # 2. 이미 들어 있는 validated_index_list 에 값이 tolerate_interval 보다 많으면 안된다.
            # 3. 그리고 minimun_interval 값을 무난하게 초과했는지 봐야한다.
            
            #현재 인덱스 값이 True 인지 확인
            current_status = resource_df[i:i+1][target_column_name].iloc[0]
            
            
            #현재의 인덱스 숫자 획득
            current_row_index = resource_df[i:i+1].index[0]
            current_row_timestamp = resource_df[i:i+1]['timestamp_kst'].iloc[0]
            #print(f"[{current_true_count},{current_false_count}]{current_status}, {current_row_index}, {current_row_timestamp}, {validated_index_list}")
            
            #현재 포인터리스트의 상태를 확인
            
            if(current_status==False):  
                #조건에 맞을 경우는 list에 인덱스 정보를 넣음
                if(current_false_count==tolerate_interval): #기준 숫자를 초과한 연속 하락 발생
            
                    #만약 이미 true 가 기준 갯수 이상이었다면 현재의인덱스가 마지막 인덱스다.
                    if(current_true_count>= (minimum_interval)):
                        
                        #현재 인덱스를 리스트에 넣음
                        validated_index_list.append(current_row_index)
                        
                        #마무리 하기 위해 현재의 list 를 group에 추가
                        
                        #print(f"조건에 맞는 리스트 추가 : {validated_index_list}")
                        
                        validated_group_list.append(validated_index_list)
                        
                        
                        
                                      
                        pass
                    else: #기준이 한번도 안나오고 실패 하면 아무것도 안하고 초기화
                        pass
                    
                    #초기화작업
                    validated_index_list = []
                    current_true_count = 0
                    current_false_count = 0
                    start_index = i+1 #새로운 [시작:] 을 부여
                    end_index = i+1 #새로운 [:끝] 을 부여
                else: #바로 직전보다는 하락이지만 추세는 아직 유지되고 있을 떄 ,
                    current_false_count += 1  #실패카운트를 올리고
                    #발생한 False의 인덱스를 넣고 마무리
                    validated_index_list.append(current_row_index)
                    
                    
            else: #일단 추세 유지라고 판단되는 경우
                #if(current_true_count==(minimum_interval-1)): #이번 상승으로 조건을 충족할 경우
                #    #일단 현재의 결과를 넣고
                #    validated_index_list.append(current_row_index)
                #    
                #    #그룹에 추가하고
                #    validated_group_list.append(validated_index_list)
                #    
                #    #초기화
                #    validated_index_list = []
                #    current_true_count = 0
                #    current_false_count = 0
                #else:
                #    #현재 True 긴 한데 아직 조건 충족이 안되었을 경우
                #    current_true_count += 1
                #    validated_index_list.append(current_row_index)
                
                #만약 초기화 된 이후 첫번째 validated-index_list 라면, 바로 앞의 인덱스까지 append 해주어야 한다. 
                #현재가 true 라는 것은 이전것에서부터 true 라는 뜻이기 때문이다.
                if(len(validated_index_list)==0):
                    before_row_index = resource_df[i-1:i].index[0]
                    current_true_count += 1
                    validated_index_list.append(before_row_index)
                
                
                #일단 true 인경우는 그냥 전체 구간으로 인식하게 둘 경우는 위에 주석 처리
                current_true_count += 1
                validated_index_list.append(current_row_index)
                
                #추세 유지지만 마지막까지 다다른 경우는 최종 값으로 추가해줘야 함
                if(idx == (len(resource_df) -1 )):
                    if(len(validated_index_list) >= (minimum_interval)): #현재의 조건이 맞는 경우
                        #print(f"조건에 맞는 리스트 추가 : {validated_index_list}")
                        
                        validated_group_list.append(validated_index_list)
                
                    
        return validated_group_list