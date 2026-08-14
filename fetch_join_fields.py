"""
Run this in your ML-main repo (same env as w04_baseline_score.ipynb — duckdb + HF_TOKEN work there).

python fetch_join_fields.py

Produces work/outputs/w05_join_fields.csv with:
  content_hash_id, client_hash_id, content_age_days, search_volume, keyword_token_count

This gets joined onto the existing baseline_action_score.csv (by content_hash_id) in the
ML-08 notebook — no need to re-pull imp_march/avg_pos_march/ctr_march, those are already saved.
"""
import os
import duckdb
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
HF_TOKEN = os.environ["HF_TOKEN"]

con = duckdb.connect()
con.execute(f"CREATE OR REPLACE SECRET hf (TYPE huggingface, TOKEN '{HF_TOKEN}')")

REL = "hf://datasets/FlyRank/internship-warehouse"
MARCH = f"{REL}/fact_content_daily_performance/month=2026-03/*.parquet"
DIM_CONTENT = f"{REL}/dim_content.parquet"

df = con.sql(f"""
    WITH march_ids AS (
        SELECT DISTINCT content_hash_id, client_hash_id
        FROM read_parquet('{MARCH}')
        WHERE gsc_data_available IS TRUE
    )
    SELECT
        m.content_hash_id,
        m.client_hash_id,
        DATE_DIFF('day', d.content_created_date, DATE '2026-03-31') AS content_age_days,
        d.search_volume,
        d.keyword_token_count
    FROM march_ids m
    JOIN read_parquet('{DIM_CONTENT}') d USING (content_hash_id)
    WHERE d.content_created_date IS NOT NULL
""").df()

# one row per content item (a content item should have one client; keep first if any dup slip in)
df = df.drop_duplicates(subset=["content_hash_id"]).reset_index(drop=True)

out_path = "work/outputs/w05_join_fields.csv"
df.to_csv(out_path, index=False)
print(f"wrote {len(df):,} rows to {out_path}")
print(df.head())