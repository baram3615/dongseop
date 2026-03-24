import pyupbit
from core.upbit import Upbit
from loader.upbit_realtimedata_loader import UpbitRealtimeDataLoader
from processing.moving_average import MovingAverageProcessing
from processing.rsi import RSIProcessing
from processing.high_point_scoring import HighPointScoringProcessing
from processing.low_point_scoring import LowPointScoringProcessing
from processing.filtering_high_points import GetHighPoints
from processing.filtering_low_points import GetLowPoints
from processing.get_trend_section import  GetTrendSections

from visualization.basic_price_rsi_visualization import BasicPriceWithRsiVisualization

from common.common import *

#여기가 최종 완성 구간이네

#60분일 때 
#interval_base = "minute60"
#load_count = 240
#score_band_list = [12] #12시간에 한번씩 채점
#threshold = 0.90
#indecreasing_count_set=[3,0] #3번 계속 상승구간만 체크하고 허용을 0번함

figure_to_jpg_dict = {} #저장한 이미지와 그 경로를 가진 dict 를 생성하고 아래카카오에서 이 정보를 기반으로 메시지를 전송함

#240분일 떄
interval_base = "minute240"
#interval_base = "day1"
load_count = 400
score_band_list = [30] #5일중 제일 높은 구간 채점
threshold = 0.85
indecreasing_count_set=[3,1]

target_coin_name_list = []

## 업비트 전체 뒤져보기
tickers = pyupbit.get_tickers('KRW')

#코인별 확인
for idx, one_coin in enumerate(tickers):
    
    #if one_coin not in base_date_dict.keys(): #최근 변곡점이 아닌 애들이라면 아예 하지 않음
    #    continue
    
    #if(one_coin not in ['KRW-NEAR']):
    #    continue
    
    print(f"{one_coin} 시작")
    
    #RAW 데이터 로드
    upbit = Upbit()
    upbit.set_loader(UpbitRealtimeDataLoader(one_coin,interval_base,load_count))
    upbit.load()
    #upbit.data = upbit.data.loc[upbit.data['timestamp_kst'] <= '2025-03-27 00:00:00']
    #upbit.data = upbit.data.loc[upbit.data['timestamp_kst'] <= '2025-03-26 23:00:00']
    
    #지표 추가
    indicator_list = [MovingAverageProcessing(), RSIProcessing(),HighPointScoringProcessing(score_band_list),LowPointScoringProcessing(score_band_list)]
    upbit.add_sub_indicator(indicator_list)
    
    #고점, 저점 찾기
    upbit.generate_high_low_data(GetHighPoints(upbit.data.loc[upbit.data['high_score']!=0], 'high_score', threshold), 
                                GetLowPoints(upbit.data.loc[upbit.data['low_score']!=0], 'low_score', threshold)
                                )
    
    #고.저점 상승 추세구간 획득
    upbit.set_processor(GetTrendSections('high','increasing',indecreasing_count_set[0],indecreasing_count_set[1]))
    high_point_increasing_trend_section_upbit = upbit.get_key_points(upbit.high_point_df)
    upbit.set_processor(GetTrendSections('high','decreasing',indecreasing_count_set[0],indecreasing_count_set[1]))
    high_point_decreasing_trend_section_upbit = upbit.get_key_points(upbit.high_point_df)
    
    upbit.set_processor(GetTrendSections('low','increasing',indecreasing_count_set[0],indecreasing_count_set[1]))
    low_point_increasing_trend_section_upbit = upbit.get_key_points(upbit.low_point_df)
    upbit.set_processor(GetTrendSections('low','decreasing',indecreasing_count_set[0],indecreasing_count_set[1]))
    low_point_decreasing_trend_section_upbit = upbit.get_key_points(upbit.low_point_df)
    
    #저점고점 함께 상승하는 구간 찾기
    high_point_group_start_end_upbit = []
    for i in high_point_increasing_trend_section_upbit:
        high_point_group_start_end_upbit.append([i[0],i[-1]])
    
    
    low_point_group_start_end_upbit = []
    for i in low_point_increasing_trend_section_upbit:
        low_point_group_start_end_upbit.append([i[0],i[-1]])

    
    #고점은 낮아지는 구간 찾기
    #high_point_group_start_end_upbit = []
    #for i in high_point_decreasing_trend_section_upbit:
    #    high_point_group_start_end_upbit.append([i[0],i[-1]])
    
    
    
    high_low_increasing_trend_section_upbit, high_low_list_dict = find_overlapping_intervals(high_point_group_start_end_upbit, low_point_group_start_end_upbit)
    
    #중첩되었을 떄의 고점 리스트는
    
    #중첩 구간이 가장 최근인지 확인
    if(len(high_low_increasing_trend_section_upbit) != 0 ):
        #중첩된 구간의 마지막 인덱스를 찾고
        latest_overlap_index = high_low_increasing_trend_section_upbit[-1][-1] #가장 가까운 구간의 인덱스 값을 찾고
        #중첩이 되었을 떄 활용되었던 고점의 마지막 인덱스를 획득하고
        latest_high_index = high_low_list_dict[latest_overlap_index]['high_section'][-1]
        
        #중첩이 되었을 때 활용되었던 저점의 마지막 인덱스를 획득
        latest_low_index = high_low_list_dict[latest_overlap_index]['low_section'][-1]
        
        print(f"기준이 되는 고점 날짜 ; {upbit.data.iloc[[latest_high_index]]['timestamp_kst'].iloc[0]}")
        print(f"기준이 되는 저점 날짜 ; {upbit.data.iloc[[latest_low_index]]['timestamp_kst'].iloc[0]}")
        
        latest_timestamp_high = upbit.data.iloc[[latest_high_index]]['timestamp_kst'].iloc[0] #마지막 고점구간의 끝 날짜 확인
        latest_timestamp_low = upbit.data.iloc[[latest_low_index]]['timestamp_kst'].iloc[0] #마지막 저점구간의 끝 날짜 확인
        check_df_high = upbit.data.loc[upbit.data['timestamp_kst'] >= latest_timestamp_high] #그 날짜보다 높은 값이 있는지 확인
        check_df_low = upbit.data.loc[upbit.data['timestamp_kst'] >= latest_timestamp_low] #그 날짜보다 높은 값이 있는지 확인
        
        print(f"기준 고점 이후 몇시간 지났나 : {len(check_df_high)}")
        print(f"기준 저점 이후 몇시간 지났나 : {len(check_df_low)}")
        
        #print(check_df)
        #print(len(check_df))
        if(len(check_df_high)<11 or len(check_df_low)<11): #1개만 발견됐다면 이건 바로 지금 유의미한 자리인 것
            pass
        else:
            continue
    else: #중첩 구간이 없는건 일단 무시
        continue
        
    #일단 주목해야할 코인들의 리스트를 받은
    target_coin_name_list.append(one_coin)
    
    
    #출력
    draw_instance = BasicPriceWithRsiVisualization()
    draw_instance.set_data(upbit.data, upbit.high_point_df, upbit.low_point_df)
    draw_instance.make_figure()
    
    figure = draw_instance.get_figure()
    
    #add_vrect_to_main_figure(figure, upbit.data, 'red', high_low_increasing_trend_section_upbit) #중첩된 구간만 그리기
    add_vrect_to_main_figure(figure, upbit.data, 'red', high_point_group_start_end_upbit) #고점 그래프는 빨간색
    add_vrect_to_main_figure(figure, upbit.data, 'blue', low_point_group_start_end_upbit) #고점 그래프는 파란색
    draw_instance.visualize()
    
    #파일이름으로 저장함
    
    #jpg_file_name = JPG_DIRECTORY+'/'+generate_jpg_file_name(one_coin)
    #print(f"파일 저장 :{jpg_file_name}")
    #figure.write_image(jpg_file_name, format="jpg")
    #print("완료")
    
    
    #break
    
    if(idx==2):
        break
    
    
    
