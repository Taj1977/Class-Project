"""
db/connection.py

Single place that creates and exposes the MongoDB client + collections.
Every other module (ingestion, api, analytics, mcp) imports `get_db()`
from here instead of creating its own connection.
"""
import os
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "acme_dwh")

_client = None


def get_db():
    """Returns the acme_dwh database, creating the client once (singleton)."""
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client[MONGO_DB]


def ensure_indexes():
    """
    Creates indexes needed for the queries in the spec (Q1-Q5) and for
    temporal lookups. Safe to call multiple times (idempotent).
    """
    db = get_db()

    # assets: look up by logical assetId + filter to "current" version (validTo: null)
    db.assets.create_index([("assetId", ASCENDING), ("validFrom", ASCENDING)])
    db.assets.create_index([("assetId", ASCENDING), ("validTo", ASCENDING)])

    # timeseries: the hot query path is (assetId, dataSourceId, timestamp range)
    db.timeseries.create_index(
        [("assetId", ASCENDING), ("dataSourceId", ASCENDING), ("timestamp", ASCENDING)]
    )

    # datasources: lookup by stable id
    db.datasources.create_index([("dataSourceId", ASCENDING)], unique=True)

    print("Indexes ensured on: assets, timeseries, datasources")


if __name__ == "__main__":
    ensure_indexes()
