"""
run_analysis.py
-----------------
Parses sql/analysis.sql into its individual labeled queries (each preceded
by a "-- @name: query_name" comment), runs each one against the DuckDB
warehouse, prints a preview, and exports the full result to output/<name>.csv

Run:
    python scripts/run_analysis.py
"""

import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "warehouse.duckdb"
ANALYSIS_SQL_PATH = ROOT / "sql" / "analysis.sql"
OUTPUT_DIR = ROOT / "output"


def parse_queries(sql_text: str):
    """Splits analysis.sql into a list of (name, query) tuples based on
    '-- @name: ...' marker comments."""
    pattern = re.compile(r"--\s*@name:\s*(\w+)\s*\n(.*?)(?=(?:--\s*@name:)|\Z)", re.S)
    queries = []
    for match in pattern.finditer(sql_text):
        name = match.group(1).strip()
        query = match.group(2).strip().rstrip(";")
        queries.append((name, query))
    return queries


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB_PATH))

    sql_text = ANALYSIS_SQL_PATH.read_text()
    queries = parse_queries(sql_text)

    print(f"Found {len(queries)} labeled queries in {ANALYSIS_SQL_PATH.name}\n")

    for name, query in queries:
        print(f"=== {name} ===")
        df = con.execute(query).fetchdf()
        print(df.head(10).to_string(index=False))
        out_path = OUTPUT_DIR / f"{name}.csv"
        df.to_csv(out_path, index=False)
        print(f"-> saved {len(df)} rows to {out_path.relative_to(ROOT)}\n")

    con.close()


if __name__ == "__main__":
    main()
