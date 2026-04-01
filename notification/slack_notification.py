# Slack 알림 전략 구현
from .notification_strategy import NotificationStrategy
import requests
import os
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class SlackNotification(NotificationStrategy):
    """Slack으로 메시지 및 이미지를 전송하는 알림 전략"""
    
    def __init__(self, webhook_url: str = None, bot_token: str = None, channel_id: str = None):
        """
        Args:
            webhook_url: Slack Incoming Webhook URL (간단한 방식)
            bot_token: Slack Bot Token (고급 방식)
            channel_id: Slack Channel ID (bot_token 사용 시)
        """
        self.webhook_url = webhook_url or os.getenv('SLACK_WEBHOOK_URL')
        self.bot_token = bot_token or os.getenv('SLACK_BOT_TOKEN')
        self.channel_id = channel_id or os.getenv('SLACK_CHANNEL_ID')
        self._web_client = WebClient(token=self.bot_token) if self.bot_token else None
        
        if not self.webhook_url and not self.bot_token:
            raise ValueError("webhook_url 또는 bot_token이 필요합니다.")
    
    def send_notification(self, message: str):
        """인터페이스 구현: 텍스트 메시지 전송"""
        self._send_message_via_webhook(message) if self.webhook_url else self._send_message_via_bot(message)
    
    def send_notification_with_image(self, message: str, figure):
        """그래프 이미지와 함께 메시지 전송
        
        Args:
            message: 전송할 메시지
            figure: Plotly figure 객체
        """
        try:
            # 임시 이미지 파일로 저장
            image_path = self._save_figure_as_image(figure)
            
            if self.bot_token and self.channel_id:
                self._send_message_and_image_via_bot(message, image_path)
            else:
                # Webhook은 파일 업로드 미지원, 메시지만 전송
                self._send_message_via_webhook(message)
                print("⚠️  Webhook 방식은 이미지 업로드 미지원. Bot Token 사용을 권장합니다.")
            
            # 임시 파일 삭제
            if os.path.exists(image_path):
                os.remove(image_path)
                
        except Exception as e:
            print(f"❌ Slack 이미지 전송 실패: {str(e)}")
            raise
    
    def send_notification_with_multiple_images(self, message: str, figures_dict: dict):
        """여러 그래프를 한번에 전송
        
        Args:
            message: 전송할 메시지
            figures_dict: {'그래프명': figure_object} 형태의 딕셔너리
        """
        if not self.bot_token or not self.channel_id:
            raise ValueError("Bot Token과 Channel ID가 필요합니다.")
        
        try:
            # 먼저 메시지 전송
            self._send_message_via_bot(message)
            
            # 각 그래프를 이미지로 저장 후 전송
            for graph_name, figure in figures_dict.items():
                image_path = self._save_figure_as_image(figure, filename_prefix=graph_name)
                self._upload_file_to_slack(image_path)
                
                if os.path.exists(image_path):
                    os.remove(image_path)
                    
        except Exception as e:
            print(f"❌ 복수 이미지 전송 실패: {str(e)}")
            raise
    
    def _save_figure_as_image(self, figure, filename_prefix: str = "chart") -> str:
        """Plotly figure를 PNG 이미지로 저장
        
        Args:
            figure: Plotly figure 객체
            filename_prefix: 파일명 접두사
            
        Returns:
            저장된 이미지 파일 경로
        """
        import plotly.io as pio
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = f"/tmp/{filename_prefix}_{timestamp}.png"
        
        # Windows 환경 대응
        if os.name == 'nt':
            import tempfile
            temp_dir = tempfile.gettempdir()
            image_path = os.path.join(temp_dir, f"{filename_prefix}_{timestamp}.png")
        
        try:
            pio.write_image(figure, image_path, width=1400, height=900)
            print(f"📊 이미지 저장: {image_path}")
            return image_path
        except Exception as e:
            print(f"❌ 이미지 저장 실패: {str(e)}")
            # kaleido 설치 확인
            print("💡 필요 패키지: pip install kaleido")
            raise
    
    def _send_message_via_webhook(self, message: str):
        """Webhook을 통해 텍스트 메시지 전송"""
        payload = {"text": message}
        
        try:
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()
            print(f"✅ Slack 메시지 전송 성공")
        except Exception as e:
            print(f"❌ Slack 메시지 전송 실패: {str(e)}")
            raise
    
    def _send_message_via_bot(self, message: str):
        """Bot Token을 통해 텍스트 메시지 전송"""
        url = "https://slack.com/api/chat.postMessage"
        headers = {"Authorization": f"Bearer {self.bot_token}"}
        payload = {
            "channel": self.channel_id,
            "text": message
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if not data.get('ok'):
                raise Exception(f"Slack API 에러: {data.get('error')}")
            
            print(f"✅ Slack 메시지 전송 성공")
        except Exception as e:
            print(f"❌ Slack 메시지 전송 실패: {str(e)}")
            raise
    
    def _send_message_and_image_via_bot(self, message: str, image_path: str):
        """Bot Token을 통해 메시지와 이미지 함께 전송"""
        # 먼저 메시지 전송
        self._send_message_via_bot(message)
        
        # 이미지 업로드
        self._upload_file_to_slack(image_path)
    
    def _upload_file_to_slack(self, image_path: str):
        """Slack에 파일 업로드 (files_upload_v2 사용)"""
        if not self._web_client:
            raise ValueError("Bot Token이 필요합니다.")

        try:
            filename = os.path.basename(image_path)
            with open(image_path, 'rb') as file_obj:
                response = self._web_client.files_upload_v2(
                    channel=self.channel_id,
                    file=file_obj,
                    filename=filename,
                    title=filename,
                )

            if not response.get("ok", False):
                raise Exception(f"Slack API 에러: {response.get('error', 'unknown_error')}")

            print(f"✅ 이미지 업로드 성공: {filename}")

        except SlackApiError as e:
            error = e.response.get("error", str(e)) if e.response else str(e)
            print(f"❌ 이미지 업로드 실패: Slack API 에러: {error}")
            raise Exception(f"Slack API 에러: {error}") from e
        except Exception as e:
            print(f"❌ 이미지 업로드 실패: {str(e)}")
            raise
