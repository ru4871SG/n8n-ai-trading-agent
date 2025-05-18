import os
import argparse
import psycopg2
import google.generativeai as genai
import requests
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
COINAPI_KEY = os.getenv("COINAPI_KEY")


def fetch_data_from_supabase(db_url, symbol, start_date, end_date):
    """Fetches OHLCV data from Supabase for a given symbol and date range."""
    conn = None
    try:
        print(f"Connecting to database...")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        print("✅ Connected to database.")

        print(f"Fetching data for {symbol} from {start_date} to {end_date}...")
        query = """
        SELECT trade_date, open_price, high_price, low_price, close_price, volume
        FROM daily_ohlcv
        WHERE symbol = %s AND trade_date >= %s AND trade_date <= %s
        ORDER BY trade_date ASC;
        """
        cur.execute(query, (symbol, start_date, end_date))
        rows = cur.fetchall()
        print(f"✅ Found {len(rows)} records for {symbol}.")
        return rows
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        if conn:
            cur.close()
            conn.close()
            print("✅ Database connection closed.")

def format_data_for_prompt(data, symbol):
    """Formats the fetched data into a string for the Gemini prompt."""
    if not data:
        return f"No data available for {symbol} in the specified range."

    header = f"{symbol} Data:\nDate        Open    High    Low     Close   Volume\n"
    data_str = header + "-" * (len(header.split('\n')[1]) -1) + "\n"

    for row in data:
        date_str = row[0].strftime('%Y-%m-%d')
        open_p = f"{row[1]:<7.2f}"
        high_p = f"{row[2]:<7.2f}"
        low_p = f"{row[3]:<7.2f}"
        close_p = f"{row[4]:<7.2f}"
        volume = f"{row[5]:<10}"
        data_str += f"{date_str}  {open_p} {high_p} {low_p} {close_p} {volume}\n"

    return data_str.strip()


def get_wbtc_usdt_price(api_key):
    """Fetches the current WBTC/USDT price from CoinAPI."""
    url = 'https://rest.coinapi.io/v1/exchangerate/WBTC/USDT'
    headers = {'X-CoinAPI-Key': api_key}
    
    try:
        print("Fetching current WBTC/USDT price from CoinAPI...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        price = data.get('rate')
        if price:
            print(f"✅ Current WBTC/USDT Price: {price}")
            return price
        else:
            print("⚠️ Price data not found in response.")
            return None
    except requests.exceptions.HTTPError as http_err:
        print(f"❌ HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        print(f"❌ Error fetching WBTC/USDT price: {err}")
        return None


def analyze_with_gemini(api_key, stock_data_str, btc_data_str, btc_price=None):
    """Sends the data to Gemini API for analysis."""
    if "No data available" in stock_data_str and "No data available" in btc_data_str:
        return "No data available for analysis." 

    try:
        print("Configuring Gemini API...")
        genai.configure(api_key=api_key)
        # Use the preferred model
        model = genai.GenerativeModel('gemini-2.0-flash')
        print("✅ Gemini API configured with the chosen model")

        btc_info = ""
        if btc_price is not None:
            btc_info = f"\n\nThe current WBTC/USDT price is: {btc_price}"

        # Prepare the prompt for AI analysis    
        prompt = f"""You are a financial data analyst. Analyze the following data sets:

{stock_data_str}

{btc_data_str}{btc_info}

Please provide:
1. Independent analysis of both datasets, highlighting key trends and price action patterns
2. Make comparative trend analysis between the stock and Bitcoin during this period, including correlation analysis
3. How this comparison might help predict or explain the current Bitcoin price of {btc_price if btc_price else 'N/A'}
4. If the trends that you see from both datasets may suggest any potential prediction of future Bitcoin price, please include that as well."""

        print("Sending data to AI for analysis...")
        response = model.generate_content(prompt)
        print("✅ Analysis received from Gemini.")
        return response.text
    except Exception as e:
        print(f"Gemini API error: {e}")
        return f"Error during Gemini analysis: {e}"

def main():
    parser = argparse.ArgumentParser(description="Fetch stock data and BTC data, then analyze with Gemini.")
    parser.add_argument("--symbol", required=True, help="Stock symbol (e.g., AAPL)")
    parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    args = parser.parse_args()

    # Validate date format
    try:
        datetime.strptime(args.start_date, '%Y-%m-%d')
        datetime.strptime(args.end_date, '%Y-%m-%d')
    except ValueError:
        print("Error: Dates must be in YYYY-MM-DD format.")
        return

    # Check if environment variables are properly set
    if not DATABASE_URL:
        print("Error: DATABASE_URL environment variable not set.")
        return
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY environment variable not set.")
        return

    # Fetch data for the user-specified symbol
    stock_data = fetch_data_from_supabase(DATABASE_URL, args.symbol, args.start_date, args.end_date)
    if stock_data is None:
        print("Exiting due to database error when fetching stock data.")
        return
    
    # Automatically fetch BTC data for the same date range
    btc_symbol = "BTCUSD"
    print(f"Also fetching {btc_symbol} data for the same time period...")
    btc_data = fetch_data_from_supabase(DATABASE_URL, btc_symbol, args.start_date, args.end_date)
    if btc_data is None:
        print(f"Exiting due to database error when fetching {btc_symbol} data.")
        return

    # Format both datasets
    formatted_stock_data = format_data_for_prompt(stock_data, args.symbol)
    formatted_btc_data = format_data_for_prompt(btc_data, btc_symbol)
    
    # Get current BTC (WBTC) price from CoinAPI
    btc_price = get_wbtc_usdt_price(COINAPI_KEY)
    
    # Analyze both datasets together
    analysis = analyze_with_gemini(GEMINI_API_KEY, formatted_stock_data, formatted_btc_data, btc_price)

    print("\nAI Analysis Result:")
    print(analysis)

if __name__ == "__main__":
    main()
