from __future__ import annotations

import csv
import json
import re
import webbrowser
from datetime import datetime
from pathlib import Path


CSV_PATH = Path(r"C:\Users\es49lee\transaction history 2026-06-15.csv")
OUTPUT_HTML = Path(__file__).with_name("coin_history_chart.html")
DISPLAY_DIVISOR = 100_000_000


def parse_date(text: str) -> datetime:
    value = text.strip()
    candidates = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"날짜 형식을 해석할 수 없습니다: {text!r}") from exc


def parse_number(text: str) -> float:
    cleaned = re.sub(r"[^0-9.+\-eE]", "", text)
    if cleaned in {"", "+", "-", "."}:
        raise ValueError(f"숫자 형식을 해석할 수 없습니다: {text!r}")
    return float(cleaned)


def load_series(
    csv_path: Path,
) -> tuple[list[str], list[float], list[dict[str, float | str]], list[dict[str, float | str]]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {csv_path}")

    items: list[tuple[datetime, float]] = []
    deposits: list[dict[str, float | str]] = []
    withdrawals: list[dict[str, float | str]] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)

        for row in reader:
            if len(row) < 9:
                continue

            try:
                dt = parse_date(row[2])
                coin_amount = parse_number(row[8])
            except ValueError:
                continue

            items.append((dt, coin_amount))

            event_kind = row[1].strip().lower()
            if event_kind in {"deposit", "withdrawal"}:
                try:
                    tx_amount = parse_number(row[3]) / DISPLAY_DIVISOR
                except ValueError:
                    tx_amount = float("nan")

                point = {
                    "x": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "y": coin_amount,
                    "txAmount": tx_amount,
                }
                if event_kind == "deposit":
                    deposits.append(point)
                else:
                    withdrawals.append(point)

    if not items:
        raise ValueError("유효한 데이터가 없습니다. 3열(날짜), 9열(코인 수량)을 확인해 주세요.")

    items.sort(key=lambda x: x[0])
    labels = [d.strftime("%Y-%m-%d %H:%M:%S") for d, _ in items]
    values = [v for _, v in items]
    return labels, values, deposits, withdrawals


def build_html(
    labels: list[str],
    values: list[float],
    deposits: list[dict[str, float | str]],
    withdrawals: list[dict[str, float | str]],
) -> str:
    labels_json = json.dumps(labels, ensure_ascii=False)
    values_json = json.dumps(values)
    deposits_json = json.dumps(deposits)
    withdrawals_json = json.dumps(withdrawals)

    return f'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Coin History</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js"></script>
  <style>
    :root {{
      --bg1: #f7f8fa;
      --bg2: #ecf2ff;
      --text: #101828;
      --card: #ffffff;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", "Noto Sans KR", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 20% 20%, #dbe8ff 0%, transparent 40%),
        radial-gradient(circle at 80% 80%, #d7f5ff 0%, transparent 40%),
        linear-gradient(135deg, var(--bg1), var(--bg2));
      display: grid;
      place-items: center;
      padding: 16px;
    }}

    .card {{
      width: min(1100px, 100%);
      background: var(--card);
      border-radius: 18px;
      box-shadow: 0 20px 60px rgba(16, 24, 40, 0.12);
      padding: 18px;
    }}

    h1 {{
      margin: 0 0 10px;
      font-size: clamp(1.1rem, 2vw, 1.5rem);
      font-weight: 700;
    }}

    .hint {{
      margin: 0 0 14px;
      font-size: 0.92rem;
      color: #475467;
    }}

    .chart-wrap {{
      position: relative;
      width: 100%;
      height: min(66vh, 560px);
    }}

    @media (max-width: 768px) {{
      .card {{ padding: 12px; border-radius: 14px; }}
      .chart-wrap {{ height: 58vh; }}
    }}
  </style>
</head>
<body>
  <section class="card">
    <h1>날짜별 BTC 보유량 히스토리</h1>
    <p class="hint">그래프는 9번째 BTC 컬럼 원본 값을 사용합니다. 입금/출금 말풍선과 amount 툴팁만 100000000(1억)으로 나눈 값입니다. 마우스 휠 또는 드래그로 확대/축소, 드래그로 이동할 수 있습니다.</p>
    <div class="chart-wrap">
      <canvas id="coinChart"></canvas>
    </div>
  </section>

  <script>
    const labels = {labels_json};
    const values = {values_json};
    const depositPoints = {deposits_json};
    const withdrawalPoints = {withdrawals_json};

    const formatDisplayValue = (value, maxFractionDigits = 8) => {{
      return Number(value).toLocaleString(undefined, {{
        minimumFractionDigits: 0,
        maximumFractionDigits: maxFractionDigits
      }});
    }};

    const balloonLabelPlugin = {{
      id: "balloonLabelPlugin",
      afterDatasetsDraw(chart) {{
        const {{ ctx }} = chart;
        const eventDatasets = chart.data.datasets.filter(
          (dataset) => dataset.label === "Deposit" || dataset.label === "Withdrawal"
        );

        ctx.save();
        ctx.font = '12px "Segoe UI", "Noto Sans KR", sans-serif';
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";

        eventDatasets.forEach((dataset) => {{
          const datasetIndex = chart.data.datasets.indexOf(dataset);
          const meta = chart.getDatasetMeta(datasetIndex);
          meta.data.forEach((element, index) => {{
            const raw = dataset.data[index];
            const txAmount = Number(raw.txAmount);
            if (Number.isNaN(txAmount)) {{
              return;
            }}

            const isDeposit = dataset.label === "Deposit";
            const prefix = isDeposit ? "+" : "-";
            const text = `${{prefix}}${{formatDisplayValue(Math.abs(txAmount), 4)}}`;
            const x = element.x;
            const y = element.y - 24;
            const paddingX = 10;
            const bubbleHeight = 24;
            const textWidth = ctx.measureText(text).width;
            const bubbleWidth = textWidth + paddingX * 2;
            const left = x - bubbleWidth / 2;
            const top = y - bubbleHeight / 2;
            const radius = 12;
            const color = isDeposit ? "#16a34a" : "#dc2626";

            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.moveTo(left + radius, top);
            ctx.lineTo(left + bubbleWidth - radius, top);
            ctx.quadraticCurveTo(left + bubbleWidth, top, left + bubbleWidth, top + radius);
            ctx.lineTo(left + bubbleWidth, top + bubbleHeight - radius);
            ctx.quadraticCurveTo(left + bubbleWidth, top + bubbleHeight, left + bubbleWidth - radius, top + bubbleHeight);
            ctx.lineTo(x + 7, top + bubbleHeight);
            ctx.lineTo(x, top + bubbleHeight + 8);
            ctx.lineTo(x - 7, top + bubbleHeight);
            ctx.lineTo(left + radius, top + bubbleHeight);
            ctx.quadraticCurveTo(left, top + bubbleHeight, left, top + bubbleHeight - radius);
            ctx.lineTo(left, top + radius);
            ctx.quadraticCurveTo(left, top, left + radius, top);
            ctx.closePath();
            ctx.fill();

            ctx.fillStyle = "#ffffff";
            ctx.fillText(text, x, y);
          }});
        }});

        ctx.restore();
      }}
    }};

    const eventTooltip = (context, label) => {{
      const raw = context.raw || {{}};
      const txAmount = Number(raw.txAmount);
      if (!Number.isNaN(txAmount)) {{
        return `${{label}} (4열 amount / 1e8): ${{formatDisplayValue(txAmount, 4)}}`;
      }}
      return `${{label}} (4열 amount): 값 없음`;
    }};

    const ctx = document.getElementById("coinChart");
    new Chart(ctx, {{
      plugins: [balloonLabelPlugin],
      type: "line",
      data: {{
        labels,
        datasets: [
          {{
            label: "BTC 보유량",
            data: values,
            borderColor: "#1f6feb",
            backgroundColor: "rgba(31, 111, 235, 0.16)",
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.2,
            fill: true
          }},
          {{
            label: "Deposit",
            data: depositPoints,
            parsing: false,
            showLine: false,
            pointStyle: "triangle",
            pointRadius: 7,
            pointHoverRadius: 9,
            borderColor: "#16a34a",
            backgroundColor: "#16a34a"
          }},
          {{
            label: "Withdrawal",
            data: withdrawalPoints,
            parsing: false,
            showLine: false,
            pointStyle: "rectRot",
            pointRadius: 7,
            pointHoverRadius: 9,
            borderColor: "#dc2626",
            backgroundColor: "#dc2626"
          }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{ mode: "index", intersect: false }},
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            callbacks: {{
              label: (context) => {{
                if (context.dataset.label === "Deposit") {{
                  return eventTooltip(context, "Deposit");
                }}
                if (context.dataset.label === "Withdrawal") {{
                  return eventTooltip(context, "Withdrawal");
                }}
                return `BTC 보유량: ${{formatDisplayValue(context.parsed.y, 8)}}`;
              }}
            }}
          }},
          zoom: {{
            pan: {{
              enabled: true,
              mode: "x"
            }},
            zoom: {{
              wheel: {{ enabled: true }},
              pinch: {{ enabled: true }},
              drag: {{ enabled: true, backgroundColor: "rgba(31, 111, 235, 0.12)" }},
              mode: "x"
            }},
            limits: {{
              x: {{ min: 0, max: labels.length - 1 }}
            }}
          }}
        }},
        scales: {{
          x: {{
            ticks: {{ maxRotation: 0, autoSkip: true, maxTicksLimit: 12 }},
            grid: {{ color: "rgba(16, 24, 40, 0.08)" }}
          }},
          y: {{
            beginAtZero: false,
            ticks: {{ callback: (value) => formatDisplayValue(value, 8) }},
            grid: {{ color: "rgba(16, 24, 40, 0.12)" }}
          }}
        }}
      }}
    }});
  </script>
</body>
</html>
'''


def main() -> None:
    labels, values, deposits, withdrawals = load_series(CSV_PATH)
    html = build_html(labels, values, deposits, withdrawals)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    webbrowser.open(OUTPUT_HTML.resolve().as_uri())
    print(f"그래프 파일 생성 완료: {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
