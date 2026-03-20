# 알림 전략 인터페이스
class NotificationStrategy(ABC):
    @abstractmethod
    def send_notification(self, message: str):
        pass