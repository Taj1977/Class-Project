"""
api/main.py

UC2: Expose Financial Data for Consumption via RESTful API.

Implements the 5 required queries:
Q1 - GET /assets                -> limited info on all assets
Q2 - GET /assets/{assetId}      -> full detail of one asset
Q3 - GET /sources               -> limited info on all data sources
Q4 - GET /sources/{dataSourceId}-> full detail of one source
Q5 - GET /timeseries            -> time series for an asset + source

Also exposes a couple of analytics endpoints (UC3) and a temporal
point-in-time query, since the spec requires history to be queryable.

Run: uvicorn app.api.main:app --reload
Docs: http://localhost:8000/docs
"""
from fastapi import FastAPI, HTTPException, Query
from typing import Optional
from app.db.connection import get_db
from app.db.temporal_repo import get_asset_as_of, list_current_assets
from app.analytics.engine import compute_trend, forecast_next_price

app = FastAPI(title="Acme Ltd - Financial Data Warehouse API", version="0.1.0")


def serialize(doc):
    """Mongo docs contain ObjectId, which isn't JSON serializable by default."""
    if doc is None:
        return None
    doc = dict(doc)
    doc["_id"] = str(doc["_id"])
    return doc


@app.get("/assets")
def list_assets(instrumentClass: Optional[str] = None):
    """Q1: limited info (assetId, symbol, class) about all current assets."""
    assets = list_current_assets(instrument_class=instrumentClass)
    return [
        {"assetId": a["assetId"], "symbol": a["symbol"], "instrumentClass": a["instrumentClass"]}
        for a in assets
    ]


@app.get("/assets/{asset_id}")
def get_asset(asset_id: str, asOf: Optional[str] = None):
    """
    Q2: full details of an asset by id.
    If `asOf` (ISO timestamp) is given, returns the historical version
    valid at that point in time instead of the current one.
    """
    db = get_db()
    if asOf:
        doc = get_asset_as_of(asset_id, asOf)
    else:
        doc = db.assets.find_one({"assetId": asset_id, "validTo": None})

    if not doc or doc.get("isDeleted"):
        raise HTTPException(status_code=404, detail="Asset not found")
    return serialize(doc)


@app.get("/sources")
def list_sources():
    """Q3: limited info about all registered data sources."""
    db = get_db()
    sources = list(db.datasources.find({}))
    return [{"dataSourceId": s["dataSourceId"], "name": s["name"]} for s in sources]


@app.get("/sources/{data_source_id}")
def get_source(data_source_id: str):
    """Q4: full details of one data source."""
    db = get_db()
    doc = db.datasources.find_one({"dataSourceId": data_source_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Data source not found")
    return serialize(doc)


@app.get("/timeseries")
def get_timeseries(
    assetId: str = Query(...),
    dataSourceId: str = Query(...),
    fromDate: Optional[str] = None,
    toDate: Optional[str] = None,
):
    """Q5: time-series data for a given asset + data source, optional date range."""
    db = get_db()
    query = {"assetId": assetId, "dataSourceId": dataSourceId, "isDeleted": False}
    if fromDate or toDate:
        ts_filter = {}
        if fromDate:
            ts_filter["$gte"] = fromDate
        if toDate:
            ts_filter["$lte"] = toDate
        query["timestamp"] = ts_filter

    points = list(db.timeseries.find(query).sort("timestamp", 1))
    if not points:
        raise HTTPException(status_code=404, detail="No timeseries data found for that asset/source")
    return [serialize(p) for p in points]


# --- UC3: simple analytics on top of the time series ---

@app.get("/analytics/trend")
def trend(assetId: str, dataSourceId: str):
    """Returns basic trend stats: min/max/avg close price, % change over the period."""
    result = compute_trend(assetId, dataSourceId)
    if result is None:
        raise HTTPException(status_code=404, detail="Not enough data to compute trend")
    return result


@app.get("/analytics/forecast")
def forecast(assetId: str, dataSourceId: str):
    """Very simple next-day price forecast (linear regression on recent history)."""
    result = forecast_next_price(assetId, dataSourceId)
    if result is None:
        raise HTTPException(status_code=404, detail="Not enough data to forecast")
    return result


@app.get("/health")
def health():
    return {"status": "ok"}
