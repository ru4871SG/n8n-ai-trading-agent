import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv
import argparse
import datetime
from pathlib import Path

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Parse command line arguments
parser = argparse.ArgumentParser(description='Import Bitcoin CSV data to Supabase')
parser.add_argument('--file', type=str, default="bitcoin_daily_ohlc/BTCUSD_Daily_OHLC.csv",
                   help='Path to Bitcoin CSV file (default: bitcoin_daily_ohlc/BTCUSD_Daily_OHLC.csv)')
args = parser.parse_args()

# Constants
SYMBOL = "BTCUSD"
CSV_PATH = args.file

if not DATABASE_URL:
    raise RuntimeError("Please set DATABASE_URL in your .env")

if not Path(CSV_PATH).exists():
    raise FileNotFoundError(f"CSV file not found: {CSV_PATH}")

# Connect to Supabase
print(f"Connecting to database...")
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
print("✅ Connected to database.")

# Validate table existence
print("Ensuring 'daily_ohlcv' table exists...")
cur.execute("""
CREATE TABLE IF NOT EXISTS daily_ohlcv (
    symbol      TEXT        NOT NULL,
    trade_date  DATE        NOT NULL,
    open_price  NUMERIC(12,4) NOT NULL,
    high_price  NUMERIC(12,4) NOT NULL,
    low_price   NUMERIC(12,4) NOT NULL,
    close_price NUMERIC(12,4) NOT NULL,
    volume      BIGINT      NOT NULL,
    PRIMARY KEY (symbol, trade_date)
);
""")
conn.commit()
print("✅ Table 'daily_ohlcv' is ready.")

# Read the CSV file
print(f"Reading CSV file: {CSV_PATH}...")
df = pd.read_csv(CSV_PATH)
print(f"✅ Loaded {len(df)} rows from CSV.")

# Check latest date in database for this symbol
latest_date = None
cur.execute("SELECT MAX(trade_date) FROM daily_ohlcv WHERE symbol = %s", (SYMBOL,))
result = cur.fetchone()
if result[0] is not None:
    latest_date = result[0]
    print(f"Found existing data for {SYMBOL} up to {latest_date}")
else:
    print(f"No existing data found for {SYMBOL}, will import all available history")

# Process the data
print("Processing data...")

df['trade_date'] = pd.to_datetime(df['timestamp'], unit='s').dt.date

for col in ['open', 'high', 'low', 'close', 'volume']:
    df[col] = pd.to_numeric(df[col], errors='coerce')

df['volume'] = df['volume'].round().astype('int64')

# Drop the original timestamp and trades columns, rename the rest to match our schema
df = df.drop(columns=['timestamp', 'trades'])
df = df.rename(columns={
    'open': 'open_price',
    'high': 'high_price',
    'low': 'low_price',
    'close': 'close_price'
})

# Add the symbol column
df['symbol'] = SYMBOL

# Filter data to only include new entries
if latest_date:
    df = df[df['trade_date'] > latest_date]
    print(f"Found {len(df)} new entries to upload (after {latest_date})")
else:
    print(f"All {len(df)} entries will be uploaded")

if len(df) == 0:
    print("No new data to upload!")
    cur.close()
    conn.close()
    print("✅ Database connection closed.")
    exit(0)

# Upsert each daily bar
print(f"Upserting {len(df)} daily bars for {SYMBOL}...")
upsert_sql = """
INSERT INTO daily_ohlcv
  (symbol, trade_date, open_price, high_price, low_price, close_price, volume)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (symbol, trade_date) DO UPDATE
  SET open_price  = EXCLUDED.open_price,
      high_price  = EXCLUDED.high_price,
      low_price   = EXCLUDED.low_price,
      close_price = EXCLUDED.close_price,
      volume      = EXCLUDED.volume;
"""

row_count = 0
commit_interval = 500  # Commit every 500 rows

first_row = True
# Sort by date to ensure chronological insertion
df = df.sort_values('trade_date')

for _, row in df.iterrows():
    if first_row:
        print(f"Inserting first row for date: {row['trade_date']}...")
        first_row = False
        
    cur.execute(upsert_sql, (
        row['symbol'],
        row['trade_date'],
        row['open_price'],
        row['high_price'],
        row['low_price'],
        row['close_price'],
        row['volume']
    ))
    
    row_count += 1
    if row_count % commit_interval == 0:
        conn.commit()
        print(f"    Committed {row_count}/{len(df)} rows...")

# Commit any remaining rows that didn't make a full batch
conn.commit()
print(f"    Committed final rows. Total: {row_count}")

cur.close()
conn.close()
print("✅ Database connection closed.")

print(f"✅ Successfully upserted {row_count} days of {SYMBOL} into daily_ohlcv")