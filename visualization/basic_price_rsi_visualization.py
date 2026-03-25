from .visualization_strategy import Visualization

# 구체적인 시각화 전략: 라인 그래프
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
pio.renderers.default = "notebook" 

class BasicPriceWithRsiVisualization(Visualization):
    
    def __init__(self):
        self.price_trace_list = []
        self.rsi_trace_lsit = []
        self.figure_title = 'Candlestick Chart'
        
    def set_data(self, df, high_points_df, low_points_df):
        self.__df = df
        self.__high_points_df = high_points_df
        self.__low_points_df = low_points_df
    
    def make_figure(self, title=None):
        if title:
            self.figure_title = title
        self.__get_base_figure()
    
    def visualize(self):
        self.__main_figure.show()
        
    def add_trace(self, trace):
        
        #가격 트레이스 추가
        self.price_trace_list.append(trace)
        
        #메인 피겨 갱신
        self.__main_figure = self.__draw_subplots(self.price_trace_list, self.rsi_trace_lsit)
        
    def get_figure(self):
        return self.__main_figure
        
        
    def __get_base_figure(self):
        main_trace = go.Candlestick(
            x=list(self.__df['timestamp_kst']),
            open=list(self.__df['open']),
            high=list(self.__df['high']),
            low=list(self.__df['low']),
            close=list(self.__df['close']),
        )
        
        #두번째 고가 점 트레이스 만들기
        high_point_trace = go.Scatter(y=list(self.__high_points_df['high_for_graph']), x=list(self.__high_points_df['timestamp_kst']), 
        marker=dict(
        color='rgba(255, 0, 255, 1)',  # 점의 색상 설정 (RGBa 형식)
        size=5,  # 점의 크기 설정
        ),
        mode='markers', name='고점 그래프')
        
        #세번째 저가 점 트레이스 만들기
        low_point_trace = go.Scatter(y=list(self.__low_points_df['low_for_graph']), x=list(self.__low_points_df['timestamp_kst']), 
        marker=dict(
        color='rgba(0, 0, 0, 1)',  # 점의 색상 설정 (RGBa 형식)
        size=5,  # 점의 크기 설정
        ),
        mode='markers', name='저점 그래프')
        
        ma_20_trace = go.Scatter(x=self.__df['timestamp_kst'], y=self.__df['ma_20'], mode='lines', name='MA_20', line=dict(color='blue'))

        ma_60_trace = go.Scatter(x=self.__df['timestamp_kst'], y=self.__df['ma_60'], mode='lines', name='MA_60', line=dict(color='black'))
        
        ma_200_trace = go.Scatter(x=self.__df['timestamp_kst'], y=self.__df['ma_200'], mode='lines', name='MA_200', line=dict(color='gray'))

        
        rsi_trace = go.Scatter(x=self.__df['timestamp_kst'], y=self.__df['RSI'], mode='lines', name='RSI', line=dict(color='blue'))
        self.rsi_trace_lsit = [rsi_trace]
        
        self.price_trace_list.append(main_trace)
        self.price_trace_list.append(high_point_trace)
        self.price_trace_list.append(low_point_trace)
        self.price_trace_list.append(ma_20_trace)
        self.price_trace_list.append(ma_60_trace)
        self.price_trace_list.append(ma_200_trace)
        
        main_figure = self.__draw_subplots(self.price_trace_list, self.rsi_trace_lsit)
        
        self.__main_figure = main_figure
   
    
    def __draw_subplots(self, price_trace_list, rsi_trace_list):
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                        row_heights=[0.7, 0.3],  # 위쪽(가격) 70%, 아래쪽(RSI) 30%
                        subplot_titles=("가격 차트", "RSI (14)"))
        
        fig.update_layout(
        title=self.figure_title,
        xaxis_title='Date',
        yaxis_title='Price',
        xaxis_rangeslider_visible=False,
        width=1000,  # 그래프 너비 설정
        height=800   # 그래프 높이 설정
        )
        
        #trace_list1를 전부 담음
        for i in price_trace_list:
            fig.add_trace(i, row=1, col=1)
        
        for i in rsi_trace_list:
            fig.add_trace(i, row=2, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Overbought (70)", row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Oversold (30)", row=2, col=1)

        self.__highlight_aligned_in_order_sections(fig)
            
            
        return fig

    def __highlight_aligned_in_order_sections(self, fig):
        if 'aligned_in_order' not in self.__df.columns:
            return

        timestamps = list(self.__df['timestamp_kst'])
        raw_aligned_values = self.__df['aligned_in_order'].fillna(False).tolist()

        aligned_values = []
        true_string_values = {"true", "1", "t", "y", "yes"}
        for value in raw_aligned_values:
            if isinstance(value, bool):
                aligned_values.append(value)
            elif isinstance(value, (int, float)):
                aligned_values.append(value == 1)
            elif isinstance(value, str):
                aligned_values.append(value.strip().lower() in true_string_values)
            else:
                aligned_values.append(False)

        start_idx = None
        for idx, is_aligned in enumerate(aligned_values):
            if is_aligned and start_idx is None:
                start_idx = idx
            elif not is_aligned and start_idx is not None:
                fig.add_vrect(
                    x0=timestamps[start_idx],
                    x1=timestamps[idx - 1],
                    fillcolor="rgba(255, 165, 0, 0.20)",
                    line_width=0,
                    row=1,
                    col=1,
                )
                start_idx = None

        if start_idx is not None and len(timestamps) > 0:
            fig.add_vrect(
                x0=timestamps[start_idx],
                x1=timestamps[-1],
                fillcolor="rgba(255, 165, 0, 0.20)",
                line_width=0,
                row=1,
                col=1,
            )

