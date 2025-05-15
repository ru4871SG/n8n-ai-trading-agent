import time
import hmac
import hashlib
import requests
import urllib.parse
import os
import json
from decimal import Decimal, ROUND_DOWN
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY    = os.getenv("MEXC_API_KEY")
API_SECRET = os.getenv("MEXC_API_SECRET")
if not API_KEY or not API_SECRET:
    print("Error - API_KEY or API_SECRET not found")
    exit()

BASE_URL            = "https://api.mexc.co"
SYMBOL              = "WBTCUSDT"
PARAMS_FILE         = "ai_agent_param.json"
PRICE_PRECISION     = 2
QUANTITY_PRECISION  = 5
SLEEP_INTERVAL      = 120
MIN_BALANCE         = Decimal('0.00015')  # Minimum balance to execute trades

session = requests.Session()

# Helper functions
def sign_request(params):
    qs = urllib.parse.urlencode(params)
    return hmac.new(API_SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()

def send_signed_request(method, endpoint, params):
    params['timestamp']  = int(time.time() * 1000)
    params['recvWindow'] = 5000
    params['signature']  = sign_request(params)
    headers = {'X-MEXC-APIKEY': API_KEY}

    if method == 'POST':
        data = urllib.parse.urlencode(params)
        r = session.post(f"{BASE_URL}{endpoint}?{data}", headers=headers)
    else:
        r = session.get(f"{BASE_URL}{endpoint}", headers=headers, params=params)

    r.raise_for_status()
    return r.json()

def get_wbtc_balance():
    resp = send_signed_request('GET', '/api/v3/account', {})
    for b in resp.get('balances', []):
        if b['asset'] == 'WBTC':
            return Decimal(b['free'])  # Only use free balance, not locked balance
    return Decimal('0')

def load_params():
    with open(PARAMS_FILE) as f:
        p = json.load(f)
    return Decimal(str(p['take_profit'])), Decimal(str(p['stop_loss']))

def get_price():
    r = session.get(f"{BASE_URL}/api/v3/ticker/price", params={'symbol': SYMBOL})
    r.raise_for_status()
    return Decimal(r.json()['price'])

def format_value(val, prec):
    return f"{val.quantize(Decimal('1e-' + str(prec)), rounding=ROUND_DOWN)}"

def place_market_sell(qty_str):
    try:
        # Apply a small reduction to account for possible fees
        qty_decimal = Decimal(qty_str) * Decimal('0.995')
        qty_str = format_value(qty_decimal, QUANTITY_PRECISION)
        print(f"Selling quantity: {qty_str} (reduced to account for fees)")
        
        params = {
            'symbol':   SYMBOL,
            'side':     'SELL',
            'type':     'MARKET',
            'quantity': qty_str
        }
        
        resp = send_signed_request('POST', '/api/v3/order', params)
        print("[+] Market SELL response:", resp)
        return True
    except requests.exceptions.HTTPError as e:
        print(f"Failed to place order: {e}")
        if hasattr(e.response, 'text'):
            print(f"Exchange response: {e.response.text}")
            
            # If still oversold, try reducing the quantity
            if "Oversold" in e.response.text:
                print("Trying with 99% of available quantity...")
                try:
                    reduced_qty = Decimal(qty_str) * Decimal('0.99')
                    reduced_qty_str = format_value(reduced_qty, QUANTITY_PRECISION)
                    
                    params = {
                        'symbol':   SYMBOL,
                        'side':     'SELL',
                        'type':     'MARKET', 
                        'quantity': reduced_qty_str
                    }
                    
                    resp = send_signed_request('POST', '/api/v3/order', params)
                    print("[+] Market SELL response:", resp)
                    return True
                except Exception as inner_e:
                    print(f"Second attempt also failed: {inner_e}")
                    return False
        
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def main():
    print("Monitor WBTCUSDT & Market Sell")
    balance = get_wbtc_balance()
    
    # Check if balance meets minimum threshold
    if balance <= 0:
        print("No WBTC balance detected. Exiting.")
        return
    elif balance < MIN_BALANCE:
        print(f"Balance ({balance}) is too small, won't execute any market sell (minimum: {MIN_BALANCE})")
        return

    qty_str = format_value(balance, QUANTITY_PRECISION)
    print(f"WBTC balance: {balance}")
    print(f"Qty to sell: {qty_str}")

    while True:
        # Reload parameters on each check
        tp, sl = load_params()
        print(f"Current parameters - Take-Profit @ {tp}, Stop-Loss @ {sl}")
        
        price = get_price()
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{ts}] Current price: {price}")

        if price >= tp:
            print(f"Price ≥ TP ({tp}). Selling {qty_str} WBTC at market.")
            success = place_market_sell(qty_str)
            if success:
                break
            else:
                print("Warning: Order failed. Will continue monitoring...")
        
        if price <= sl:
            print(f"Price ≤ SL ({sl}). Selling {qty_str} WBTC at market.")
            success = place_market_sell(qty_str)
            if success:
                break
            else:
                print("Warning: Order failed. Will continue monitoring...")

        print(f"No trigger. Sleeping {SLEEP_INTERVAL}s...")
        time.sleep(SLEEP_INTERVAL)

if __name__ == "__main__":
    main()
