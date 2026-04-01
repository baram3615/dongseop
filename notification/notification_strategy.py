# 알림 전략 인터페이스
from abc import ABC, abstractmethod

class NotificationStrategy(ABC):
    @abstractmethod
    def send_notification(self, message: str):
        """기본 메시지 전송"""
        pass
    
    def send_notification_with_image(self, message: str, figure):
        """그래프 이미지와 함께 메시지 전송 (선택적)"""
        raise NotImplementedError("이 알림 방식은 이미지 전송을 지원하지 않습니다")