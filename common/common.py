import datetime

def find_overlapping_intervals(a, b):
    result = []
    index_dict = {} #인덱스에 해당하는 high low 구간을 기록
    
    for a_start, a_end in a:
        for b_start, b_end in b:
            # 겹치는 부분 확인
            overlap_start = max(a_start, b_start)
            overlap_end = min(a_end, b_end)
            
            if overlap_start <= overlap_end:  # 유효한 겹침 구간
                result.append([overlap_start, overlap_end])
                #만약 겹침 구간이 등록되었다면 그때 인덱스에서 활용된 high / low 인덱스리스트를 기록
                index_dict[overlap_end] = {}
                index_dict[overlap_end]['high_section'] = [a_start,a_end]
                index_dict[overlap_end]['low_section'] = [b_start,b_end]
                
    if(len(result)!=0):
        return result, index_dict
    else:
        return result, index_dict
    #return result

def add_vrect_to_main_figure(main_figure, df, color, group_list):
    for one_list in group_list:
        #df순서대로 조회하면서 
        start_end_df = df.loc[[one_list[0],one_list[-1]]]
        start_date = start_end_df['timestamp_kst'].iloc[0]
        end_date = start_end_df['timestamp_kst'].iloc[-1]
        
        main_figure.add_vrect(
        x0=start_date, x1=end_date,  # 색칠할 x 구간
        fillcolor=color, opacity=0.3,  # 색상 및 투명도
        layer="below",  # 그래프 아래 배치
        line_width=0  # 테두리 제거
        )
    
    return main_figure

def generate_jpg_file_name(coin_name):
    import datetime
    post_fixt = datetime.datetime.now().strftime('%Y%m%d_%H.jpg')
    return coin_name+'_'+post_fixt
    