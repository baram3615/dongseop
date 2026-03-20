# 구체적인 알림 전략: 문자 메시지 전송
class SMSNotification(NotificationStrategy):
    def send_notification(self, message: str):
        print(f"문자 메시지 전송: {message}")