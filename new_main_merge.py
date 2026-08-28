import argparse
import datetime
import math
import os

import pandas as pd
import plotly.graph_objects as go
import pyupbit
from plotly.subplots import make_subplots

from core.upbit import Upbit
from loader.upbit_realtimedata_loader import UpbitRealtimeDataLoader
from notification.slack_notification import SlackNotification
from notification.slack_send_history import load_slack_send_history
from notification.slack_send_history import save_slack_send_history
from notification.slack_send_history import should_send_slack_message
from notification.slack_send_history import update_slack_send_history
from processing.filtering_high_points import GetHighPoints
from processing.filtering_low_points import GetLowPoints
from processing.get_trend_section import GetTrendSections
from processing.high_point_scoring import HighPointScoringProcessing
from processing.low_point_scoring import LowPointScoringProcessing
from processing.ma_200_rising import MA200RisingProcessing
from processing.moving_average import MovingAverageProcessing
from processing.rsi import RSIProcessing
from visualization.basic_price_rsi_visualization import BasicPriceWithRsiVisualization

from common.common import add_vline_to_main_figure
from common.common import add_vrect_to_main_figure
from common.common import find_overlapping_intervals


# 병합 출력 기본 설정
DEFAULT_LOAD_COUNT = 400
DEFAULT_THRESHOLD = 0.85
DEFAULT_INDECREASING_COUNT_SET = [3, 1]
DEFAULT_SKIP_VISUALIZATION_FOR_ALREADY_SENT_HISTORY = True

# 일봉 설정
DAILY_INTERVAL_BASE = "day1"
DAILY_SCORE_BAND_LIST = [100]

# 4시간봉 설정
H4_INTERVAL_BASE = "minute240"
H4_SCORE_BAND_LIST = [30]
MA_200_RISING_MIN_CONSECUTIVE_TRUE = 2
ALIGNED_IN_ORDER_WINDOW_SIZE = 8

# Slack 채널
SLACK_CHANNEL_DEFAULT = "C0APBAF5DPW"
SLACK_CHANNEL_NEW_INTERVAL = "C0ASU4HRLSG"
SLACK_CHANNEL_UNIQUE = "C0ASM57RV9T"


def create_slack_client(channel_id):
    try:
        client = SlackNotification(
            bot_token=os.getenv("SLACK_BOT_TOKEN"),
            channel_id=channel_id,
        )
        print(f"Slack 연결 성공: {channel_id}")
        return client
    except Exception as exc:
        print(f"Slack 연결 실패({channel_id}): {str(exc)}")
        return None


def calc_weekly_ma20_angle_info(upbit_daily_data):
    daily_for_weekly = upbit_daily_data[["timestamp_kst", "open", "high", "low", "close"]].copy()
    daily_for_weekly["timestamp_kst"] = pd.to_datetime(daily_for_weekly["timestamp_kst"])
    daily_for_weekly = daily_for_weekly.set_index("timestamp_kst")

    # W-SUN: 월요일~일요일 단위 집계 (일요일 마감)
    weekly_resampled = daily_for_weekly.resample("W-SUN").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
    ).dropna(subset=["close"])
    weekly_resampled["ma_20"] = weekly_resampled["close"].rolling(window=20, min_periods=1).mean()
    weekly_df = weekly_resampled.reset_index()

    if len(weekly_df) < 6:
        return {
            "weekly_df": weekly_df,
            "weekly_ma20_current": None,
            "weekly_ma20_5w_ago": None,
            "weekly_ma20_3w_ago": None,
            "weekly_angle_5w": None,
            "weekly_angle_3w": None,
            "above_ma20_str": "N/A",
        }

    weekly_ma20_current = weekly_df.iloc[-1]["ma_20"]
    weekly_ma20_5w_ago = weekly_df.iloc[-6]["ma_20"]
    weekly_ma20_3w_ago = weekly_df.iloc[-4]["ma_20"]

    weekly_close_current = weekly_df.iloc[-1]["close"]
    if not pd.isna(weekly_ma20_current):
        is_above_weekly_ma20 = weekly_close_current > weekly_ma20_current
        above_ma20_str = "Y" if is_above_weekly_ma20 else "N"
    else:
        above_ma20_str = "N/A"

    def _weekly_angle(past_val, weeks_back):
        if pd.isna(past_val) or past_val == 0:
            return None
        return math.degrees(math.atan((weekly_ma20_current - past_val) / past_val / weeks_back))

    weekly_angle_5w = _weekly_angle(weekly_ma20_5w_ago, 5)
    weekly_angle_3w = _weekly_angle(weekly_ma20_3w_ago, 3)

    return {
        "weekly_df": weekly_df,
        "weekly_ma20_current": weekly_ma20_current,
        "weekly_ma20_5w_ago": weekly_ma20_5w_ago,
        "weekly_ma20_3w_ago": weekly_ma20_3w_ago,
        "weekly_angle_5w": weekly_angle_5w,
        "weekly_angle_3w": weekly_angle_3w,
        "above_ma20_str": above_ma20_str,
    }


def run_once(coin_filter=None, limit=None, visualize=False):
    skip_visualization_for_already_sent_history = DEFAULT_SKIP_VISUALIZATION_FOR_ALREADY_SENT_HISTORY

    slack_default = create_slack_client(SLACK_CHANNEL_DEFAULT)
    slack_new_interval = create_slack_client(SLACK_CHANNEL_NEW_INTERVAL)
    slack_unique = create_slack_client(SLACK_CHANNEL_UNIQUE)
    slack_enabled = any([slack_default, slack_new_interval, slack_unique])

    slack_send_history = load_slack_send_history()

    print("merge start")
    tickers = pyupbit.get_tickers("KRW")
    total_tickers = len(tickers)

    processed_count = 0
    for idx, one_coin in enumerate(tickers):
        if coin_filter and one_coin not in coin_filter:
            continue

        if limit is not None and processed_count >= limit:
            break

        processed_count += 1
        print(f"{one_coin} 시작")

        try:
            # 1) 일봉 데이터 + 빨간 라인 후보 계산
            upbit_daily = Upbit()
            upbit_daily.set_loader(
                UpbitRealtimeDataLoader(
                    one_coin,
                    DAILY_INTERVAL_BASE,
                    DEFAULT_LOAD_COUNT,
                    current_index=idx + 1,
                    total_count=total_tickers,
                )
            )
            upbit_daily.load()

            daily_indicator_list = [
                MovingAverageProcessing(),
                RSIProcessing(),
                HighPointScoringProcessing(DAILY_SCORE_BAND_LIST),
                LowPointScoringProcessing(DAILY_SCORE_BAND_LIST),
                MA200RisingProcessing(),
            ]
            upbit_daily.add_sub_indicator(daily_indicator_list)

            upbit_daily.generate_high_low_data(
                GetHighPoints(upbit_daily.data.loc[upbit_daily.data["high_score"] != 0], "high_score", DEFAULT_THRESHOLD),
                GetLowPoints(upbit_daily.data.loc[upbit_daily.data["low_score"] != 0], "low_score", DEFAULT_THRESHOLD),
            )

            low_decline_then_rise_points = []
            if len(upbit_daily.low_point_df) > 3:
                low_values = upbit_daily.low_point_df["low"].values
                low_indices = upbit_daily.low_point_df.index.tolist()

                for i in range(len(low_values) - 3):
                    if low_values[i] > low_values[i + 1] > low_values[i + 2] and low_values[i + 2] < low_values[i + 3]:
                        low_decline_then_rise_points.append(low_indices[i + 3])

            daily_rise_dates = set()
            if len(low_decline_then_rise_points) > 0:
                for point_idx in low_decline_then_rise_points:
                    ts = pd.to_datetime(upbit_daily.low_point_df.loc[point_idx, "timestamp_kst"])
                    daily_rise_dates.add(ts.date())

            # 2) 4시간봉 데이터 + 진한 노란색 구간 계산
            upbit_h4 = Upbit()
            upbit_h4.set_loader(
                UpbitRealtimeDataLoader(
                    one_coin,
                    H4_INTERVAL_BASE,
                    DEFAULT_LOAD_COUNT,
                    current_index=idx + 1,
                    total_count=total_tickers,
                )
            )
            upbit_h4.load()

            h4_indicator_list = [
                MovingAverageProcessing(),
                RSIProcessing(),
                HighPointScoringProcessing(H4_SCORE_BAND_LIST),
                LowPointScoringProcessing(H4_SCORE_BAND_LIST),
                MA200RisingProcessing(),
            ]
            upbit_h4.add_sub_indicator(h4_indicator_list)

            upbit_h4.generate_high_low_data(
                GetHighPoints(upbit_h4.data.loc[upbit_h4.data["high_score"] != 0], "high_score", DEFAULT_THRESHOLD),
                GetLowPoints(upbit_h4.data.loc[upbit_h4.data["low_score"] != 0], "low_score", DEFAULT_THRESHOLD),
            )

            upbit_h4.set_processor(GetTrendSections("high", "increasing", DEFAULT_INDECREASING_COUNT_SET[0], DEFAULT_INDECREASING_COUNT_SET[1]))
            high_point_increasing_trend_section_upbit = upbit_h4.get_key_points(upbit_h4.high_point_df)

            upbit_h4.set_processor(GetTrendSections("low", "increasing", DEFAULT_INDECREASING_COUNT_SET[0], DEFAULT_INDECREASING_COUNT_SET[1]))
            low_point_increasing_trend_section_upbit = upbit_h4.get_key_points(upbit_h4.low_point_df)

            high_point_group_start_end_upbit = []
            for sec in high_point_increasing_trend_section_upbit:
                high_point_group_start_end_upbit.append([sec[0], sec[-1]])

            low_point_group_start_end_upbit = []
            for sec in low_point_increasing_trend_section_upbit:
                low_point_group_start_end_upbit.append([sec[0], sec[-1]])

            _, _ = find_overlapping_intervals(
                high_point_group_start_end_upbit,
                low_point_group_start_end_upbit,
            )

            dark_yellow_group_start_end_upbit = []
            if "aligned_in_order" in upbit_h4.data.columns and "ma_200_rising" in upbit_h4.data.columns:
                ma_rising_series = upbit_h4.data["ma_200_rising"].fillna(False).astype(bool)
                ma_rising_two_consecutive = ma_rising_series
                for shift_step in range(1, MA_200_RISING_MIN_CONSECUTIVE_TRUE):
                    ma_rising_two_consecutive = ma_rising_two_consecutive & ma_rising_series.shift(shift_step, fill_value=False)

                aligned_series = upbit_h4.data["aligned_in_order"].fillna(False).astype(bool)
                aligned_all_true_in_8 = aligned_series.rolling(
                    window=ALIGNED_IN_ORDER_WINDOW_SIZE,
                    min_periods=ALIGNED_IN_ORDER_WINDOW_SIZE,
                ).sum().eq(ALIGNED_IN_ORDER_WINDOW_SIZE)

                dark_yellow_mask = ma_rising_two_consecutive & aligned_all_true_in_8
                if dark_yellow_mask.any():
                    dark_yellow_group_id = (dark_yellow_mask != dark_yellow_mask.shift(fill_value=False)).cumsum()
                    for _, one_group_df in upbit_h4.data.loc[dark_yellow_mask].groupby(dark_yellow_group_id[dark_yellow_mask]):
                        dark_yellow_group_start_end_upbit.append([one_group_df.index[0], one_group_df.index[-1]])

            h4_line_index_list = []
            if len(daily_rise_dates) > 0:
                h4_dates = pd.to_datetime(upbit_h4.data["timestamp_kst"]).dt.date
                for one_date in sorted(daily_rise_dates):
                    matched_idx = upbit_h4.data.index[h4_dates == one_date]
                    if len(matched_idx) > 0:
                        h4_line_index_list.append(matched_idx[0])

            has_dark_yellow_after_daily_rise = False
            if len(h4_line_index_list) > 0 and len(dark_yellow_group_start_end_upbit) > 0:
                latest_daily_rise_idx = max(h4_line_index_list)
                has_dark_yellow_after_daily_rise = any(
                    start_idx > latest_daily_rise_idx
                    for start_idx, _ in dark_yellow_group_start_end_upbit
                )

            if not has_dark_yellow_after_daily_rise:
                print(f"{one_coin} 스킵: 일봉 빨간 라인 이후 진한 노란색 정배열 구간 없음")
                continue

            should_visualize = visualize
            should_send = False
            current_lengths = []
            previous_lengths = []

            if slack_enabled:
                should_send, current_lengths, previous_lengths = should_send_slack_message(
                    slack_send_history,
                    one_coin,
                    dark_yellow_group_start_end_upbit,
                )
                should_visualize = should_send or not skip_visualization_for_already_sent_history or visualize

                if not should_send:
                    print(
                        f"{one_coin} Slack 전송 생략: 이미 동일한 진한 노란색 구간 이력 전송됨 "
                        f"(이전/현재: {previous_lengths}/{current_lengths})"
                    )

            if not should_visualize and not should_send:
                print(f"{one_coin} 그래프 출력 생략: 이미 동일한 진한 노란색 구간 이력 전송됨")

            # 3) 주봉 MA20 각도 계산
            weekly_info = calc_weekly_ma20_angle_info(upbit_daily.data)
            weekly_df = weekly_info["weekly_df"]

            weekly_angle_5w = weekly_info["weekly_angle_5w"]
            weekly_angle_3w = weekly_info["weekly_angle_3w"]
            above_ma20_str = weekly_info["above_ma20_str"]
            weekly_ma20_current = weekly_info["weekly_ma20_current"]
            weekly_ma20_5w_ago = weekly_info["weekly_ma20_5w_ago"]
            weekly_ma20_3w_ago = weekly_info["weekly_ma20_3w_ago"]

            angle_5w_str = f"{weekly_angle_5w:.2f}°" if weekly_angle_5w is not None else "N/A"
            angle_3w_str = f"{weekly_angle_3w:.2f}°" if weekly_angle_3w is not None else "N/A"
            print(f"{one_coin} 주봉 MA20 각도 - 5주전: {angle_5w_str}, 3주전: {angle_3w_str}, 20선 위: {above_ma20_str}")

            draw_daily = BasicPriceWithRsiVisualization()
            draw_daily.set_data(upbit_daily.data, upbit_daily.high_point_df, upbit_daily.low_point_df)
            draw_daily.make_figure(title=f"{one_coin} - DAY1 ({idx + 1}/{total_tickers})")
            figure_daily = draw_daily.get_figure()

            if len(low_decline_then_rise_points) > 0:
                add_vline_to_main_figure(
                    figure_daily,
                    upbit_daily.low_point_df,
                    "red",
                    low_decline_then_rise_points,
                    label_text="일봉 저점 상승 시작",
                )

            figure_daily.add_annotation(
                text=(
                    f"주봉 5주전 각도 : {angle_5w_str}<br>"
                    f"주봉 3주전 각도 : {angle_3w_str}<br>"
                    f"주봉 20선 위 : {above_ma20_str}"
                ),
                xref="paper",
                yref="paper",
                x=0.01,
                y=0.99,
                xanchor="left",
                yanchor="top",
                showarrow=False,
                font=dict(size=13, color="black"),
                bgcolor="rgba(255, 255, 255, 0.75)",
                bordercolor="#888888",
                borderwidth=1,
            )

            # 4) 주봉 MA20 각도 검토용 그래프
            fig_weekly = None
            if len(weekly_df) >= 10:
                weekly_view = weekly_df.iloc[-10:].copy()
                ts_current = weekly_df.iloc[-1]["timestamp_kst"]
                ts_5w_ago = weekly_df.iloc[-6]["timestamp_kst"]
                ts_3w_ago = weekly_df.iloc[-4]["timestamp_kst"]

                fig_weekly = make_subplots(rows=1, cols=1)
                fig_weekly.update_layout(
                    title=f"{one_coin} - WEEK / MA20 각도 검토 (최근 10주)",
                    xaxis_title="Date",
                    yaxis_title="Price",
                    xaxis_rangeslider_visible=False,
                    width=1000,
                    height=500,
                )

                fig_weekly.add_trace(go.Candlestick(
                    x=list(weekly_view["timestamp_kst"]),
                    open=list(weekly_view["open"]),
                    high=list(weekly_view["high"]),
                    low=list(weekly_view["low"]),
                    close=list(weekly_view["close"]),
                    name="주봉 캔들",
                ))

                fig_weekly.add_trace(go.Scatter(
                    x=weekly_view["timestamp_kst"],
                    y=weekly_view["ma_20"],
                    mode="lines",
                    name="MA20",
                    line=dict(color="blue", width=2),
                ))

                if weekly_ma20_5w_ago is not None and not pd.isna(weekly_ma20_5w_ago):
                    fig_weekly.add_trace(go.Scatter(
                        x=[ts_5w_ago, ts_current],
                        y=[weekly_ma20_5w_ago, weekly_ma20_current],
                        mode="lines+markers+text",
                        name=f"5주 각도선 ({angle_5w_str})",
                        line=dict(color="orange", width=2, dash="dash"),
                        marker=dict(size=8, color="orange"),
                        text=[f"MA20 (5주전)<br>{weekly_ma20_5w_ago:,.0f}", f"현재<br>{weekly_ma20_current:,.0f}"],
                        textposition=["bottom center", "top center"],
                    ))

                if weekly_ma20_3w_ago is not None and not pd.isna(weekly_ma20_3w_ago):
                    fig_weekly.add_trace(go.Scatter(
                        x=[ts_3w_ago, ts_current],
                        y=[weekly_ma20_3w_ago, weekly_ma20_current],
                        mode="lines+markers+text",
                        name=f"3주 각도선 ({angle_3w_str})",
                        line=dict(color="green", width=2, dash="dash"),
                        marker=dict(size=8, color="green"),
                        text=[f"MA20 (3주전)<br>{weekly_ma20_3w_ago:,.0f}", ""],
                        textposition=["bottom center", "top center"],
                    ))

            draw_h4 = BasicPriceWithRsiVisualization()
            draw_h4.set_data(upbit_h4.data, upbit_h4.high_point_df, upbit_h4.low_point_df)
            draw_h4.make_figure(title=f"{one_coin} - 4H")
            figure_h4 = draw_h4.get_figure()

            if len(dark_yellow_group_start_end_upbit) > 0:
                add_vrect_to_main_figure(
                    figure_h4,
                    upbit_h4.data,
                    "#b8860b",
                    dark_yellow_group_start_end_upbit,
                    show_interval_label=True,
                    label_prefix="번 구간",
                    start_label_index=1,
                    show_interval_length=True,
                    interval_length_separator=" : ",
                )

            if len(h4_line_index_list) > 0:
                add_vline_to_main_figure(
                    figure_h4,
                    upbit_h4.data,
                    "red",
                    h4_line_index_list,
                    label_text="일봉 저점 상승 시작",
                )

            # Slack 전송
            if slack_enabled and should_send:
                try:
                    msg_daily = (
                        f"🚀 {one_coin} - 일봉 조건 충족 차트\n"
                        f"진한 노란색 구간 길이: {current_lengths}\n"
                        f"주봉 MA20 각도 (5주전: {angle_5w_str} / 3주전: {angle_3w_str})\n"
                        f"주봉 20선 위 : {above_ma20_str}"
                    )
                    msg_h4 = f"🚀 {one_coin} - 4시간봉 조건 충족 차트\n진한 노란색 구간 길이: {current_lengths}"
                    msg_weekly = (
                        f"🚀 {one_coin} - 주봉 MA20 각도 검토 차트\n"
                        f"5주전: {angle_5w_str} / 3주전: {angle_3w_str} / 20선 위: {above_ma20_str}"
                    )

                    interval_changed = should_send
                    send_to_new_interval = False
                    send_to_default = False
                    send_to_unique = False

                    now = datetime.datetime.now()
                    today_9am = now.replace(hour=9, minute=0, second=0, microsecond=0)

                    if interval_changed:
                        send_to_new_interval = True
                    else:
                        last_sent_at = slack_send_history.get(one_coin, {}).get("last_sent_at")
                        sent_after_9am = False
                        sent_before_9am = False
                        if last_sent_at:
                            last_sent_dt = pd.to_datetime(last_sent_at)
                            if last_sent_dt.date() == now.date():
                                if last_sent_dt >= today_9am:
                                    sent_after_9am = True
                                else:
                                    sent_before_9am = True
                        if sent_after_9am:
                            pass
                        elif sent_before_9am and now >= today_9am:
                            send_to_default = True
                        else:
                            send_to_default = True

                    if above_ma20_str == "Y":
                        send_to_unique = True

                    if send_to_new_interval and slack_new_interval:
                        slack_new_interval.send_notification_with_image(msg_daily, figure_daily)
                        slack_new_interval.send_notification_with_image(msg_h4, figure_h4)
                        print(f"{one_coin} Slack 전송: new_interval")

                    if send_to_default and slack_default:
                        slack_default.send_notification_with_image(msg_daily, figure_daily)
                        slack_default.send_notification_with_image(msg_h4, figure_h4)
                        print(f"{one_coin} Slack 전송: upbitnoti")

                    if send_to_unique and slack_unique:
                        slack_unique.send_notification_with_image(msg_daily, figure_daily)
                        slack_unique.send_notification_with_image(msg_h4, figure_h4)
                        if fig_weekly is not None:
                            slack_unique.send_notification_with_image(msg_weekly, fig_weekly)
                        print(f"{one_coin} Slack 전송: unique")

                    slack_send_history = update_slack_send_history(
                        slack_send_history,
                        one_coin,
                        dark_yellow_group_start_end_upbit,
                        is_above_weekly_ma20=above_ma20_str,
                    )
                    save_slack_send_history(slack_send_history)
                    print(f"{one_coin} Slack 그래프 전송 완료")
                except Exception as exc:
                    print(f"{one_coin} Slack 그래프 전송 실패: {str(exc)}")

            if visualize:
                print(f"{one_coin} 일봉 출력")
                draw_daily.visualize()

                if fig_weekly is not None:
                    print(f"{one_coin} 주봉 MA20 각도 검토 출력")
                    fig_weekly.show()

                print(f"{one_coin} 4시간봉 출력")
                draw_h4.visualize()

        except Exception as exc:
            print(f"{one_coin} 처리 중 오류: {str(exc)}")


def parse_coin_filter(raw_coin_filter):
    if raw_coin_filter is None or raw_coin_filter.strip() == "":
        return None

    coin_filter = [item.strip() for item in raw_coin_filter.split(",") if item.strip()]
    return coin_filter if coin_filter else None


def main():
    parser = argparse.ArgumentParser(description="Merged daily/h4 scan and Slack notifier")
    parser.add_argument(
        "--coin-filter",
        type=str,
        default="",
        help="쉼표로 구분한 코인 필터 예: KRW-BTC,KRW-ETH",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="처리할 코인 개수 제한",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="차트 창 출력 여부 (자동 실행 환경에서는 비권장)",
    )
    args = parser.parse_args()

    coin_filter = parse_coin_filter(args.coin_filter)
    run_once(
        coin_filter=coin_filter,
        limit=args.limit,
        visualize=args.visualize,
    )


if __name__ == "__main__":
    main()
