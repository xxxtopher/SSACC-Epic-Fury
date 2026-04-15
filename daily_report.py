import os
import random
import time
import io
import pandas as pd
from curl_cffi import requests

# Config
STOCKS = ["02497", "02501"]
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def fetch_data(ticker):
    # Search trick to find Issue ID dynamically
    search_url = f"https://webbsite.0xmd.com/dbpub/stocksearch.asp?s={ticker}"
    try:
        resp = requests.get(search_url, impersonate="chrome120", timeout=15)
        import re
        match = re.search(r'i=(\d+)', resp.url) or re.search(r'i=(\d+)', resp.text)
        if not match: return None
        
        issue_id = match.group(1)
        url = f"https://webbsite.0xmd.com/ccass/chldchg.asp?i={issue_id}&sort=chngdn"
        
        time.sleep(random.uniform(3, 7))
        data_resp = requests.get(url, impersonate="chrome120", timeout=20)
        tables = pd.read_html(io.StringIO(data_resp.text))
        
        for df in tables:
            if 'Change' in df.columns:
                df = df[df['Name'] != 'Total'].copy()
                df['Change'] = pd.to_numeric(df['Change'].astype(str).str.replace(',', ''), errors='coerce')
                # Filter for active movers
                df = df[df['Change'] != 0].dropna(subset=['Name'])
                return df[['Name', 'Change', 'Stake Δ %']]
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
    return None

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    requests.post(url, json=payload)

# Execution
final_message = "<b>📊 Daily CCASS Change Report</b>\n\n"

for stock in STOCKS:
    df = fetch_data(stock)
    if df is not None and not df.empty:
        final_message += f"<b>Stock: {stock}</b>\n"
        # We use <pre> to keep the table columns aligned on mobile
        final_message += f"<pre>{df.to_string(index=False)}</pre>\n\n"
    else:
        final_message += f"<b>Stock: {stock}</b>\n<i>No changes detected.</i>\n\n"

if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
    send_telegram(final_message)
    print("Telegram message sent.")