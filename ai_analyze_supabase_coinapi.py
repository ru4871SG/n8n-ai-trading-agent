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
        print(f"✅ Found {len(rows)} records.")
        return rows
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        if conn:
            cur.close()
            conn.close()
            print("✅ Database connection closed.")

def format_data_for_prompt(data):
    """Formats the fetched data into a string for the Gemini prompt."""
    if not data:
        return "No data available for the specified range."

    header = "Date        Open    High    Low     Close   Volume\n"
    data_str = header + "-" * (len(header) -1) + "\n"

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


def analyze_with_gemini(api_key, data_str, btc_price=None):
    """Sends the data to Gemini API for analysis."""
    if "No data available" in data_str:
        return data_str 

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
        prompt = f"You are a financial data analyst. Analyze the following stock market OHLCV data and provide insights on potential trends or patterns:{btc_info}\n\n{data_str}"
        
        if btc_price is not None:
            prompt += f"\n\nInclude in your analysis how this historical stock data might affect the current WBTC/USDT price of {btc_price}. Typically, there's no direct correlation between stock market and crypto market but you need to make this correlation since Bitcoin often follow the stock market trends."

        print("Sending data to AI for analysis...")
        response = model.generate_content(prompt)
        print("✅ Analysis received from Gemini.")
        return response.text
    except Exception as e:
        print(f"Gemini API error: {e}")
        return f"Error during Gemini analysis: {e}"

def main():
    parser = argparse.ArgumentParser(description="Fetch stock data from Supabase and analyze with Gemini.")
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


    data = fetch_data_from_supabase(DATABASE_URL, args.symbol, args.start_date, args.end_date)

    if data is None: # Check if fetch failed due to DB error
        print("Exiting due to database error.")
        return

    formatted_data = format_data_for_prompt(data)
    
    # Get current BTC price from CoinAPI and analyze if available
    btc_price = get_wbtc_usdt_price(COINAPI_KEY)
    analysis = analyze_with_gemini(GEMINI_API_KEY, formatted_data, btc_price)

    print("AI Analysis Result:")
    print(analysis)
    print("-----------------------\n")

if __name__ == "__main__":
    main()
