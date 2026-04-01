"""
필터링된 그래프를 Slack으로 전송하는 통합 예제
"""

# 필요 패키지 설치 (처음 한 번만):
# pip install slack-sdk requests kaleido

import os
from notification.slack_notification import SlackNotification

# ====================================================================
# 방법 1: 환경변수를 이용한 Slack 설정 (권장)
# ====================================================================
# Windows PowerShell에서 설정:
# $env:SLACK_BOT_TOKEN = "xoxb-your-bot-token"
# $env:SLACK_CHANNEL_ID = "C1234567890"

# 또는 .env 파일 사용 (python-dotenv):
# pip install python-dotenv
# .env 파일:
# SLACK_BOT_TOKEN=xoxb-your-bot-token
# SLACK_CHANNEL_ID=C1234567890

# ====================================================================
# 방법 2: 직접 토큰 전달
# ====================================================================

def get_slack_notifier(use_webhook=False):
    """Slack Notifier 생성
    
    Args:
        use_webhook (bool): Webhook 방식 사용 여부
        
    Returns:
        SlackNotification 인스턴스
    """
    
    if use_webhook:
        # Webhook 방식 (간단하지만 파일 업로드 미지원)
        webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        if not webhook_url:
            raise ValueError("SLACK_WEBHOOK_URL 환경변수를 설정하세요")
        return SlackNotification(webhook_url=webhook_url)
    else:
        # Bot Token 방식 (권장 - 파일 업로드 지원)
        bot_token = os.getenv('SLACK_BOT_TOKEN')
        channel_id = os.getenv('SLACK_CHANNEL_ID')
        
        if not bot_token or not channel_id:
            raise ValueError("SLACK_BOT_TOKEN과 SLACK_CHANNEL_ID 환경변수를 설정하세요")
        
        return SlackNotification(bot_token=bot_token, channel_id=channel_id)


# ====================================================================
# new_main_merge.ipynb에 통합하는 방법
# ====================================================================

"""
기존 코드에서 다음 부분을 찾아서:

    if not has_dark_yellow_after_daily_rise:
        print(f'{one_coin} 스킵: 일봉 빨간 라인 이후 진한 노란색 정배열 구간 없음')
        continue

    draw_h4 = BasicPriceWithRsiVisualization()
    ...
    figure_h4 = draw_h4.get_figure()


아래 코드를 추가하면 됩니다:
"""

# ========== 통합 코드 예제 ==========
def send_filtered_charts_to_slack(coin_name, figure_daily, figure_h4, 
                                   daily_rise_info="", h4_yellow_info=""):
    """필터링된 차트를 Slack으로 전송
    
    Args:
        coin_name: 코인명 (예: 'KRW-CARV')
        figure_daily: 일봉 그래프 (figure_daily 객체)
        figure_h4: 4시간봉 그래프 (figure_h4 객체)
        daily_rise_info: 일봉 상승 정보
        h4_yellow_info: 4시간봉 진한 노란색 구간 정보
    """
    try:
        slack = get_slack_notifier(use_webhook=False)  # Bot Token 방식
        
        # 요약 메시지 작성
        message = f"""
🚀 *{coin_name}* - 필터링 신호 감지

📊 **일봉 (Day1)**
- 저점 값에서 상승 신호 감지
{daily_rise_info}

📈 **4시간봉 (4H)**  
- MA200 상승 + 정렬된 정배열 구간 감지
{h4_yellow_info}

⏰ 생성 시간: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        # 메시지 전송
        slack.send_notification(message.strip())
        
        # 그래프 2개를 한 메시지에서 별도로 전송
        slack.send_notification_with_image(f"📌 {coin_name} - 일봉 차트", figure_daily)
        slack.send_notification_with_image(f"📌 {coin_name} - 4시간봉 차트", figure_h4)
        
        print(f"✅ {coin_name} 차트 Slack 전송 완료")
        
    except Exception as e:
        print(f"❌ {coin_name} Slack 전송 실패: {str(e)}")


# ========== new_main_merge.ipynb에 통합할 코드 ==========
"""
다음은 new_main_merge.ipynb의 끝 부분에 추가할 코드입니다:

# ===== Slack 전송 부분 (이 줄 아래를 추가) =====
    if has_dark_yellow_after_daily_rise:
        # 기존 그래프 표시 코드...
        
        # Slack 전송 추가
        from notification.slack_notification import SlackNotification
        import os
        
        try:
            slack = SlackNotification(
                bot_token=os.getenv('SLACK_BOT_TOKEN'),
                channel_id=os.getenv('SLACK_CHANNEL_ID')
            )
            
            # 요약 메시지
            message = f"🚀 {one_coin} - 필터링 신호 감지 (일봉 저점 상승 + 4H 정배열)"
            slack.send_notification(message)
            
            # 이미지 전송
            slack.send_notification_with_image(f"{one_coin} - 일봉", figure_daily)
            slack.send_notification_with_image(f"{one_coin} - 4시간봉", figure_h4)
            
            print(f"✅ {one_coin} Slack 전송 완료")
        except Exception as e:
            print(f"⚠️  {one_coin} Slack 전송 실패: {str(e)}")
"""
