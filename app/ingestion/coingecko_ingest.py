"""
ingestion/coingecko_ingest.py

Implements UC1 (Data Ingest from Financial Data Providers) for CoinGecko.

What it does:
1. Registers "coingecko" as a data source (provenance).
2. Fetches a small set of top coins (current snapshot -> becomes an asset
   version via upsert_asset, so attribute changes are tracked over time).
3. Fetches historical daily price data for each coin (-> timeseries points).

Run: python -m app.ingestion.coingecko_ingest
"""
import time
import requests
from datetime import datetime, timezone
from app.db.connection import get_db
from app.db.temporal_repo import upsert_asset, insert_timeseries_point

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
DATA_SOURCE_ID = "coingecko"

# Keep this small to stay within CoinGecko's free-tier rate limits
COIN_IDS = ["bitcoin", "ethereum", "tether", "binancecoin", "ripple"]


def register_data_source():
    db = get_db()
    db.datasources.update_one(
        {"dataSourceId": DATA_SOURCE_ID},
        {"$setOnInsert": {
            "dataSourceId": DATA_SOURCE_ID,
            "name": "CoinGecko",
            "type": "REST API",
            "baseUrl": COINGECKO_BASE,
            "registeredAt": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    print(f"Data source '{DATA_SOURCE_ID}' registered.")


def ingest_asset_metadata():
    """Fetch current market snapshot for each coin -> creates/updates asset version."""
    url = f"{COINGECKO_BASE}/coins/markets"
    params = {"vs_currency": "usd", "ids": ",".join(COIN_IDS)}
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    coins = resp.json()

    for coin in coins:
        upsert_asset(
            asset_id=coin["id"],
            symbol=coin["symbol"].upper(),
            instrument_class="crypto",
            description=coin["name"],
            region="Global",
            attributes={
                "marketCap": coin.get("market_cap"),
                "circulatingSupply": coin.get("circulating_supply"),
                "currentPrice": coin.get("current_price"),
            },
            source_id=DATA_SOURCE_ID,
        )
        print(f"Asset upserted: {coin['id']} ({coin['symbol'].upper()})")


def ingest_timeseries(days: int = 30):
    """Fetch `days` of daily historical prices for each coin -> timeseries points."""
    for coin_id in COIN_IDS:
        url = f"{COINGECKO_BASE}/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": days, "interval": "daily"}
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        prices = data.get("prices", [])       # [timestamp_ms, price]
        volumes = data.get("total_volumes", [])

        count = 0
        for i, (ts_ms, price) in enumerate(prices):
            ts_iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
            volume = volumes[i][1] if i < len(volumes) else None
            insert_timeseries_point(
                asset_id=coin_id,
                data_source_id=DATA_SOURCE_ID,
                timestamp=ts_iso,
                fields={"close": price, "volume": volume},
            )
            count += 1
        print(f"Ingested {count} timeseries points for {coin_id}")
        time.sleep(1.5)  # be polite to CoinGecko's free-tier rate limit


def run():
    register_data_source()
    ingest_asset_metadata()
    ingest_timeseries(days=30)
    print("Ingestion complete.")


if __name__ == "__main__":
    run()
