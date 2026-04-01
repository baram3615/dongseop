# Slack 그래프 전송 설정 가이드

## 📋 목차
1. [필요 패키지 설치](#필요-패키지-설치)
2. [Slack Bot 생성 및 토큰 획득](#slack-bot-생성-및-토큰-획득)
3. [환경변수 설정](#환경변수-설정)
4. [코드 통합](#코드-통합)
5. [테스트](#테스트)

---

## 필요 패키지 설치

```bash
pip install slack-sdk requests kaleido
```

- **slack-sdk**: Slack API 통신
- **requests**: HTTP 요청
- **kaleido**: Plotly 그래프를 PNG로 저장

---

## Slack Bot 생성 및 토큰 획득

### 1단계: Slack Workspace에 앱 생성

1. [Slack API Dashboard](https://api.slack.com/apps) 방문
2. **"Create New App"** 클릭
3. **"From scratch"** 선택
4. App 이름 입력 (예: `BitMex-Alert`) 및 Workspace 선택
5. **"Create App"** 클릭

### 2단계: Bot Token 권한 설정

1. 왼쪽 메뉴에서 **"OAuth & Permissions"** 클릭
2. **"Scopes"** 섹션에서 다음 권한 추가:
   - `chat:write` - 메시지 전송
   - `files:write` - 파일 업로드
   - `chat:write.public` - 공개 채널에 메시지 전송

   ```
   선택 항목:
   ✓ chat:write
   ✓ files:write  
   ✓ chat:write.public
   ```

### 3단계: Bot Token 복사

1. 같은 페이지 상단에서 **"Bot User OAuth Token"** 복사
   - 형식: `xoxb-...`

### 4단계: Channel ID 확인

1. Slack Workspace에서 메시지를 받을 채널 선택
2. 채널명 우클릭 → **"View channel details"**
3. 하단의 **"Channel ID"** 복사
   - 형식: `C1234567890`

---

## 환경변수 설정

### 방법 1: Windows PowerShell (권장)

```powershell
# PowerShell 열기 (관리자 권한)
$env:SLACK_BOT_TOKEN = "xoxb-your-token-here"
$env:SLACK_CHANNEL_ID = "C1234567890"

# 확인
$env:SLACK_BOT_TOKEN
$env:SLACK_CHANNEL_ID
```

### 방법 2: .env 파일 사용

프로젝트 루트(`c:\Users\baram\dongseop\dongseop\`)에 `.env` 파일 생성:

```bash
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_CHANNEL_ID=C1234567890
```

Python 코드에서:

```python
from dotenv import load_dotenv
import os

load_dotenv()
bot_token = os.getenv('SLACK_BOT_TOKEN')
channel_id = os.getenv('SLACK_CHANNEL_ID')
```

### 방법 3: .env.example로 관리

`.env.example` (깃에 커밋):
```bash
SLACK_BOT_TOKEN=your-bot-token-here
SLACK_CHANNEL_ID=your-channel-id-here
```

`.gitignore`에 추가:
```bash
.env
```

---

## 코드 통합

### new_main_merge.ipynb에 추가할 코드

**첫 번째 셀 (임포트 부분)**에 추가:

```python
from notification.slack_notification import SlackNotification
import os

# Slack 초기화
try:
    slack = SlackNotification(
        bot_token=os.getenv('SLACK_BOT_TOKEN'),
        channel_id=os.getenv('SLACK_CHANNEL_ID')
    )
    slack_enabled = True
    print("✅ Slack 연결 성공")
except Exception as e:
    print(f"⚠️  Slack 연결 실패: {str(e)}")
    slack_enabled = False
```

**메인 로직 (그래프 생성 후)**에 추가:

```python
# 기존 코드...
if not has_dark_yellow_after_daily_rise:
    print(f'{one_coin} 스킵: 일봉 빨간 라인 이후 진한 노란색 정배열 구간 없음')
    continue

draw_h4 = BasicPriceWithRsiVisualization()
# ... 기존 그래프 생성 코드 ...
figure_h4 = draw_h4.get_figure()

# ========== 여기부터 추가 ==========
# Slack으로 그래프 전송
if slack_enabled:
    try:
        # 요약 메시지
        summary = f"""
🚀 *{one_coin}* - 필터링 신호 감지

📊 **조건**:
✓ 일봉: 저점에서 상승 시작
✓ 4시간봉: MA200 상승 + 정렬된 정배열 구간

⏰ {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        slack.send_notification(summary.strip())
        slack.send_notification_with_image(f"{one_coin} - 일봉 (Day1)", figure_daily)
        slack.send_notification_with_image(f"{one_coin} - 4시간봉 (4H)", figure_h4)
        
        print(f"✅ {one_coin} Slack 전송 완료")
        
    except Exception as e:
        print(f"⚠️  {one_coin} Slack 전송 실패: {str(e)}")
```

---

## 테스트

### 간단한 테스트 스크립트

새로운 Jupyter 셀에서 실행:

```python
import os
from notification.slack_notification import SlackNotification

# 기본 메시지 테스트
try:
    slack = SlackNotification(
        bot_token=os.getenv('SLACK_BOT_TOKEN'),
        channel_id=os.getenv('SLACK_CHANNEL_ID')
    )
    
    slack.send_notification("🧪 테스트 메시지 - SlackNotification 정상 작동!")
    print("✅ 테스트 성공")
    
except Exception as e:
    print(f"❌ 테스트 실패: {str(e)}")
```

### 그래프 전송 테스트

```python
import plotly.graph_objects as go
from notification.slack_notification import SlackNotification
import os

# 샘플 그래프 생성
fig = go.Figure(data=go.Scatter(y=[4, 1, 3, 7]))
fig.update_layout(title="테스트 그래프")

# 전송
try:
    slack = SlackNotification(
        bot_token=os.getenv('SLACK_BOT_TOKEN'),
        channel_id=os.getenv('SLACK_CHANNEL_ID')
    )
    
    slack.send_notification_with_image("테스트 그래프 전송", fig)
    print("✅ 그래프 전송 성공")
    
except Exception as e:
    print(f"❌ 그래프 전송 실패: {str(e)}")
```

---

## 🎯 권장 설정

### 프로젝트 구조

```
dongseop/
├── notification/
│   ├── notification_strategy.py  ✅ 업데이트됨
│   ├── sms_notification.py
│   └── slack_notification.py      ✅ 새 파일
├── new_main_merge.ipynb           ← 코드 추가
├── slack_integration_guide.py      ← 참고
├── .env                            ← 토큰 저장 (gitignore)
└── .env.example
```

### .gitignore 업데이트

```bash
# .gitignore
.env
.DS_Store
__pycache__/
*.pyc
```

---

## ❓ 문제 해결

### "kaleido not found" 에러
```bash
pip install --upgrade kaleido
```

### "Slack API 에러: invalid_auth"
- 토큰 형식 확인 (`xoxb-`로 시작하는지)
- 토큰 만료 여부 확인
- Slack API Dashboard에서 토큰 재생성

### "Channel not found" 에러
- Channel ID 형식 확인 (8-12자리 알파벳/숫자)
- Bot이 해당 채널에 초대되었는지 확인

### 그래프가 PNG로 저장되지 않음
- `kaleido` 설치 확인
- Plotly 버전 확인: `pip install --upgrade plotly`
- Windows 환경에서 임시 디렉토리 권한 확인

---

## 📚 추가 리소스

- [Slack API 문서](https://api.slack.com/docs)
- [Slack SDK Python](https://slack.dev/python-slack-sdk/)
- [Plotly 이미지 저장](https://plotly.com/python/static-image-export/)

