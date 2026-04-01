"""
Slack 그래프 전송 헬퍼 함수
new_main_merge.ipynb에서 쉽게 사용할 수 있는 유틸리티 함수들
"""

import os
import pandas as pd
from notification.slack_notification import SlackNotification


class SlackChartNotifier:
    """Slack 그래프 전송을 쉽게 관리하는 클래스"""
    
    def __init__(self):
        """슬랙 노티파이어 초기화"""
        try:
            self.slack = SlackNotification(
                bot_token=os.getenv('SLACK_BOT_TOKEN'),
                channel_id=os.getenv('SLACK_CHANNEL_ID')
            )
            self.is_enabled = True
            print("✅ Slack 연결 성공")
        except Exception as e:
            self.is_enabled = False
            print(f"⚠️  Slack 연결 실패: {str(e)}")
    
    def send_filtered_signal(self, coin_name, figure_daily, figure_h4, 
                            daily_info=None, h4_info=None):
        """필터링 신호를 Slack으로 전송
        
        Args:
            coin_name: 코인명 (예: 'KRW-CARV')
            figure_daily: 일봉 그래프
            figure_h4: 4시간봉 그래프
            daily_info: 일봉 추가 정보 (dict)
            h4_info: 4시간봉 추가 정보 (dict)
        """
        if not self.is_enabled:
            return
        
        try:
            # 요약 메시지 작성
            message = self._create_signal_message(coin_name, daily_info, h4_info)
            
            # 메시지 전송
            self.slack.send_notification(message)
            
            # 그래프 전송
            self.slack.send_notification_with_image(f"📊 {coin_name} - 일봉 (Day1)", figure_daily)
            self.slack.send_notification_with_image(f"📈 {coin_name} - 4시간봉 (4H)", figure_h4)
            
            print(f"✅ {coin_name} Slack 전송 완료")
            return True
            
        except Exception as e:
            print(f"❌ {coin_name} Slack 전송 실패: {str(e)}")
            return False
    
    def send_daily_chart(self, coin_name, figure_daily, title=None):
        """일봉 차트만 전송
        
        Args:
            coin_name: 코인명
            figure_daily: 일봉 그래프
            title: 제목 (기본값: 코인명)
        """
        if not self.is_enabled:
            return
        
        try:
            title = title or f"{coin_name} - 일봉"
            self.slack.send_notification_with_image(title, figure_daily)
            print(f"✅ {coin_name} 일봉 전송 완료")
            return True
        except Exception as e:
            print(f"❌ 전송 실패: {str(e)}")
            return False
    
    def send_h4_chart(self, coin_name, figure_h4, title=None):
        """4시간봉 차트만 전송
        
        Args:
            coin_name: 코인명
            figure_h4: 4시간봉 그래프
            title: 제목 (기본값: 코인명)
        """
        if not self.is_enabled:
            return
        
        try:
            title = title or f"{coin_name} - 4시간봉"
            self.slack.send_notification_with_image(title, figure_h4)
            print(f"✅ {coin_name} 4시간봉 전송 완료")
            return True
        except Exception as e:
            print(f"❌ 전송 실패: {str(e)}")
            return False
    
    def send_alert(self, message: str):
        """간단한 알림 메시지 전송
        
        Args:
            message: 메시지 내용
        """
        if not self.is_enabled:
            return
        
        try:
            self.slack.send_notification(message)
            print(f"✅ 알림 전송 완료")
            return True
        except Exception as e:
            print(f"❌ 알림 전송 실패: {str(e)}")
            return False
    
    @staticmethod
    def _create_signal_message(coin_name, daily_info=None, h4_info=None):
        """신호 메시지 생성
        
        Args:
            coin_name: 코인명
            daily_info: 일봉 정보 (dict)
            h4_info: 4시간봉 정보 (dict)
            
        Returns:
            포맷된 메시지 문자열
        """
        timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        
        message = f"""🚀 *{coin_name}* - 필터링 신호 감지!

📊 **일봉 (Day1)**
• 저점 패턴: 하락 후 상승 시작 신호 감지"""
        
        if daily_info:
            for key, value in daily_info.items():
                message += f"\n• {key}: {value}"
        
        message += f"""

📈 **4시간봉 (4H)**
• MA200 상승: 지속 중
• 정배열 구간: 필터링 조건 충족"""
        
        if h4_info:
            for key, value in h4_info.items():
                message += f"\n• {key}: {value}"
        
        message += f"""

⏰ {timestamp}
"""
        return message.strip()


# ====================================================================
# 사용 예제 함수들
# ====================================================================

def quick_send_charts(coin_name, figure_daily, figure_h4):
    """빠르게 차트 전송 (설정 없이 사용)
    
    Args:
        coin_name: 코인명
        figure_daily: 일봉 그래프
        figure_h4: 4시간봉 그래프
    """
    notifier = SlackChartNotifier()
    notifier.send_filtered_signal(coin_name, figure_daily, figure_h4)


def send_error_alert(error_message: str, coin_name: str = None):
    """에러 알림 전송
    
    Args:
        error_message: 에러 메시지
        coin_name: 코인명 (선택사항)
    """
    notifier = SlackChartNotifier()
    prefix = f"[{coin_name}] " if coin_name else ""
    alert = f"⚠️ {prefix}에러 발생: {error_message}"
    notifier.send_alert(alert)


def send_summary_report(total_coins: int, signal_count: int, processed_time: str = None):
    """요약 리포트 전송
    
    Args:
        total_coins: 처리한 코인 수
        signal_count: 신호 감지한 코인 수
        processed_time: 처리 시간
    """
    notifier = SlackChartNotifier()
    
    timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    percentage = (signal_count / total_coins * 100) if total_coins > 0 else 0
    
    message = f"""📋 *일일 분석 완료*

📊 **통계**
• 분석 코인: {total_coins}개
• 신호 감지: {signal_count}개 ({percentage:.1f}%)
• 시간: {processed_time or 'N/A'}

⏰ {timestamp}
"""
    notifier.send_alert(message.strip())


# ====================================================================
# new_main_merge.ipynb 최상단에 추가할 코드
# ====================================================================

"""
# Slack 초기화 (첫 번째 셀에 추가)
from slack_helper import SlackChartNotifier
slack_notifier = SlackChartNotifier()


# 메인 루프에서 신호 감지 시 추가 (그래프 생성 후)
if not has_dark_yellow_after_daily_rise:
    print(f'{one_coin} 스킵')
    continue

# ... 그래프 생성 코드 ...
figure_daily = draw_daily.get_figure()
# ... 더 많은 그래프 코드 ...
figure_h4 = draw_h4.get_figure()

# 신호 감지 시 Slack 전송
daily_info = {
    "저점 개수": len(low_decline_then_rise_points),
    "가격": f"{upbit_daily.data.iloc[-1]['close']:,.0f}"
}

h4_info = {
    "정배열 구간": len(dark_yellow_group_start_end_upbit),
    "4H 가격": f"{upbit_h4.data.iloc[-1]['close']:,.0f}"
}

slack_notifier.send_filtered_signal(
    one_coin, 
    figure_daily, 
    figure_h4,
    daily_info=daily_info,
    h4_info=h4_info
)


# 최종 요약 리포트 (루프 끝에 추가)
send_summary_report(total_coins=200, signal_count=signal_count, processed_time="5m 32s")
"""
