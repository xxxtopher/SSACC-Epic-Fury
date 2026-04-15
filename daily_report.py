import os
import random
import time
import io
import datetime
import pandas as pd
from curl_cffi import requests

# Config
STOCKS = ["02497", "02501"]
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def fetch_data(ticker):
    # Calculate HK Today's Date
    hk_now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    today_str = hk_now.strftime('%Y-%m-%d')
    
    search_url = f"https://webbsite.0xmd.com/dbpub/stocksearch.asp?s={ticker}"
    try:
        # Step 1: Find Issue ID
        resp = requests.get(search_url, impersonate="chrome120", timeout=15)
        import re
        match = re.search(r'i=(\d+)', resp.url) or re.search(r'i=(\d+)', resp.text)
        if not match: return None
        
        issue_id = match.group(1)
        url = f"https://webbsite.0xmd.com/ccass/chldchg.asp?i={issue_id}&sort=chngdn&d={today_str}"
        
        # Step 2: Fetch Table
        time.sleep(random.uniform(3, 6))
        data_resp = requests.get(url, impersonate="chrome120", timeout=20)
        
        # Safety Check: Does the page actually have a table?
        if "<table" not in data_resp.text.lower():
            return "NO_TABLE"

        tables = pd.read_html(io.StringIO(data_resp.text))
        
        for df in tables:
            if 'Change' in df.columns:
                df = df[~df['Name'].isin(['Total', 'Unnamed Investor Participants'])].copy()
                df['Change'] = pd.to_numeric(df['Change'].astype(str).str.replace(',', ''), errors='coerce')
                df = df[df['Change'] != 0].dropna(subset=['Name'])
                
                if not df.empty:
                    return df[['Name', 'Change', 'Stake Δ %']]
        return "NO_CHANGES"
        
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram config missing.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    requests.post(url, json=payload)

# Execution logic
hk_now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
final_message = f"<b>📊 CCASS Report ({hk_now.strftime('%Y-%m-%d %H:%M')})</b>\n\n"

for stock in STOCKS:
    result = fetch_data(stock)
    final_message += f"<b>Stock: {stock}</b>\n"
    
    if isinstance(result, pd.DataFrame):
        # Format table for mobile
        final_message += f"<pre>{result.to_string(index=False)}</pre>\n\n"
    elif result == "NO_TABLE":
        final_message += "<i>No data table found on Webb-site for today.</i>\n\n"
    else:
        final_message += "<i>No significant broker moves.</i>\n\n"

send_telegram(final_message)