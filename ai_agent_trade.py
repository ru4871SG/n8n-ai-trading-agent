#!/usr/bin/env python3
import sys
import json
import re

def main():
    if len(sys.argv) < 2:
        print("ERROR: No agent output provided")
        sys.exit(1)

    agent_msg = sys.argv[1]
    # Look specifically for "Take Profit <num>" and "Stop Loss <num>", if there's none, look for "Take Profits <num>" and "Stop Losses <num>",
    # if there's still none, look for "Take Profit Level <num>" and "Stop Loss Level <num>"
    tp_match = re.search(r'Take Profit\s*([0-9]+(?:\.[0-9]+)?)', agent_msg)
    if not tp_match:
        tp_match = re.search(r'Take Profits\s*([0-9]+(?:\.[0-9]+)?)', agent_msg)
        if not tp_match:
            tp_match = re.search(r'Take Profit Level\s*([0-9]+(?:\.[0-9]+)?)', agent_msg)
    
    sl_match = re.search(r'Stop Loss\s*([0-9]+(?:\.[0-9]+)?)', agent_msg)
    if not sl_match:
        sl_match = re.search(r'Stop Losses\s*([0-9]+(?:\.[0-9]+)?)', agent_msg)
        if not sl_match:
            sl_match = re.search(r'Stop Loss Level\s*([0-9]+(?:\.[0-9]+)?)', agent_msg)

    if not tp_match or not sl_match:
        print(f"ERROR: Couldn't parse TP/SL from agent output:\n{agent_msg}")
        sys.exit(1)

    take_profit = float(tp_match.group(1))
    stop_loss   = float(sl_match.group(1))

    # Check for buy recommendation. Default to "no" unless explicitly mentioned
    buy = "no"
    if re.search(r'Buy\s*(?:\:|)\s*yes', agent_msg, re.IGNORECASE):
        buy = "yes"

    # Echo for readability in your n8n logs
    print(f"Take Profit: {take_profit}")
    print(f"Stop Loss: {stop_loss}")
    print(f"Buy: {buy}")

    # Write clean JSON
    data = {
        "take_profit": take_profit,
        "stop_loss": stop_loss,
        "buy": buy
    }
    with open('ai_agent_param.json', 'w') as f:
        json.dump(data, f, indent=4)
    print("✅  Data saved to ai_agent_param.json")

if __name__ == "__main__":
    main()
