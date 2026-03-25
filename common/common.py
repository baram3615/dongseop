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

def add_vrect_to_main_figure(
    main_figure,
    df,
    color,
    group_list,
    show_interval_label=False,
    label_prefix='번구간',
    start_label_index=1,
    show_interval_length=False,
    interval_length_separator=' : ',
):
    y_max = None
    if show_interval_label and 'high' in df.columns and len(df) > 0:
        y_max = float(df['high'].max())

    for offset, one_list in enumerate(group_list):
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

        if show_interval_label:
            label_index = start_label_index + offset
            label_text = f"{label_index}{label_prefix}"

            if show_interval_length and 'timestamp_kst' in df.columns:
                interval_df = df.loc[
                    (df['timestamp_kst'] >= start_date) &
                    (df['timestamp_kst'] <= end_date)
                ]
                interval_length = len(interval_df)
                label_text = f"{label_text}{interval_length_separator}{interval_length}"

            try:
                x_mid = start_date + (end_date - start_date) / 2
            except Exception:
                x_mid = start_date

            annotation_kwargs = {
                'x': x_mid,
                'xref': 'x',
                'text': label_text,
                'showarrow': False,
                'font': {'size': 12, 'color': '#3a2f00'},
                'bgcolor': 'rgba(255, 255, 255, 0.65)',
                'bordercolor': '#b8860b',
                'borderwidth': 1,
            }

            if y_max is not None:
                annotation_kwargs['y'] = y_max
                annotation_kwargs['yref'] = 'y'
            else:
                annotation_kwargs['y'] = 1.0
                annotation_kwargs['yref'] = 'paper'

            main_figure.add_annotation(**annotation_kwargs)
    
    return main_figure

def generate_jpg_file_name(coin_name):
    import datetime
    post_fixt = datetime.datetime.now().strftime('%Y%m%d_%H.jpg')
    return coin_name+'_'+post_fixt

def add_vline_to_main_figure(
    main_figure,
    df,
    color,
    point_list,
    label_text='라벨',
):
    """
    세로 라인을 그래프에 추가하는 함수
    point_list: df 인덱스의 리스트 (예: [idx1, idx2, ...])
    """
    for point_idx in point_list:
        point_df = df.loc[[point_idx]]
        point_timestamp = point_df['timestamp_kst'].iloc[0]
    
        # 세로 라인 추가
        main_figure.add_vline(
            x=point_timestamp,
            line_dash="solid",
            line_color=color,
            line_width=2
        )
    
        # 라벨 추가
        main_figure.add_annotation(
            x=point_timestamp,
            y=1.0,
            yref="paper",
            text=label_text,
            showarrow=False,
            font=dict(size=12, color=color),
            bgcolor="rgba(255, 255, 255, 0.7)",
            bordercolor=color,
            borderwidth=1
        )

    return main_figure
    