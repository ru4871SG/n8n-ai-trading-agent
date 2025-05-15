import time
import hmac
import hashlib
import requests
import urllib.parse
import os
import sys
from decimal import Decimal, ROUND_DOWN
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY    = os.getenv("MEXC_API_KEY")
API_SECRET = os.getenv("MEXC_API_SECRET")
if not API_KEY or not API_SECRET:
    print("Error - API_KEY or API_SECRET not found")
    exit()

BASE_URL        = "https://api.mexc.co"
SYMBOL          = "WBTCUSDT"
USDT_TO_SPEND   = 20.0
PRICE_PRECISION = 2

session = requests.Session()

def format_value(value, precision):
    return f"{Decimal(str(value)).quantize(Decimal('1e-' + str(precision)), rounding=ROUND_DOWN)}"

def sign_request(params):
    qs = urllib.parse.urlencode(params)
    return hmac.new(API_SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()

def send_signed_request(method, endpoint, params):
    params['timestamp']   = int(time.time() * 1000)
    params['recvWindow']  = 5000
    params['signature']   = sign_request(params)
    headers = {'X-MEXC-APIKEY': API_KEY}

    if method == 'GET':
        r = session.get(BASE_URL + endpoint, headers=headers, params=params)
    else:
        data_str = urllib.parse.urlencode(params)
        r = session.post(BASE_URL + endpoint + "?" + data_str, headers=headers)

    r.raise_for_status()
    return r.json()

def validate_api_keys():
    try:
        r = send_signed_request('GET', '/api/v3/account', {})
        return 'makerCommission' in r
    except Exception as e:
        print("Error -  API key validation failed:", e)
        return False

def place_market_buy():
    qty_str = format_value(USDT_TO_SPEND, PRICE_PRECISION)
    params = {
        'symbol':       SYMBOL,
        'side':         'BUY',
        'type':         'MARKET',
        'quoteOrderQty': qty_str
    }
    resp = send_signed_request('POST', '/api/v3/order', params)
    print("[+] Market BUY response:", resp)

def main():
    # Check if a command-line argument was provided
    if len(sys.argv) < 2:
        print("Usage: python3 mexc_buy.py yes|no")
        print("You must specify 'yes' to execute the buy operation")
        return
    
    # Only proceed if the argument is exactly "yes"
    if sys.argv[1].lower() != "yes":
        print("Buy operation cancelled. Use 'yes' to confirm the buy.")
        return
        
    print("Buy WBTCUSDT")
    if not validate_api_keys():
        print("Error -  API key validation failed.")
        return
    place_market_buy()

if __name__ == "__main__":
    main()
