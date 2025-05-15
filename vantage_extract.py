import os
import requests
import psycopg2
from dotenv import load_dotenv
import argparse
import datetime

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

# Parse command line arguments
parser = argparse.ArgumentParser(description='Fetch and upload stock data to Supabase')
parser.add_argument('symbol', type=str, help='Stock symbol (e.g., AAPL)')
args = parser.parse_args()
SYMBOL = args.symbol.upper()

if not DATABASE_URL or not API_KEY:
    raise RuntimeError("Please set DATABASE_URL and ALPHAVANTAGE_API_KEY in your .env")

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

# Check latest date in database for this symbol
latest_date = None
cur.execute("SELECT MAX(trade_date) FROM daily_ohlcv WHERE symbol = %s", (SYMBOL,))
result = cur.fetchone()
if result[0] is not None:
    latest_date = result[0]
    print(f"Found existing data for {SYMBOL} up to {latest_date}")
else:
    print(f"No existing data found for {SYMBOL}, will fetch all available history")

# Fetch full daily time series
print(f"Fetching daily time series for {SYMBOL} from Alpha Vantage...")
url = (
    f"https://www.alphavantage.co/query?"
    f"function=TIME_SERIES_DAILY&symbol={SYMBOL}"
    f"&outputsize=full&apikey={API_KEY}"
)
resp = requests.get(url)
resp.raise_for_status()
data = resp.json()
print("✅ Data fetched successfully.")

timeseries = data.get("Time Series (Daily)", {})
if not timeseries:
    raise RuntimeError("No 'Time Series (Daily)' found in response.")

# Filter data to only include new entries
new_entries = {}
if latest_date:
    for date_str, stats in timeseries.items():
        if datetime.datetime.strptime(date_str, '%Y-%m-%d').date() > latest_date:
            new_entries[date_str] = stats
    print(f"Found {len(new_entries)} new entries to upload (after {latest_date})")
else:
    new_entries = timeseries
    print(f"All {len(new_entries)} entries will be uploaded")

if not new_entries:
    print("No new data to upload!")
    cur.close()
    conn.close()
    print("✅ Database connection closed.")
    exit(0)

# Upsert each daily bar
print(f"Upserting {len(new_entries)} daily bars for {SYMBOL}...")
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
commit_interval = 500 # Commit every 500 rows

first_row = True
for date_str, stats in new_entries.items():
    if first_row:
        print(f"Inserting first row for date: {date_str}...")
        first_row = False
    cur.execute(upsert_sql, (
        SYMBOL,
        date_str,
        stats["1. open"],
        stats["2. high"],
        stats["3. low"],
        stats["4. close"],
        stats["5. volume"]
    ))
    row_count += 1
    if row_count % commit_interval == 0:
        conn.commit()
        print(f"    Committed {row_count}/{len(new_entries)} rows...")

# Commit any remaining rows that didn't make a full batch
conn.commit()
print(f"    Committed final rows. Total: {row_count}")

cur.close()
conn.close()
print("✅ Database connection closed.")

print(f"✅ Successfully upserted {len(new_entries)} days of {SYMBOL} into daily_ohlcv")
