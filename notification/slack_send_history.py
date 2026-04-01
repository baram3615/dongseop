import json
import inspect
from datetime import datetime
from pathlib import Path
import pandas as pd


HISTORY_FILE_PATH = Path(__file__).resolve().parents[1] / "slack_send_history.json"


def _to_python_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _normalize_timestamp(value):
    if value is None:
        return None

    timestamp = pd.to_datetime(value)
    if pd.isna(timestamp):
        return None
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def _find_timestamp_series(timestamp_series=None):
    if timestamp_series is not None:
        return timestamp_series

    for frame_info in inspect.stack()[1:]:
        local_vars = frame_info.frame.f_locals

        if "timestamp_series" in local_vars and local_vars["timestamp_series"] is not None:
            return local_vars["timestamp_series"]

        upbit_h4 = local_vars.get("upbit_h4")
        if upbit_h4 is not None and hasattr(upbit_h4, "data"):
            data = getattr(upbit_h4, "data", None)
            if data is not None and "timestamp_kst" in data:
                return data["timestamp_kst"]

    return None


def get_dark_yellow_intervals(dark_yellow_group_start_end_list: list, timestamp_series=None) -> list:
    timestamp_series = _find_timestamp_series(timestamp_series)
    intervals = []
    for interval_index, (start_idx, end_idx) in enumerate(dark_yellow_group_start_end_list, start=1):
        normalized_start_idx = _to_python_int(start_idx)
        normalized_end_idx = _to_python_int(end_idx)
        start_timestamp = None
        end_timestamp = None

        if timestamp_series is not None:
            start_timestamp = _normalize_timestamp(timestamp_series.loc[start_idx])
            end_timestamp = _normalize_timestamp(timestamp_series.loc[end_idx])

        intervals.append(
            {
                "interval_index": interval_index,
                "start_timestamp_kst": start_timestamp,
                "end_timestamp_kst": end_timestamp,
                "length": _to_python_int(normalized_end_idx - normalized_start_idx + 1),
            }
        )
    return intervals


def load_slack_send_history(history_file_path: Path = HISTORY_FILE_PATH) -> dict:
    if not history_file_path.exists():
        return {}

    try:
        with history_file_path.open("r", encoding="utf-8") as file_obj:
            return json.load(file_obj)
    except (json.JSONDecodeError, OSError):
        return {}


def get_dark_yellow_lengths(dark_yellow_group_start_end_list: list, timestamp_series=None) -> list:
    return [one_interval["length"] for one_interval in get_dark_yellow_intervals(dark_yellow_group_start_end_list, timestamp_series)]


def should_send_slack_message(history: dict, coin_name: str, dark_yellow_group_start_end_list: list, timestamp_series=None) -> tuple[bool, str, list]:
    current_intervals = get_dark_yellow_intervals(dark_yellow_group_start_end_list, timestamp_series)
    current_lengths = [one_interval["length"] for one_interval in current_intervals]

    previous_entry = history.get(coin_name, {})
    previous_intervals = previous_entry.get("dark_yellow_intervals")
    previous_lengths = previous_entry.get("dark_yellow_lengths", [])

    if previous_intervals is None:
        previous_intervals = [
            {
                "interval_index": interval_index,
                "start_timestamp_kst": None,
                "end_timestamp_kst": None,
                "length": _to_python_int(length),
            }
            for interval_index, length in enumerate(previous_lengths, start=1)
        ]

    return current_intervals != previous_intervals, format_dark_yellow_intervals_text(current_intervals), previous_lengths


def update_slack_send_history(history: dict, coin_name: str, dark_yellow_group_start_end_list: list, timestamp_series=None) -> dict:
    dark_yellow_intervals = get_dark_yellow_intervals(dark_yellow_group_start_end_list, timestamp_series)
    history[coin_name] = {
        "dark_yellow_intervals": dark_yellow_intervals,
        "dark_yellow_lengths": [one_interval["length"] for one_interval in dark_yellow_intervals],
        "last_sent_at": datetime.now().isoformat(timespec="seconds"),
    }
    return history


def format_dark_yellow_intervals_text(dark_yellow_intervals: list) -> str:
    if not dark_yellow_intervals:
        return "진한 노란색 구간 없음"

    lines = []
    for one_interval in dark_yellow_intervals:
        lines.append(
            f"{one_interval['interval_index']}번 구간 : {one_interval['length']} "
            f"({one_interval['start_timestamp_kst']} ~ {one_interval['end_timestamp_kst']})"
        )
    return "\n".join(lines)


def save_slack_send_history(history: dict, history_file_path: Path = HISTORY_FILE_PATH):
    history_file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_file_path = history_file_path.with_suffix(".json.tmp")
    with temp_file_path.open("w", encoding="utf-8") as file_obj:
        json.dump(history, file_obj, ensure_ascii=False, indent=2)
    temp_file_path.replace(history_file_path)