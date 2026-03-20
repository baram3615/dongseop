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
        
    def set_data(self, df, high_points_df, low_points_df):
        self.__df = df
        self.__high_points_df = high_points_df
        self.__low_points_df = low_points_df
    
    def make_figure(self):
        self.__get_base_figure()
    
    def visualize(self):
        self.__main_figure.show()
        
    def add_trace(self, trace):
        
        #가격 트레이스 추가
        self.price_trace_list.append(trace)
        
        #메인 피겨 갱신
        self.__main_figure = self.__draw_subplots(self.price_trace_list,[rsi_trace])
        
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
        
        rsi_trace = go.Scatter(x=self.__df['timestamp_kst'], y=self.__df['RSI'], mode='lines', name='RSI', line=dict(color='blue'))
        
        self.price_trace_list.append(main_trace)
        self.price_trace_list.append(high_point_trace)
        self.price_trace_list.append(low_point_trace)
        self.price_trace_list.append(ma_20_trace)
        self.price_trace_list.append(ma_60_trace)
        
        main_figure = self.__draw_subplots(self.price_trace_list,[rsi_trace])
        
        self.__main_figure = main_figure
   
    
    def __draw_subplots(self, price_trace_list, rsi_trace_list):
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                        row_heights=[0.7, 0.3],  # 위쪽(가격) 70%, 아래쪽(RSI) 30%
                        subplot_titles=("가격 차트", "RSI (14)"))
        
        fig.update_layout(
        title='Candlestick Chart',
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
            
            
        return fig