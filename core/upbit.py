from core.main_strategy import PatternDetector

# Bitmex 클래스 (컨텍스트)
class Upbit(PatternDetector):
    #def __init__(self, data_loader: DataLoaderStrategy, processor: DataProcessingStrategy,
    #             visualizer: VisualizationStrategy, notifier: NotificationStrategy):
    #    self.data_loader = data_loader
    #    self.processor = processor
    #    self.visualizer = visualizer
    #    self.notifier = notifier
    #    self.data = None
        
    def __init__(self):
        pass
        
        
    def set_loader(self,data_loader : DataLoaderStrategy):
        self.data_loader = data_loader
    
    def load(self):
        self.data = self.data_loader.load_data()
        #self.data = self.data_loader.pre_precessing(self.data, 15, '2023-12-31 15:01:00')
        
    def set_processor(self, processor: DataProcessingStrategy):
        self.processor = processor
        
    def add_sub_indicator(self,indicator_instance_list):
        '''외부에서 주입받은 DataProcessingStrategy 중, 보조지표 추가하는 작업으로 정의된 클래스를 수행시킨다.
        보조지표의 추가이기  때문에 self.data 에 지속 쌓이는 데이터이다      
        '''
        for one_indicator in indicator_instance_list:
            #print("데이터확인")
            #print(self.data)
            self.data = one_indicator.process_data(self.data)
    
    def generate_high_low_data(self, high_point_processor, low_point_processor):
        self.high_point_df = high_point_processor.process_data(self.data)
        self.low_point_df = low_point_processor.process_data(self.data)
    
    def get_key_points(self, data):
        '''고점을 찾거나 다이버전스를 찾는등의 주요 포인트를 찾을 때 활용 다만 그 결과를 리턴받을 때만 쓴다.'''
        return self.processor.process_data(data)

    
    def execute(self):
        processed_data = self.processor.process_data(self.data)
        self.visualizer.visualize(processed_data)
        if processed_data[-1] > 3:  # 특정 패턴 감지 예시
            self.notifier.send_notification("패턴이 감지되었습니다!")