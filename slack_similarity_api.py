import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import threading
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
from fastapi import BackgroundTasks
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pydantic import Field
from plotly.subplots import make_subplots

from core.upbit import Upbit
from loader.upbit_realtimedata_loader import UpbitRealtimeDataLoader
from notification.slack_notification import SlackNotification
from new_main_merge import parse_coin_filter as parse_merge_coin_filter
from new_main_merge import run_once as run_merge_once
from processing.moving_average import MovingAverageProcessing


APP_NAME = "slack-similarity-api"
DEFAULT_INTERVAL = "day1"
DEFAULT_LOAD_COUNT = 1600
DEFAULT_MIN_WINDOW = 20
DEFAULT_TOP_N = 20
DEFAULT_OVERLAP_THRESHOLD = 10
DEFAULT_WINDOW_RATIO = 0.2
MA20_GAP_WEIGHT = 2.0
MA60_GAP_WEIGHT = 1.0
SIMILARITY_INTERVAL_ALIASES = {
    "일봉": "day1",
    "day1": "day1",
    "daily": "day1",
    "1d": "day1",
    "4시간봉": "minute240",
    "minute240": "minute240",
    "240m": "minute240",
    "4h": "minute240",
    "15분봉": "minute15",
    "minute15": "minute15",
    "15m": "minute15",
}
SIMILARITY_INTERVAL_LABELS = {
    "day1": "일봉",
    "minute240": "4시간봉",
    "minute15": "15분봉",
}
SIMILARITY_INTERVAL_MINUTES = {
    "minute240": 240,
    "minute15": 15,
}
SLACK_CHANNEL_UNIQUE = "C0ASM57RV9T"
WRITE_LOG_FILE = os.path.join(os.path.dirname(__file__), "trade_write_log.json")
WRITE_LOG_LOCK = threading.Lock()


app = FastAPI(title=APP_NAME)


class SimilarityRunRequest(BaseModel):
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    coin_id: str = Field(default="KRW-BTC")
    interval: str = Field(default=DEFAULT_INTERVAL)
    load_count: int = Field(default=DEFAULT_LOAD_COUNT)
    top_n: int = Field(default=DEFAULT_TOP_N)
    overlap_threshold: int = Field(default=DEFAULT_OVERLAP_THRESHOLD)
    window_ratio: float = Field(default=DEFAULT_WINDOW_RATIO)
    send_to_slack: bool = Field(default=False)
    channel_id: Optional[str] = Field(default=None)
    include_image_base64: bool = Field(default=False)


# -----------------------------
# Similarity tracker core logic
# -----------------------------
def build_daily_price_ma_df(
    coin_id: str,
    interval: str = DEFAULT_INTERVAL,
    load_count: int = DEFAULT_LOAD_COUNT,
) -> pd.DataFrame:
    upbit = Upbit()
    upbit.set_loader(UpbitRealtimeDataLoader(coin_id, interval, load_count))
    upbit.load()
    upbit.add_sub_indicator([MovingAverageProcessing()])

    df = upbit.data.copy()
    df = df[["timestamp_kst", "open", "high", "low", "close", "ma_20", "ma_60"]].copy()
    df["timestamp_kst"] = pd.to_datetime(df["timestamp_kst"])
    return df


def _normalize_feature_matrix(
    segment: pd.DataFrame,
    columns=("close", "ma_20", "ma_60"),
) -> np.ndarray:
    feature_frame = segment[list(columns)].astype(float).copy()
    feature_frame["close_ma20_gap_pct"] = ((feature_frame["close"] / feature_frame["ma_20"]) - 1.0) * MA20_GAP_WEIGHT
    feature_frame["close_ma60_gap_pct"] = ((feature_frame["close"] / feature_frame["ma_60"]) - 1.0) * MA60_GAP_WEIGHT

    values = feature_frame.to_numpy()
    if values.size == 0:
        return values

    mean = values.mean(axis=0)
    std = values.std(axis=0, ddof=0)
    std = np.where(std == 0, 1.0, std)
    return (values - mean) / std


def _dtw_distance(seq_a: np.ndarray, seq_b: np.ndarray, window_ratio: float = DEFAULT_WINDOW_RATIO) -> float:
    n = len(seq_a)
    m = len(seq_b)
    if n == 0 or m == 0:
        return float("inf")

    max_window = max(1, int(max(n, m) * window_ratio))
    dtw = np.full((n + 1, m + 1), np.inf)
    dtw[0, 0] = 0.0

    for i in range(1, n + 1):
        start_j = max(1, i - max_window)
        end_j = min(m, i + max_window)
        for j in range(start_j, end_j + 1):
            cost = np.linalg.norm(seq_a[i - 1] - seq_b[j - 1])
            dtw[i, j] = cost + min(
                dtw[i - 1, j],
                dtw[i, j - 1],
                dtw[i - 1, j - 1],
            )

    return float(dtw[n, m] / (n + m))


def define_target_interval(df: pd.DataFrame, start_date: str, end_date: str) -> Dict:
    df = df.copy()
    df["timestamp_kst"] = pd.to_datetime(df["timestamp_kst"])

    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    if start_ts > end_ts:
        raise ValueError("start_date는 end_date보다 빠르거나 같아야 합니다.")

    target_mask = (df["timestamp_kst"] >= start_ts) & (df["timestamp_kst"] <= end_ts)
    if target_mask.sum() == 0:
        raise ValueError("지정한 기준 날짜가 데이터에 없습니다.")

    target_df = df.loc[target_mask].copy()
    return {
        "start_ts": target_df["timestamp_kst"].iloc[0],
        "end_ts": target_df["timestamp_kst"].iloc[-1],
        "start_date": target_df["timestamp_kst"].iloc[0],
        "end_date": target_df["timestamp_kst"].iloc[-1],
        "window_len": len(target_df),
    }


def find_similar_periods_dtw(
    df: pd.DataFrame,
    start_date: str,
    end_date: str,
    columns=("close", "ma_20", "ma_60"),
    min_window: int = DEFAULT_MIN_WINDOW,
    top_n: int = DEFAULT_TOP_N,
    window_ratio: float = DEFAULT_WINDOW_RATIO,
) -> pd.DataFrame:
    df = df.copy()
    df["timestamp_kst"] = pd.to_datetime(df["timestamp_kst"])
    df = df.sort_values("timestamp_kst").reset_index(drop=True)

    target_interval = define_target_interval(df, start_date, end_date)
    target_segment = df.loc[
        (df["timestamp_kst"] >= target_interval["start_ts"])
        & (df["timestamp_kst"] <= target_interval["end_ts"]),
        list(columns),
    ].copy().dropna()

    if len(target_segment) < min_window:
        raise ValueError("기준 구간이 너무 짧습니다.")

    target_feature = _normalize_feature_matrix(target_segment, columns)
    window_len = len(target_segment)

    results = []
    for start_idx in range(0, max(0, len(df) - window_len + 1)):
        candidate_segment = df.iloc[start_idx:start_idx + window_len][list(columns)].copy().dropna()
        if len(candidate_segment) != window_len:
            continue

        end_idx = start_idx + window_len - 1
        candidate_feature = _normalize_feature_matrix(candidate_segment, columns)
        distance = _dtw_distance(target_feature, candidate_feature, window_ratio=window_ratio)

        results.append(
            {
                "start_idx": start_idx,
                "end_idx": end_idx,
                "start_date": df.iloc[start_idx]["timestamp_kst"],
                "end_date": df.iloc[end_idx]["timestamp_kst"],
                "window_len": window_len,
                "dtw_distance": distance,
                "similarity_score": 1 / (1 + distance),
            }
        )

    if not results:
        raise ValueError("유사 구간 계산 결과가 없습니다.")

    result_df = pd.DataFrame(results).sort_values("dtw_distance").reset_index(drop=True)
    return result_df.head(top_n)


def filter_non_overlapping_matches(similar_periods: pd.DataFrame, overlap_threshold: int = DEFAULT_OVERLAP_THRESHOLD) -> pd.DataFrame:
    _ = overlap_threshold

    if similar_periods.empty:
        return similar_periods.copy()

    filtered = similar_periods.sort_values(["dtw_distance", "similarity_score"], ascending=[True, False]).copy()
    filtered["start_ts"] = pd.to_datetime(filtered["start_date"])
    filtered["end_ts"] = pd.to_datetime(filtered["end_date"])

    kept_rows = []
    for _, row in filtered.iterrows():
        start_ts = row["start_ts"]
        end_ts = row["end_ts"]
        overlaps = False
        for kept in kept_rows:
            if not ((end_ts < kept["start_ts"]) or (start_ts > kept["end_ts"])):
                overlaps = True
                break
        if not overlaps:
            kept_rows.append(row.to_dict())

    return pd.DataFrame(kept_rows)


def build_similarity_figure(
    df: pd.DataFrame,
    similar_periods: pd.DataFrame,
    start_date: str,
    end_date: str,
    overlap_threshold: int = DEFAULT_OVERLAP_THRESHOLD,
):
    df = df.copy()
    df["timestamp_kst"] = pd.to_datetime(df["timestamp_kst"])
    df = df.sort_values("timestamp_kst").reset_index(drop=True)

    if similar_periods.empty:
        raise ValueError("유사 구간이 없습니다.")

    target_interval = define_target_interval(df, start_date, end_date)
    kept = filter_non_overlapping_matches(similar_periods, overlap_threshold=overlap_threshold)

    fig = make_subplots(rows=1, cols=1)
    fig.add_trace(
        go.Scatter(
            x=df["timestamp_kst"],
            y=df["close"],
            mode="lines",
            name="close",
            line=dict(color="black", width=1.5),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["timestamp_kst"],
            y=df["ma_20"],
            mode="lines",
            name="ma_20",
            line=dict(color="royalblue", width=1.5),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["timestamp_kst"],
            y=df["ma_60"],
            mode="lines",
            name="ma_60",
            line=dict(color="orange", width=1.5),
        )
    )

    fig.add_vrect(
        x0=target_interval["start_ts"],
        x1=target_interval["end_ts"],
        fillcolor="rgba(255, 0, 0, 0.15)",
        line_width=0,
        annotation_text=f"Target Window<br>{target_interval['start_date'].strftime('%Y-%m-%d')} ~ {target_interval['end_date'].strftime('%Y-%m-%d')}",
        annotation_position="top right",
    )

    kept = kept.reset_index(drop=True)
    label_offset_step = 18
    for idx, (_, row) in enumerate(kept.iterrows()):
        start_label = row["start_date"].strftime("%Y-%m-%d")
        end_label = row["end_date"].strftime("%Y-%m-%d")
        fig.add_vrect(
            x0=row["start_ts"],
            x1=row["end_ts"],
            fillcolor="rgba(0, 123, 255, 0.15)",
            line_width=0,
            annotation_text=f"{start_label} ~ {end_label}<br>score={row['similarity_score']:.3f}",
            annotation_position="top left",
        )
        fig.add_annotation(
            x=row["start_ts"] + (row["end_ts"] - row["start_ts"]) / 2,
            y=1.02,
            yref="paper",
            text=f"{start_label} ~ {end_label}",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1,
            arrowcolor="#1f77b4",
            ax=0,
            ay=-(30 + idx * label_offset_step),
            bgcolor="rgba(255, 255, 255, 0.9)",
            bordercolor="#1f77b4",
            borderwidth=1,
            font=dict(size=11, color="#1f1f1f"),
        )

    fig.update_layout(
        title="DTW Similarity Matches with Target Window",
        xaxis_title="Date",
        yaxis_title="Price",
        template="plotly_white",
        height=600,
        margin=dict(t=140),
    )

    return fig, kept, target_interval


def run_similarity_tracker(
    start_date: str,
    end_date: str,
    coin_id: str = "KRW-BTC",
    interval: str = DEFAULT_INTERVAL,
    load_count: int = DEFAULT_LOAD_COUNT,
    top_n: int = DEFAULT_TOP_N,
    overlap_threshold: int = DEFAULT_OVERLAP_THRESHOLD,
    window_ratio: float = DEFAULT_WINDOW_RATIO,
):
    start_date, end_date = _validate_similarity_time_range(start_date, end_date, interval)
    daily_df = build_daily_price_ma_df(coin_id=coin_id, interval=interval, load_count=load_count)

    similar_periods = find_similar_periods_dtw(
        daily_df,
        start_date=start_date,
        end_date=end_date,
        top_n=top_n,
        window_ratio=window_ratio,
    )

    fig, kept, target_interval = build_similarity_figure(
        daily_df,
        similar_periods,
        start_date=start_date,
        end_date=end_date,
        overlap_threshold=overlap_threshold,
    )

    return {
        "coin_id": coin_id,
        "interval": interval,
        "start_date": str(target_interval["start_date"].date()),
        "end_date": str(target_interval["end_date"].date()),
        "window_len": int(target_interval["window_len"]),
        "similar_periods": similar_periods,
        "kept": kept,
        "figure": fig,
    }


# -----------------------------
# Slack helpers
# -----------------------------
def _verify_slack_signature(request: Request, body: bytes) -> None:
    signing_secret = os.getenv("SLACK_SIGNING_SECRET", "").strip()
    if not signing_secret:
        # 개발 편의: 서명 시크릿 미설정이면 검증 스킵
        return

    timestamp = request.headers.get("x-slack-request-timestamp", "")
    slack_signature = request.headers.get("x-slack-signature", "")

    if not timestamp or not slack_signature:
        raise HTTPException(status_code=401, detail="Missing Slack signature headers")

    # 재전송 공격 방지: 5분 초과 요청 차단
    now_ts = int(dt.datetime.now(dt.timezone.utc).timestamp())
    if abs(now_ts - int(timestamp)) > 60 * 5:
        raise HTTPException(status_code=401, detail="Stale Slack request")

    basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    digest = hmac.new(
        signing_secret.encode("utf-8"),
        basestring.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    expected = f"v0={digest}"

    if not hmac.compare_digest(expected, slack_signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")


def _normalize_similarity_interval(interval_text: Optional[str]) -> str:
    normalized = (interval_text or "").strip().lower()
    if not normalized:
        return DEFAULT_INTERVAL

    if normalized not in SIMILARITY_INTERVAL_ALIASES:
        supported = ", ".join(["일봉", "4시간봉", "15분봉"])
        raise ValueError(f"지원하지 않는 interval입니다. 지원값: {supported}")

    return SIMILARITY_INTERVAL_ALIASES[normalized]


def _looks_like_time_token(token: str) -> bool:
    return bool(re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", token.strip()))


def _raw_similarity_timestamp_to_text(raw_text: str) -> str:
    return raw_text.strip().replace("T", " ")


def _parse_similarity_timestamp(raw_text: str) -> pd.Timestamp:
    return pd.Timestamp(_raw_similarity_timestamp_to_text(raw_text))


def _validate_similarity_time_range(start_text: str, end_text: str, interval: str) -> Tuple[str, str]:
    start_ts = _parse_similarity_timestamp(start_text)
    end_ts = _parse_similarity_timestamp(end_text)

    if start_ts > end_ts:
        raise ValueError("start_date는 end_date보다 빠르거나 같아야 합니다.")

    if interval == DEFAULT_INTERVAL:
        return start_ts.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d")

    if ":" not in _raw_similarity_timestamp_to_text(start_text) or ":" not in _raw_similarity_timestamp_to_text(end_text):
        interval_label = SIMILARITY_INTERVAL_LABELS.get(interval, interval)
        raise ValueError(f"{interval_label}은 시작/종료 시각까지 입력해야 합니다. 예: 2026-06-01 00:00:00")

    interval_minutes = SIMILARITY_INTERVAL_MINUTES[interval]
    interval_label = SIMILARITY_INTERVAL_LABELS.get(interval, interval)
    for label, timestamp in (("start_date", start_ts), ("end_date", end_ts)):
        total_minutes = timestamp.hour * 60 + timestamp.minute
        if total_minutes % interval_minutes != 0 or timestamp.second != 0 or timestamp.microsecond != 0:
            raise ValueError(
                f"{interval_label}은 {label}가 봉 시작 시각에 맞아야 합니다. 예: "
                f"{'00:00:00, 04:00:00, 08:00:00' if interval == 'minute240' else '00:00:00, 00:15:00, 00:30:00'}"
            )

    return start_ts.strftime("%Y-%m-%d %H:%M:%S"), end_ts.strftime("%Y-%m-%d %H:%M:%S")


def _parse_slack_text(text: str) -> Tuple[str, str, str, str]:
    # 지원 형식
    # 1) 2026-06-01 2026-08-01
    # 2) 2026-06-01 2026-08-01 KRW-BTC
    # 3) 2026-06-01 2026-08-01 KRW-BTC 4시간봉
    # 4) start=2026-06-01 end=2026-08-01 coin=KRW-BTC interval=15분봉
    text = (text or "").strip()
    if not text:
        raise ValueError("입력값이 비어 있습니다.")

    if "start=" in text and "end=" in text:
        chunks = dict(part.split("=", 1) for part in text.split() if "=" in part)
        start_date = chunks.get("start", "")
        end_date = chunks.get("end", "")
        coin_id = chunks.get("coin", "KRW-BTC")
        interval = _normalize_similarity_interval(chunks.get("interval", DEFAULT_INTERVAL))
    else:
        parts = text.split()
        if len(parts) < 2:
            raise ValueError("입력 형식: START END [COIN] [INTERVAL]")

        if len(parts) >= 4 and _looks_like_time_token(parts[1]) and _looks_like_time_token(parts[3]):
            start_date = f"{parts[0]} {parts[1]}"
            end_date = f"{parts[2]} {parts[3]}"
            extra_tokens = parts[4:]
        else:
            start_date = parts[0]
            end_date = parts[1]
            extra_tokens = parts[2:]

        coin_id = "KRW-BTC"
        interval = DEFAULT_INTERVAL

        for token in extra_tokens:
            if token.startswith("coin="):
                coin_id = token.split("=", 1)[1]
            elif token.startswith("interval="):
                interval = _normalize_similarity_interval(token.split("=", 1)[1])
            elif token.upper().startswith("KRW-"):
                coin_id = token.upper()
            else:
                interval = _normalize_similarity_interval(token)

    start_date, end_date = _validate_similarity_time_range(start_date, end_date, interval)

    return start_date, end_date, coin_id, interval


def _parse_checkall_text(text: str) -> Dict[str, object]:
    text = (text or "").strip()
    if not text:
        return {
            "coin_filter": None,
            "limit": None,
            "visualize": False,
        }

    coin_filter_raw = None
    limit = None
    visualize = False

    for token in text.split():
        if token.startswith("coin="):
            coin_filter_raw = token.split("=", 1)[1]
        elif token.startswith("limit="):
            value = token.split("=", 1)[1]
            limit = int(value)
        elif token.startswith("visualize="):
            value = token.split("=", 1)[1].lower()
            visualize = value in {"1", "true", "yes", "y", "on"}
        else:
            if coin_filter_raw is None and any(separator in token for separator in [",", "KRW-"]):
                coin_filter_raw = token
            elif limit is None and token.isdigit():
                limit = int(token)

    return {
        "coin_filter": parse_merge_coin_filter(coin_filter_raw),
        "limit": limit,
        "visualize": visualize,
    }


def _parse_write_text(text: str) -> Dict[str, object]:
    # 지원 형식
    # /write 매수 10000 63403
    # /write 매수 10000 63403 2026-08-29 23:00:02
    tokens = (text or "").strip().split()
    if len(tokens) < 3:
        raise ValueError("입력 형식: /write 매수|매도 비중 가격 [YYYY-MM-DD HH:MM:SS]")

    side = tokens[0]
    if side not in {"매수", "매도"}:
        raise ValueError("첫 번째 값은 매수 또는 매도여야 합니다.")

    try:
        size = float(tokens[1])
        price = float(tokens[2])
    except ValueError as exc:
        raise ValueError("비중과 가격은 숫자로 입력해야 합니다.") from exc

    if len(tokens) >= 5:
        timestamp_text = f"{tokens[3]} {tokens[4]}"
    elif len(tokens) == 4:
        # 단일 토큰 datetime 허용: YYYY-MM-DDTHH:MM:SS
        timestamp_text = tokens[3].replace("T", " ")
    else:
        timestamp_text = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        executed_at = pd.Timestamp(timestamp_text).to_pydatetime()
    except Exception as exc:
        raise ValueError("시간 형식이 올바르지 않습니다. 예: 2026-08-29 23:00:02") from exc

    date_key = executed_at.strftime("%Y-%m-%d")

    return {
        "side": side,
        "size": size,
        "price": price,
        "executed_at": executed_at.strftime("%Y-%m-%d %H:%M:%S"),
        "date_key": date_key,
    }


def _load_write_log() -> Dict[str, list]:
    if not os.path.exists(WRITE_LOG_FILE):
        return {}

    try:
        with open(WRITE_LOG_FILE, "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
            if isinstance(data, dict):
                return data
            return {}
    except Exception:
        return {}


def _save_write_log(data: Dict[str, list]) -> None:
    # 날짜 키를 정렬해서 사람이 보기 쉽게 저장
    ordered = {key: data[key] for key in sorted(data.keys())}
    with open(WRITE_LOG_FILE, "w", encoding="utf-8") as file_obj:
        json.dump(ordered, file_obj, ensure_ascii=False, indent=2)


def _append_write_record(record: Dict[str, object]) -> Dict[str, object]:
    entry = {
        "side": record["side"],
        "size": record["size"],
        "price": record["price"],
        "executed_at": record["executed_at"],
        "created_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    with WRITE_LOG_LOCK:
        data = _load_write_log()
        bucket = data.setdefault(record["date_key"], [])
        bucket.append(entry)
        _save_write_log(data)

    return entry


def _flatten_write_log(data: Dict[str, list]) -> list:
    rows = []
    for date_key, items in data.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            executed_at_text = str(item.get("executed_at", ""))
            try:
                executed_at = pd.Timestamp(executed_at_text).to_pydatetime()
            except Exception:
                # 파싱 실패 항목은 맨 뒤로 가도록 최소 시간 사용
                executed_at = dt.datetime.min
            rows.append(
                {
                    "date_key": date_key,
                    "entry": item,
                    "executed_at": executed_at,
                }
            )
    return rows


def _group_rows_by_date(rows: list) -> Dict[str, list]:
    grouped = {}
    for row in rows:
        entry = row["entry"]
        executed_at_text = str(entry.get("executed_at", ""))
        try:
            date_key = pd.Timestamp(executed_at_text).strftime("%Y-%m-%d")
        except Exception:
            date_key = str(row.get("date_key", "unknown"))
        grouped.setdefault(date_key, []).append(entry)

    # 날짜별/시간별로 사람이 보기 좋게 정렬
    for date_key, items in grouped.items():
        items.sort(key=lambda one: str(one.get("executed_at", "")))

    return {key: grouped[key] for key in sorted(grouped.keys())}


def _parse_delete_text(text: str) -> Dict[str, object]:
    # 지원 형식
    # /delete r 2026-08-13 00:00:00 2026-08-13 01:00:00
    # /delete l 5
    tokens = (text or "").strip().split()
    if len(tokens) < 2:
        raise ValueError("입력 형식: /delete r 시작일시 종료일시 또는 /delete l 개수")

    mode = tokens[0].lower()
    if mode == "r":
        if len(tokens) < 5:
            raise ValueError("range 삭제 형식: /delete r YYYY-MM-DD HH:MM:SS YYYY-MM-DD HH:MM:SS")

        start_text = f"{tokens[1]} {tokens[2]}"
        end_text = f"{tokens[3]} {tokens[4]}"
        start_dt = pd.Timestamp(start_text).to_pydatetime()
        end_dt = pd.Timestamp(end_text).to_pydatetime()
        if start_dt > end_dt:
            raise ValueError("시작 시간이 종료 시간보다 늦을 수 없습니다.")

        return {
            "mode": "range",
            "start_dt": start_dt,
            "end_dt": end_dt,
        }

    if mode == "l":
        count = int(tokens[1])
        if count <= 0:
            raise ValueError("latest 삭제 개수는 1 이상이어야 합니다.")
        return {
            "mode": "latest",
            "count": count,
        }

    raise ValueError("삭제 모드는 r(range) 또는 l(latest)만 지원합니다.")


def _delete_write_records(delete_args: Dict[str, object]) -> Dict[str, object]:
    with WRITE_LOG_LOCK:
        data = _load_write_log()
        rows = _flatten_write_log(data)

        before_count = len(rows)
        removed = 0

        if delete_args["mode"] == "range":
            start_dt = delete_args["start_dt"]
            end_dt = delete_args["end_dt"]
            kept_rows = []
            for row in rows:
                executed_at = row["executed_at"]
                if start_dt <= executed_at <= end_dt:
                    removed += 1
                else:
                    kept_rows.append(row)
            rows = kept_rows

        elif delete_args["mode"] == "latest":
            count = int(delete_args["count"])
            rows_sorted = sorted(rows, key=lambda row: row["executed_at"], reverse=True)
            to_remove = min(count, len(rows_sorted))
            remove_ids = set(id(one) for one in rows_sorted[:to_remove])
            kept_rows = []
            for row in rows:
                if id(row) in remove_ids:
                    removed += 1
                else:
                    kept_rows.append(row)
            rows = kept_rows

        else:
            raise ValueError("지원하지 않는 삭제 모드입니다.")

        after_count = len(rows)
        new_data = _group_rows_by_date(rows)
        _save_write_log(new_data)

    return {
        "before_count": before_count,
        "removed_count": removed,
        "after_count": after_count,
    }


def _make_summary_message(result: Dict) -> str:
    kept = result["kept"].copy()
    preview = kept[["start_date", "end_date", "similarity_score"]].head(5)
    interval = result.get("interval", DEFAULT_INTERVAL)
    interval_label = SIMILARITY_INTERVAL_LABELS.get(interval, interval)

    rows = []
    for i, row in enumerate(preview.itertuples(index=False), start=1):
        rows.append(
            f"{i}. {row.start_date.strftime('%Y-%m-%d')} ~ {row.end_date.strftime('%Y-%m-%d')} "
            f"(score={row.similarity_score:.3f})"
        )

    top_text = "\n".join(rows) if rows else "없음"

    message = (
        f"유사도 분석 완료\n"
        f"코인: {result['coin_id']}\n"
        f"봉타입: {interval_label}\n"
        f"기준 구간: {result['start_date']} ~ {result['end_date']}\n"
        f"기준 길이: {result['window_len']}\n"
        f"유사 구간(중복 제거 후): {len(kept)}\n"
        f"TOP 5\n{top_text}"
    )
    return message


def _post_to_response_url(response_url: str, text: str, response_type: str = "ephemeral") -> None:
    if not response_url:
        return

    payload = {
        "response_type": response_type,
        "text": text,
    }
    requests.post(response_url, json=payload, timeout=10)


def _start_background_thread(target, payload: Dict) -> None:
    worker = threading.Thread(target=target, args=(payload,), daemon=True)
    worker.start()


def _send_result_to_slack(
    *,
    bot_token: str,
    target_channel_id: str,
    summary_message: str,
    fig,
) -> None:
    slack = SlackNotification(
        bot_token=bot_token,
        channel_id=target_channel_id,
    )
    slack.send_notification_with_image(summary_message, fig)


def _background_run_similarity_from_slash(payload: Dict) -> None:
    response_url = payload.get("response_url", "")
    text = payload.get("text", "")
    command_channel_id = payload.get("channel_id", "")

    bot_token = os.getenv("SLACK_BOT_TOKEN", "").strip()
    if not bot_token:
        _post_to_response_url(response_url, "SLACK_BOT_TOKEN 환경변수가 설정되지 않았습니다.")
        return

    # 기본값은 new_main_merge와 동일하게 unique 채널
    target_channel_id = os.getenv("SLACK_TARGET_CHANNEL_ID", SLACK_CHANNEL_UNIQUE).strip()
    # 옵션 활성화 시 명령 입력 채널로 전송
    if os.getenv("SLACK_USE_COMMAND_CHANNEL", "false").lower() == "true" and command_channel_id:
        target_channel_id = command_channel_id

    try:
        start_date, end_date, coin_id, interval = _parse_slack_text(text)
    except Exception as exc:
        _post_to_response_url(
            response_url,
            (
                f"입력 파싱 실패: {exc}\n"
                "예시: /similarity 2026-06-01 2026-08-01 KRW-BTC\n"
                "예시: /similarity 2026-06-01 00:00:00 2026-08-01 04:00:00 KRW-BTC 4시간봉\n"
                "예시: /similarity start=2026-06-01T00:00:00 end=2026-08-01T00:15:00 coin=KRW-BTC interval=15분봉"
            ),
        )
        return

    try:
        interval_label = SIMILARITY_INTERVAL_LABELS.get(interval, interval)
        _post_to_response_url(
            response_url,
            f"분석 시작: {coin_id} / {interval_label} / {start_date} ~ {end_date}. 완료 후 결과 이미지를 전송합니다.",
        )

        result = run_similarity_tracker(
            start_date=start_date,
            end_date=end_date,
            coin_id=coin_id,
            interval=interval,
        )
        summary = _make_summary_message(result)

        _send_result_to_slack(
            bot_token=bot_token,
            target_channel_id=target_channel_id,
            summary_message=summary,
            fig=result["figure"],
        )

        _post_to_response_url(
            response_url,
            f"완료: 분석 결과를 채널 {target_channel_id}로 전송했습니다.",
        )
    except Exception as exc:
        _post_to_response_url(response_url, f"분석 실패: {exc}")


def _background_run_checkall_from_slash(payload: Dict) -> None:
    response_url = payload.get("response_url", "")
    text = payload.get("text", "")

    bot_token = os.getenv("SLACK_BOT_TOKEN", "").strip()
    if not bot_token:
        _post_to_response_url(response_url, "SLACK_BOT_TOKEN 환경변수가 설정되지 않았습니다.")
        return

    try:
        options = _parse_checkall_text(text)
    except Exception as exc:
        _post_to_response_url(
            response_url,
            f"입력 파싱 실패: {exc}\n예시: /checkall\n예시: /checkall coin=KRW-BTC,KRW-ETH limit=10",
        )
        return

    try:
        _post_to_response_url(
            response_url,
            "전체 코인 점검을 시작합니다. 조건에 맞는 코인은 Slack 메시지와 그래프를 전송합니다.",
        )

        run_merge_once(
            coin_filter=options["coin_filter"],
            limit=options["limit"],
            visualize=bool(options["visualize"]),
        )

        _post_to_response_url(
            response_url,
            "완료: 전체 코인 점검이 끝났습니다. 조건에 맞는 코인은 Slack으로 전송되었습니다.",
        )
    except Exception as exc:
        _post_to_response_url(response_url, f"체크올 실행 실패: {exc}")


def _background_run_write_from_slash(payload: Dict) -> None:
    response_url = payload.get("response_url", "")
    text = payload.get("text", "")

    try:
        parsed = _parse_write_text(text)
        entry = _append_write_record(parsed)
        message = (
            "기록 완료\n"
            f"구분: {entry['side']}\n"
            f"비중: {entry['size']}\n"
            f"가격: {entry['price']}\n"
            f"체결시각: {entry['executed_at']}\n"
            f"저장파일: {WRITE_LOG_FILE}"
        )
        _post_to_response_url(response_url, message)
    except Exception as exc:
        _post_to_response_url(
            response_url,
            f"기록 실패: {exc}\n예시: /write 매수 10000 63403\n예시: /write 매수 10000 63403 2026-08-29 23:00:02",
        )


def _background_run_delete_from_slash(payload: Dict) -> None:
    response_url = payload.get("response_url", "")
    text = payload.get("text", "")

    try:
        delete_args = _parse_delete_text(text)
        result = _delete_write_records(delete_args)

        mode_label = "range" if delete_args["mode"] == "range" else "latest"
        message = (
            "삭제 완료\n"
            f"모드: {mode_label}\n"
            f"삭제 전: {result['before_count']}건\n"
            f"삭제: {result['removed_count']}건\n"
            f"삭제 후: {result['after_count']}건\n"
            f"저장파일: {WRITE_LOG_FILE}"
        )
        _post_to_response_url(response_url, message)
    except Exception as exc:
        _post_to_response_url(
            response_url,
            (
                f"삭제 실패: {exc}\n"
                "예시: /delete r 2026-08-13 00:00:00 2026-08-13 01:00:00\n"
                "예시: /delete l 5"
            ),
        )


# -----------------------------
# FastAPI endpoints
# -----------------------------
@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": APP_NAME}


@app.post("/slack/commands/similarity")
async def slack_similarity_command(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    _verify_slack_signature(request, body)

    # Slack slash command payload is x-www-form-urlencoded.
    # Parse directly to avoid requiring python-multipart.
    form = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    payload = {
        "text": str(form.get("text", [""])[0]),
        "channel_id": str(form.get("channel_id", [""])[0]),
        "response_url": str(form.get("response_url", [""])[0]),
        "user_id": str(form.get("user_id", [""])[0]),
    }

    _start_background_thread(_background_run_similarity_from_slash, payload)

    return JSONResponse(
        {
            "response_type": "ephemeral",
            "text": (
                "요청을 받았습니다. 유사도 분석을 시작합니다.\n"
                "형식: /similarity START END [COIN] [INTERVAL]\n"
                "예시: /similarity 2026-06-01 2026-08-01 KRW-BTC\n"
                "예시: /similarity 2026-06-01 00:00:00 2026-08-01 04:00:00 KRW-BTC 4시간봉\n"
                "예시: /similarity 2026-06-01 00:00:00 2026-06-01 00:15:00 KRW-BTC 15분봉\n"
                "지원 INTERVAL: 일봉, 4시간봉, 15분봉"
            ),
        }
    )


@app.post("/slack/commands/checkall")
async def slack_checkall_command(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    _verify_slack_signature(request, body)

    # Slack slash command payload is x-www-form-urlencoded.
    # Parse directly to avoid requiring python-multipart.
    form = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    payload = {
        "text": str(form.get("text", [""])[0]),
        "channel_id": str(form.get("channel_id", [""])[0]),
        "response_url": str(form.get("response_url", [""])[0]),
        "user_id": str(form.get("user_id", [""])[0]),
    }

    _start_background_thread(_background_run_checkall_from_slash, payload)

    return JSONResponse(
        {
            "response_type": "ephemeral",
            "text": (
                "요청을 받았습니다. 전체 코인 점검을 시작합니다.\n"
                "형식: /checkall\n"
                "옵션 예시: /checkall coin=KRW-BTC,KRW-ETH limit=10 visualize=false"
            ),
        }
    )


@app.post("/slack/commands/write")
async def slack_write_command(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    _verify_slack_signature(request, body)

    form = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    payload = {
        "text": str(form.get("text", [""])[0]),
        "channel_id": str(form.get("channel_id", [""])[0]),
        "response_url": str(form.get("response_url", [""])[0]),
        "user_id": str(form.get("user_id", [""])[0]),
    }

    _start_background_thread(_background_run_write_from_slash, payload)

    return JSONResponse(
        {
            "response_type": "ephemeral",
            "text": (
                "요청을 받았습니다. 매매 기록을 저장합니다.\n"
                "형식: /write 매수|매도 비중 가격 [YYYY-MM-DD HH:MM:SS]\n"
                "예시: /write 매수 10000 63403\n"
                "예시: /write 매도 8000 64000 2026-08-29 23:00:02"
            ),
        }
    )


@app.post("/slack/commands/wirte")
async def slack_wirte_command(request: Request, background_tasks: BackgroundTasks):
    # 오타 커맨드 호환: /wirte -> /write와 동일 처리
    return await slack_write_command(request, background_tasks)


@app.post("/slack/commands/delete")
async def slack_delete_command(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    _verify_slack_signature(request, body)

    form = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    payload = {
        "text": str(form.get("text", [""])[0]),
        "channel_id": str(form.get("channel_id", [""])[0]),
        "response_url": str(form.get("response_url", [""])[0]),
        "user_id": str(form.get("user_id", [""])[0]),
    }

    _start_background_thread(_background_run_delete_from_slash, payload)

    return JSONResponse(
        {
            "response_type": "ephemeral",
            "text": (
                "요청을 받았습니다. 매매 기록 삭제를 수행합니다.\n"
                "형식1: /delete r YYYY-MM-DD HH:MM:SS YYYY-MM-DD HH:MM:SS\n"
                "형식2: /delete l 개수\n"
                "예시: /delete r 2026-08-13 00:00:00 2026-08-13 01:00:00\n"
                "예시: /delete l 5"
            ),
        }
    )


@app.post("/similarity/run")
def similarity_run(req: SimilarityRunRequest):
    result = run_similarity_tracker(
        start_date=req.start_date,
        end_date=req.end_date,
        coin_id=req.coin_id,
        interval=req.interval,
        load_count=req.load_count,
        top_n=req.top_n,
        overlap_threshold=req.overlap_threshold,
        window_ratio=req.window_ratio,
    )

    summary_message = _make_summary_message(result)

    if req.send_to_slack:
        bot_token = os.getenv("SLACK_BOT_TOKEN", "").strip()
        if not bot_token:
            raise HTTPException(status_code=400, detail="SLACK_BOT_TOKEN 환경변수가 필요합니다.")

        target_channel_id = (req.channel_id or os.getenv("SLACK_TARGET_CHANNEL_ID") or SLACK_CHANNEL_UNIQUE).strip()
        _send_result_to_slack(
            bot_token=bot_token,
            target_channel_id=target_channel_id,
            summary_message=summary_message,
            fig=result["figure"],
        )

    response = {
        "ok": True,
        "summary": summary_message,
        "coin_id": result["coin_id"],
        "interval": result["interval"],
        "interval_label": SIMILARITY_INTERVAL_LABELS.get(result["interval"], result["interval"]),
        "start_date": result["start_date"],
        "end_date": result["end_date"],
        "window_len": result["window_len"],
        "kept_count": len(result["kept"]),
        "kept_top5": [
            {
                "start_date": row.start_date.strftime("%Y-%m-%d"),
                "end_date": row.end_date.strftime("%Y-%m-%d"),
                "similarity_score": float(row.similarity_score),
            }
            for row in result["kept"][["start_date", "end_date", "similarity_score"]]
            .head(5)
            .itertuples(index=False)
        ],
    }

    if req.include_image_base64:
        import plotly.io as pio

        image_bytes = pio.to_image(result["figure"], format="png", width=1400, height=900)
        response["image_base64"] = base64.b64encode(image_bytes).decode("ascii")

    return JSONResponse(response)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("slack_similarity_api:app", host="0.0.0.0", port=8080, reload=False)
