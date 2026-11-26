"""Paso de OHLCV entre Yahoo Finance, CCXT y el analista técnico."""

from typing import Optional

import pandas as pd

OHLCV_COLUMNS = ("Open", "High", "Low", "Close", "Volume")


def _drop_timezone(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
        df = df.copy()
        df.index = df.index.tz_localize(None)
    return df


def ohlcv_to_frame(ohlcv) -> pd.DataFrame:
    """Velas CCXT [timestamp_ms, open, high, low, close, volume] → DataFrame diario."""
    frame = pd.DataFrame(ohlcv, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    frame = frame.set_index("timestamp")
    frame.index = frame.index.tz_localize(None)
    for column in OHLCV_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame[list(OHLCV_COLUMNS)].dropna(subset=["Close"]).sort_index()


def frame_to_history(frame: Optional[pd.DataFrame]) -> Optional[dict]:
    if frame is None or frame.empty:
        return None
    cleaned = _drop_timezone(frame.copy())
    keep = [column for column in OHLCV_COLUMNS if column in cleaned.columns]
    if "Close" not in keep:
        return None
    return cleaned[keep].to_dict()


def history_to_frame(history) -> Optional[pd.DataFrame]:
    if not history or not isinstance(history, dict):
        return None
    frame = pd.DataFrame(history)
    if frame.empty or "Close" not in frame.columns:
        return None
    if not isinstance(frame.index, pd.DatetimeIndex):
        frame.index = pd.to_datetime(frame.index, errors="coerce")
    frame = frame[~frame.index.isna()].sort_index()
    frame = _drop_timezone(frame)
    for column in OHLCV_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["Close"])
    if frame.empty:
        return None
    return frame
