# Project Report: Data Warehouse for Financial Markets Data (Acme Ltd)

## 1. Overview
This project implements a temporal, NoSQL-backed data warehouse for
financial instruments, covering data ingestion, a REST API, basic
analytics, and an LLM assistant integrated via MCP, as required by the
project specification.

[Student: add 2-3 sentences here on current status - e.g. "implemented
and partially tested" / "implemented, testing in progress" - be honest
about what's verified vs not, consistent with GENAI_USAGE.md.]

## 2. Data Used
- **Source:** CoinGecko public REST API (no authentication required)
- **Assets ingested:** Bitcoin, Ethereum, Tether, BNB, XRP (instrumentClass: crypto)
- **Time series:** daily closing price + volume, 30-day history per asset
- **Provenance:** every asset version and time-series point stores its
  `dataSourceId`, so the origin of any record can always be traced.

## 3. Architecture
- **Database (NoSQL, mandatory):** MongoDB
  - `assets` collection — temporal, append-only versions of each
    financial instrument (validFrom/validTo/isDeleted)
  - `timeseries` collection — append-only price/volume facts per
    asset + data source + timestamp
  - `datasources` collection — registry of providers
- **API layer:** FastAPI (Python), implementing the 5 required queries
  (Q1-Q5) plus two analytics endpoints
- **Analytics:** pandas for trend statistics, scikit-learn (linear
  regression) for a simple next-value forecast
- **LLM/MCP layer:** an MCP server exposing 6 tools (list_assets,
  get_asset, list_sources, fetch_time_series, summarize_trend,
  compare_assets) so an MCP-compatible LLM client can answer questions
  grounded in the warehouse's actual data

## 4. Temporal Data Warehouse Design
Records in `assets` are never updated or deleted in place:
- An "update" closes the current version (sets `validTo` to the change
  timestamp) and inserts a new version document with the new data.
- A "deletion" inserts a new version with `isDeleted: true`, marking
  that the asset is no longer available from that point onward, while
  preserving all prior versions.
- Point-in-time queries (`GET /assets/{id}?asOf=...`) return the
  version of the asset that was valid at a given timestamp, satisfying
  the requirement that the system return correct historical data at
  any given time.

Time-series points are treated as immutable facts (each tied to a
specific timestamp), so they are append-only by construction; an
`isDeleted` flag is available for retracting an individual point
without removing it from the collection.

## 5. Use Case Coverage
| Use Case | Status | Notes |
|---|---|---|
| UC1 - Ingestion | Implemented | CoinGecko, with provenance tracking |
| UC2 - REST API | Implemented | 5 required queries + health check |
| UC3 - Analytics | Implemented | trend stats + simple linear forecast |
| UC4 - LLM/MCP assistant | Implemented | 6 MCP tools exposed |
| Bonus - Agentic/LangFlow | Not implemented | out of scope given time constraints |

## 6. How to Reproduce
See `README.md` for full setup steps (MongoDB via Docker, Python
dependencies, ingestion script, running the API and MCP server, and
example queries).

## 7. Limitations and Future Work
- Only one asset class (crypto) and one provider (CoinGecko) are wired
  in; the data model supports more (stocks, bonds, etc. via the
  `attributes` map) but additional ingestion adapters would be needed.
- The forecast model is intentionally simple, per the spec's allowance
  for "simple forecasts."
- No authentication/authorization on the API.
- Agentic multi-step workflows (LangFlow bonus) were not built.

## 8. GenAI Tools Usage
See `GENAI_USAGE.md` for the full disclosure statement.
