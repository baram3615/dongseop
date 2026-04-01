# Slack 그래프 전송 - 구현 완료 요약

## ✅ 생성된 파일

### 1. **notification/slack_notification.py** (신규)
Slack으로 그래프 이미지를 전송하는 구현체
```python
from notification.slack_notification import SlackNotification

slack = SlackNotification(
    bot_token="토큰예시",
    channel_id="TC43WQ0SZ"
)

# 메시지만 전송
slack.send_notification("안녕하세요!")

# 그래프와 함께 전송
slack.send_notification_with_image("차트 제목", figure_object)

# 여러 그래프 전송
slack.send_notification_with_multiple_images(
    "여러 차트",
    {"일봉": fig_daily, "4시간봉": fig_h4}
)
```

### 2. **notification/notification_strategy.py** (수정)
추상 인터페이스에 이미지 전송 메서드 추가
```python
def send_notification_with_image(self, message: str, figure):
    """선택사항: 그래프와 함께 메시지 전송"""
    raise NotImplementedError(...)
```

### 3. **slack_helper.py** (신규)
쉬운 사용을 위한 헬퍼 클래스
```python
from slack_helper import SlackChartNotifier

notifier = SlackChartNotifier()

# 필터링된 신호 한 번에 전송
notifier.send_filtered_signal(
    coin_name="KRW-CARV",
    figure_daily=fig_daily,
    figure_h4=fig_h4,
    daily_info={"저점": 3, "가격": "150,000"},
    h4_info={"구간": 2, "현재가": "151,000"}
)

# 간단한 알림
notifier.send_alert("⚠️ 신호 감지!")
```

### 4. **문서 파일들**
- `QUICKSTART.md` - 5분 안에 시작하기
- `SLACK_SETUP_GUIDE.md` - 상세 설정 가이드  
- `slack_integration_guide.py` - 코드 통합 예제

---

## 🎯 Architecture 구조

```
┌─────────────────────────────────────────────────┐
│         new_main_merge.ipynb                    │
│    (필터링된 그래프 생성)                       │
└──────────────┬──────────────────────────────────┘
               │
               ▼
    ┌──────────────────────────┐
    │  SlackChartNotifier      │  (헬퍼)
    │  (slack_helper.py)       │
    └────────┬─────────────────┘
             │
             ▼
    ┌──────────────────────────────────┐
    │  SlackNotification               │
    │  (notification/slack_notification.py)
    │                                  │
    │  - send_notification()           │
    │  - send_notification_with_image()│
    │  - _save_figure_as_image()       │
    │  - _upload_file_to_slack()       │
    └────────┬─────────────────────────┘
             │
             ▼
        ┌─────────────┐
        │ Slack API   │
        │ chat/files  │
        └─────────────┘
```

---

## 📋 필요한 단계

### 1️⃣ 패키지 설치 (터미널)
```bash
pip install slack-sdk requests kaleido
```

### 2️⃣ Slack Bot 생성 (https://api.slack.com/apps)
- App 생성
- Scopes: `chat:write`, `files:write`, `chat:write.public`
- Bot Token, Channel ID 획득

### 3️⃣ 환경변수 설정 (PowerShell)
```powershell
$env:SLACK_BOT_TOKEN = "xoxb-..."
$env:SLACK_CHANNEL_ID = "C1234567890"
```

### 4️⃣ 코드 통합 (new_main_merge.ipynb)

**첫 셀에 추가:**
```python
from slack_helper import SlackChartNotifier
slack = SlackChartNotifier()
```

**신호 감지 시 추가:**
```python
if not has_dark_yellow_after_daily_rise:
    continue

# ... 기존 그래프 생성 코드 ...

slack.send_filtered_signal(one_coin, figure_daily, figure_h4)
```

---

## 🎨 인터페이스 설계 (Design Pattern)

### Strategy Pattern
```
NotificationStrategy (추상)
├── SMSNotification
└── SlackNotification  (새로 구현)
```

### 기능 확장성
- `send_notification()` - 기본 텍스트 전송
- `send_notification_with_image()` - 이미지 포함 전송 (선택사항)
- `send_notification_with_multiple_images()` - 복수 이미지 전송

---

## 💻 사용 예제

### 기본 사용
```python
from slack_helper import SlackChartNotifier

notifier = SlackChartNotifier()

# 신호 감지 시
notifier.send_filtered_signal(
    "KRW-CARV",
    figure_daily,
    figure_h4
)
```

### 상세 정보 포함
```python
notifier.send_filtered_signal(
    "KRW-CARV",
    figure_daily,
    figure_h4,
    daily_info={
        "저점 개수": 3,
        "현재가": "150,000 KRW"
    },
    h4_info={
        "정배열 구간": 2,
        "MA200": "상승"
    }
)
```

### 개별 전송
```python
notifier.send_alert("🚀 신호 감지!")
notifier.send_daily_chart("KRW-CARV", figure_daily)
notifier.send_h4_chart("KRW-CARV", figure_h4)
```

### 에러 알림
```python
from slack_helper import send_error_alert

try:
    # 어떤 작업...
except Exception as e:
    send_error_alert(str(e), "KRW-CARV")
```

---

## 🔧 고급 설정

### 여러 채널로 전송
```python
slack_channel_1 = SlackChartNotifier(channel_id="C111...")
slack_channel_2 = SlackChartNotifier(channel_id="C222...")

slack_channel_1.send_filtered_signal(coin, fig_d, fig_h4)
slack_channel_2.send_filtered_signal(coin, fig_d, fig_h4)
```

### 조건부 전송
```python
if signal_strength > threshold and price_momentum > min_momentum:
    slack.send_filtered_signal(coin, fig_d, fig_h4)
```

### 배치 전송
```python
for coin_name, signal_data in filtered_signals.items():
    slack.send_filtered_signal(
        coin_name,
        signal_data['daily_fig'],
        signal_data['h4_fig'],
        daily_info=signal_data['daily_metrics'],
        h4_info=signal_data['h4_metrics']
    )
```

---

## 📊 Slack 채널 예시

```
🚀 KRW-CARV - 필터링 신호 감지!

📊 일봉 (Day1)
• 저점 패턴: 하락 후 상승 시작 신호 감지
• 저점 개수: 3개
• 가격: 150,000 KRW

📈 4시간봉 (4H)
• MA200 상승: 지속 중
• 정배열 구간: 필터링 조건 충족
• 정배열 구간: 2개
• 현재가: 151,000 KRW

⏰ 2024-03-27 14:30:22

[이미지: 일봉 차트]
[이미지: 4시간봉 차트]
```

---

## ✨ 주요 특징

✅ **인터페이스 설계**: Strategy Pattern으로 NotificationStrategy를 따름
✅ **확장성**: 새로운 알림 방식 추가 용이
✅ **에러 처리**: 완벽한 예외 처리 및 로깅
✅ **이미지 저장**: Plotly 그래프를 PNG로 자동 변환
✅ **다양한 메서드**: 단일/복수 이미지, 텍스트 등 지원
✅ **Windows 호환**: 임시 파일 경로 자동 처리

---

## 📚 참고 자료

| 파일 | 용도 |
|------|------|
| [QUICKSTART.md](QUICKSTART.md) | 5분 빠른 시작 |
| [SLACK_SETUP_GUIDE.md](SLACK_SETUP_GUIDE.md) | 상세 설정 & 문제 해결 |
| [slack_integration_guide.py](slack_integration_guide.py) | 코드 통합 예제 |
| [slack_helper.py](slack_helper.py) | 헬퍼 함수 문서 |

---

## 🎓 학습 포인트

1. **Strategy Pattern**: 알림 방식을 확장하기 좋은 설계
2. **Python 추상 클래스**: Abstract Base Class 활용
3. **Slack API**: REST API를 통한 메시지/파일 전송
4. **Plotly 이미지화**: 그래프를 정적 이미지로 변환
5. **환경변수 관리**: 보안을 위한 토큰 처리

---

**✅ 구현 완료! 이제 필터링된 그래프를 Slack으로 바로 받아볼 수 있습니다!**

