# Acme Ltd - Data Warehouse for Financial Markets Data

## What this is
A temporal NoSQL data warehouse for financial instruments, built for the
Lab Project spec. Covers all 4 use cases:
- UC1: Ingestion from CoinGecko (with provenance tracking)
- UC2: REST API (FastAPI) - the 5 required queries
- UC3: Simple analytics (trend stats + linear regression forecast)
- UC4: MCP server exposing the platform as LLM tools

## Architecture
- **Database:** MongoDB (NoSQL, mandatory per spec)
- **Temporal model:** assets are never updated/deleted in place. Each
  change inserts a new version (`validFrom`/`validTo`); deletion inserts
  an `isDeleted: true` marker version. See `app/db/temporal_repo.py`.
- **API:** FastAPI, see `app/api/main.py`
- **Analytics:** pandas + scikit-learn, see `app/analytics/engine.py`
- **MCP/LLM:** `app/mcp/server.py` exposes 6 tools an LLM client can call

## Setup
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Start MongoDB (Docker is easiest):
```bash
docker run -d -p 27017:27017 --name acme-mongo mongo:7
```

Create indexes:
```bash
python -m app.db.connection
```

Run ingestion (pulls 5 cryptocurrencies + 30 days of history from CoinGecko):
```bash
python -m app.ingestion.coingecko_ingest
```

Start the API:
```bash
uvicorn app.api.main:app --reload
```
Docs available at http://localhost:8000/docs

Example calls:
```
GET /assets
GET /assets/bitcoin
GET /sources
GET /timeseries?assetId=bitcoin&dataSourceId=coingecko
GET /analytics/trend?assetId=bitcoin&dataSourceId=coingecko
GET /analytics/forecast?assetId=bitcoin&dataSourceId=coingecko
```

Run the MCP server (separate terminal, for LLM client integration):
```bash
python -m app.mcp.server
```

## Temporal queries
`GET /assets/bitcoin?asOf=2026-06-01T00:00:00Z` returns the version of
the asset that was valid at that point in time, demonstrating the
temporal/point-in-time capability required by the spec.

## Known limitations / next steps
- Only crypto assets ingested (CoinGecko); stocks/bonds not yet wired in
- Forecast model is intentionally simple (linear regression), as allowed
  by the spec ("simple forecasts")
- No authentication on the API (out of scope for this project)
- LangFlow agentic bonus not implemented

## GenAI usage
See GENAI_USAGE.md for the disclosure statement.
