# 🚀 Slack 그래프 전송 - 빠른 시작 가이드

## 📦 필요 패키지 설치 (1회만)

```bash
pip install slack-sdk requests kaleido
```

---

## 🔑 Slack 설정 (5분)

### Step 1: Slack Bot 생성
1. https://api.slack.com/apps → **Create New App**
2. **"From scratch"** 선택
3. App 이름: `BitMex-Alert`
4. Workspace 선택 → **Create App**

### Step 2: 권한 설정
1. **OAuth & Permissions** 메뉴
2. **Scopes** → 아래 권한 추가:
   ```
   ✓ chat:write
   ✓ files:write
   ✓ chat:write.public
   ```

### Step 3: 토큰 복사
1. **Bot User OAuth Token** 복사 (`xoxb-` 형식)
2. Slack에서 메시지받을 채널 우클릭 → **Channel ID** 복사

### Step 4: 환경변수 설정

**PowerShell에서:**
```powershell
$env:SLACK_BOT_TOKEN = "슬랙코드"
$env:SLACK_CHANNEL_ID = "C0APBAF5DPW"
```

또는 **`.env` 파일 생성:**
```
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=C1234567890
```

---

## ✅ 테스트 (선택사항)

새로운 Jupyter 셀에서:

```python
from slack_helper import SlackChartNotifier

notifier = SlackChartNotifier()
notifier.send_alert("🧪 테스트 메시지 - 정상 작동합니다!")
```

Slack 채널에 메시지가 나타나면 성공! ✅

---

## 🎯 코드 통합 (3가지 방법)

### 방법 1: 간단하게 (권장)

`new_main_merge.ipynb` 첫 셀에 추가:

```python
from slack_helper import SlackChartNotifier
slack = SlackChartNotifier()
```

필터 조건 만족 시 그래프 전송:

```python
if not has_dark_yellow_after_daily_rise:
    continue

# ... 그래프 생성 코드 ...

# 한 줄로 전송
slack.send_filtered_signal(one_coin, figure_daily, figure_h4)
```

---

### 방법 2: 상세 정보 포함

```python
slack.send_filtered_signal(
    one_coin,
    figure_daily,
    figure_h4,
    daily_info={
        "저점 개수": len(low_decline_then_rise_points),
        "가격": f"{upbit_daily.data.iloc[-1]['close']:,.0f} KRW"
    },
    h4_info={
        "정배열 구간": len(dark_yellow_group_start_end_upbit),
        "현재가": f"{upbit_h4.data.iloc[-1]['close']:,.0f} KRW"
    }
)
```

---

### 방법 3: 개별 전송

```python
slack.send_alert(f"🚀 {one_coin} 신호 감지!")
slack.send_daily_chart(one_coin, figure_daily)
slack.send_h4_chart(one_coin, figure_h4)
```

---

## 📂 생성된 파일 구조

```
dongseop/
├── notification/
│   ├── notification_strategy.py      ← 수정됨 (이미지 메서드 추가)
│   └── slack_notification.py         ← 새 파일 (SlackNotification 클래스)
├── slack_helper.py                   ← 새 파일 (헬퍼 함수)
├── slack_integration_guide.py         ← 참고 문서
├── SLACK_SETUP_GUIDE.md              ← 상세 가이드
└── QUICKSTART.md                     ← 이 파일
```

---

## 🎨 Slack 메시지 예시

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

[일봉 차트]
[4시간봉 차트]
```

---

## 🐛 문제 해결

| 문제 | 해결 |
|------|------|
| `SLACK_BOT_TOKEN not found` | 환경변수 설정 확인 (PowerShell 재시작 필요) |
| `Channel not found` | Channel ID 형식 확인 (C로 시작하는 12자리) |
| `kaleido not found` | `pip install kaleido` |
| 그래프 전송 안됨 | 토큰 권한: `files:write` 확인 |

---

## 📚 자세한 설명

- [전체 설정 가이드](SLACK_SETUP_GUIDE.md)
- [통합 예제 코드](slack_integration_guide.py)
- [헬퍼 함수 문서](slack_helper.py)

---

## 💡 팁

### 조건부 전송
```python
# 특정 조건일 때만 전송
if signal_strength > threshold:
    slack.send_filtered_signal(coin_name, fig_daily, fig_h4)
```

### 배치 전송
```python
# 여러 코인 신호를 모아서 한 번에 전송
signals = []
for coin_name, figs in collected_signals:
    slack.send_filtered_signal(coin_name, figs['daily'], figs['h4'])
```

### 에러 처리
```python
try:
    slack.send_filtered_signal(one_coin, figure_daily, figure_h4)
except Exception as e:
    print(f"Slack 전송 실패, 계속 진행: {e}")
    # 프로그램 중단 없이 계속 실행
```

---

## ❓ FAQ

**Q: Webhook URL 대신 Bot Token을 사용하는 이유?**  
A: Bot Token은 파일(이미지) 업로드를 지원하지만, Webhook은 지원하지 않습니다.

**Q: 여러 채널로 동시에 전송 가능?**  
A: 현재는 한 채널만 지원. 여러 채널이 필요하면 SlackChartNotifier를 여러 번 생성하세요.

**Q: 그래프 품질 조정?**  
A: `slack_notification.py`의 `_save_figure_as_image()` 메서드에서 width/height 조정 가능.

---

**설정 완료! 이제 Slack에서 실시간 신호를 받아보세요! 🎉**

