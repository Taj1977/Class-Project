"""
db/temporal_repo.py

Implements the temporal data warehouse paradigm for the `assets` collection:
- Nothing is ever updated or deleted in place.
- "Updating" an asset = close the current version (set validTo) and insert
  a new version document.
- "Deleting" an asset = insert a new version with isDeleted=True, marking
  that from validFrom onward the asset is no longer available.
- You can always ask "what did asset X look like at time T?" and get a
  correct historical answer.

The `timeseries` collection is append-only by nature (each point is a fact
tied to a timestamp), so it only needs an `isDeleted` marker for retraction,
no validFrom/validTo versioning.
"""
from datetime import datetime, timezone
from app.db.connection import get_db


def _now():
    return datetime.now(timezone.utc).isoformat()


def upsert_asset(asset_id: str, symbol: str, instrument_class: str,
                  description: str, region: str, attributes: dict,
                  source_id: str, as_of: str = None):
    """
    Insert a new version of an asset. If a current version exists, it is
    closed (validTo set) rather than modified. If the new data is identical
    to the current version, no-op (avoid noisy duplicate versions).
    """
    db = get_db()
    as_of = as_of or _now()

    current = db.assets.find_one({"assetId": asset_id, "validTo": None})

    if current:
        # Skip if nothing actually changed
        unchanged = (
            current.get("symbol") == symbol
            and current.get("instrumentClass") == instrument_class
            and current.get("description") == description
            and current.get("regionOfOrigin") == region
            and current.get("attributes") == attributes
            and current.get("isDeleted", False) is False
        )
        if unchanged:
            return current

        # Close the current version (this is the only "update" we ever do,
        # and it only touches validTo - never the business fields)
        db.assets.update_one(
            {"_id": current["_id"]},
            {"$set": {"validTo": as_of}}
        )

    new_version = {
        "assetId": asset_id,
        "symbol": symbol,
        "instrumentClass": instrument_class,
        "description": description,
        "regionOfOrigin": region,
        "attributes": attributes,
        "sourceId": source_id,
        "validFrom": as_of,
        "validTo": None,
        "isDeleted": False,
    }
    result = db.assets.insert_one(new_version)
    new_version["_id"] = result.inserted_id
    return new_version


def delete_asset(asset_id: str, as_of: str = None):
    """
    'Deletes' an asset by closing the current version and inserting a
    marker version with isDeleted=True. The historical record is preserved.
    """
    db = get_db()
    as_of = as_of or _now()
    current = db.assets.find_one({"assetId": asset_id, "validTo": None})
    if not current or current.get("isDeleted"):
        return None

    db.assets.update_one({"_id": current["_id"]}, {"$set": {"validTo": as_of}})

    marker = {**current, "validFrom": as_of, "validTo": None, "isDeleted": True}
    marker.pop("_id")
    result = db.assets.insert_one(marker)
    marker["_id"] = result.inserted_id
    return marker


def get_current_asset(asset_id: str):
    db = get_db()
    return db.assets.find_one({"assetId": asset_id, "validTo": None})


def get_asset_as_of(asset_id: str, as_of: str):
    """
    Point-in-time query: returns the version of the asset that was valid
    at the given timestamp (as_of), or None if it didn't exist yet / was
    already deleted at that point.
    """
    db = get_db()
    doc = db.assets.find_one({
        "assetId": asset_id,
        "validFrom": {"$lte": as_of},
        "$or": [{"validTo": None}, {"validTo": {"$gt": as_of}}],
    })
    return doc


def list_current_assets(instrument_class: str = None):
    db = get_db()
    query = {"validTo": None, "isDeleted": False}
    if instrument_class:
        query["instrumentClass"] = instrument_class
    return list(db.assets.find(query))


def insert_timeseries_point(asset_id: str, data_source_id: str, timestamp: str,
                             fields: dict):
    """
    Inserts a single time-series point. Points are immutable facts, so this
    is a plain insert (append-only). Duplicate (assetId, dataSourceId,
    timestamp) points are upserted-by-replace ONLY for the very same
    ingestion run correcting itself - in a stricter system you might forbid
    this entirely, but for this project we guard against double-ingestion.
    """
    db = get_db()
    doc = {
        "assetId": asset_id,
        "dataSourceId": data_source_id,
        "timestamp": timestamp,
        "ingestedAt": _now(),
        "isDeleted": False,
        **fields,
    }
    existing = db.timeseries.find_one({
        "assetId": asset_id, "dataSourceId": data_source_id, "timestamp": timestamp
    })
    if existing:
        return existing  # already ingested this point, don't duplicate
    result = db.timeseries.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc
