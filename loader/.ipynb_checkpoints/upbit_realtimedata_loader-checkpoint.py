from loader.data_loader_strategy import DataLoaderStrategy

# 구체적인 데이터 로드 전략: CSV 로드
class UpbitRealtimeDataLoader(DataLoaderStrategy):
    
    def __init__(self, coin_id, base_delta, count:int = 1000):
        self.coin_id = coin_id
        self.base_delta = base_delta
        self.count = count
        
        
    
    def load_data(self):
        print(f"업비트에서 {self.coin_id} 가격을 최신부터{self.base_delta} 간격으로 {self.count}개 로드 합니다.")
        import pyupbit
        df = pyupbit.get_ohlcv(self.coin_id, interval=self.base_delta, count=self.count)
        
        #인덱스를 컬럼으로 가져오기
        df = df.reset_index()
        df = df.rename(columns={'index': 'timestamp_kst'})
        
        df = df[['timestamp_kst','open','low','high','close']]
        
        return df