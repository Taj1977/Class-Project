"""
analytics/engine.py

UC3: Enable Data Aggregation, Analytics and Data Mining.

Two simple, defensible analytics functions on top of the timeseries
collection:
- compute_trend: min/max/avg close price + percentage change
- forecast_next_price: linear regression over recent closes to predict
  the next data point (intentionally simple - the spec asks for "simple
  forecasts", not a production model)
"""
import pandas as pd
from sklearn.linear_model import LinearRegression
import numpy as np
from app.db.connection import get_db


def _load_series(asset_id: str, data_source_id: str) -> pd.DataFrame:
    db = get_db()
    points = list(
        db.timeseries.find(
            {"assetId": asset_id, "dataSourceId": data_source_id, "isDeleted": False}
        ).sort("timestamp", 1)
    )
    if not points:
        return pd.DataFrame()
    df = pd.DataFrame(points)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def compute_trend(asset_id: str, data_source_id: str):
    df = _load_series(asset_id, data_source_id)
    if df.empty or "close" not in df.columns or len(df) < 2:
        return None

    first_close = df["close"].iloc[0]
    last_close = df["close"].iloc[-1]
    pct_change = ((last_close - first_close) / first_close) * 100 if first_close else None

    return {
        "assetId": asset_id,
        "dataSourceId": data_source_id,
        "periodStart": df["timestamp"].iloc[0].isoformat(),
        "periodEnd": df["timestamp"].iloc[-1].isoformat(),
        "min": round(float(df["close"].min()), 6),
        "max": round(float(df["close"].max()), 6),
        "avg": round(float(df["close"].mean()), 6),
        "pctChange": round(float(pct_change), 4) if pct_change is not None else None,
        "direction": "up" if pct_change and pct_change > 0 else ("down" if pct_change and pct_change < 0 else "flat"),
    }


def forecast_next_price(asset_id: str, data_source_id: str):
    df = _load_series(asset_id, data_source_id)
    if df.empty or "close" not in df.columns or len(df) < 5:
        return None  # not enough history for a meaningful fit

    df = df.reset_index(drop=True)
    X = np.arange(len(df)).reshape(-1, 1)
    y = df["close"].values

    model = LinearRegression()
    model.fit(X, y)
    next_x = np.array([[len(df)]])
    predicted = model.predict(next_x)[0]

    return {
        "assetId": asset_id,
        "dataSourceId": data_source_id,
        "method": "linear_regression_on_recent_closes",
        "pointsUsed": len(df),
        "lastClose": round(float(y[-1]), 6),
        "predictedNextClose": round(float(predicted), 6),
        "note": "Simple linear trend forecast, not investment advice.",
    }
