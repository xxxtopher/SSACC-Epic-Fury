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
    search_url = f"https://webbsite.0xmd.com/dbpub/stocksearch.asp?s={ticker}"
    try:
        resp = requests.get(search_url, impersonate="chrome120", timeout=15)
        import re
        match = re.search(r'i=(\d+)', resp.url) or re.search(r'i=(\d+)', resp.text)
        if not match: return None
        issue_id = match.group(1)

        # Scan back 5 days
        for days_back in range(5):
            check_date = (datetime.datetime.utcnow() + datetime.timedelta(hours=8) - datetime.timedelta(days=days_back)).strftime('%Y-%m-%d')
            url = f"https://webbsite.0xmd.com/ccass/chldchg.asp?i={issue_id}&sort=chngdn&d={check_date}"
            
            time.sleep(random.uniform(2, 4))
            data_resp = requests.get(url, impersonate="chrome120", timeout=20)
            
            if "<table" not in data_resp.text.lower():
                continue

            # NEW: Clean the HTML text before parsing to remove hidden formatting that blocks pandas
            clean_html = data_resp.text.replace('&nbsp;', '').replace('+', '')
            tables = pd.read_html(io.StringIO(clean_html))
            
            for df in tables:
                # Standardize column names
                df.columns = [str(c).strip().lower() for c in df.columns]
                
                # Find the 'name' column and any 'change' column
                name_col = next((c for c in df.columns if 'name' in c), None)
                change_col = next((c for c in df.columns if 'change' in c), None)
                
                if name_col and change_col:
                    # DEEP CLEAN: Remove commas and everything except numbers/minus signs
                    df[change_col] = df[change_col].astype(str).str.replace(r'[^-0-9.]', '', regex=True)
                    df[change_col] = pd.to_numeric(df[change_col], errors='coerce').fillna(0)
                    
                    # Filter: Must have a move, and Name must not be empty or 'Total'
                    move_df = df[(df[change_col] != 0) & 
                                (~df[name_col].str.contains('total|participants|investor', case=False, na=False))].copy()
                    
                    if not move_df.empty:
                        # Find stake column if it exists
                        stake_col = next((c for c in df.columns if '%' in c or 'stake' in c), change_col)
                        
                        display_df = move_df[[name_col, change_col, stake_col]].copy()
                        display_df.columns = ['Name', 'Change', 'Stake %']
                        return {"date": check_date, "df": display_df}
        
        return "NO_CHANGES"
    except Exception as e:
        print(f"Deep Scan Error for {ticker}: {e}")
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
    
    if isinstance(result, dict):
        final_message += f"<i>Date Found: {result['date']}</i>\n"
        final_message += f"<pre>{result['df'].to_string(index=False)}</pre>\n\n"
    else:
        final_message += "<i>No significant moves in the last 3 days.</i>\n\n"

send_telegram(final_message)