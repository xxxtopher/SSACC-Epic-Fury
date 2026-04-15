import os, random, time, io, datetime
import pandas as pd
from curl_cffi import requests
from bs4 import BeautifulSoup

STOCKS = ["02497", "02501"]
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def fetch_data(ticker):
    # 1. Get the Issue ID (Standard across both)
    search_url = f"https://webbsite.0xmd.com/dbpub/stocksearch.asp?s={ticker}"
    try:
        resp = requests.get(search_url, impersonate="chrome120", timeout=15)
        import re
        match = re.search(r'i=(\d+)', resp.url) or re.search(r'i=(\d+)', resp.text)
        if not match: return None
        issue_id = match.group(1)

        # 2. Loop through 5 days (Streamlit often just hits 'latest', but we need a date)
        for days_back in range(5):
            check_date = (datetime.datetime.utcnow() + datetime.timedelta(hours=8) - datetime.timedelta(days=days_back)).strftime('%Y-%m-%d')
            url = f"https://webbsite.0xmd.com/ccass/chldchg.asp?i={issue_id}&sort=chngdn&d={check_date}"
            
            time.sleep(random.uniform(2, 4))
            data_resp = requests.get(url, impersonate="chrome120", timeout=20)
            
            # STREAMLIT LOGIC START: 
            # Use 'bs4' flavor which is often the default in Streamlit's environment
            tables = pd.read_html(io.StringIO(data_resp.text), flavor='bs4')
            
            for df in tables:
                # Force column names to string and lowercase
                df.columns = [str(c).strip().lower() for c in df.columns]
                
                # Streamlit scrapers usually look for the 'Name' and 'Holding change' columns
                name_col = next((c for c in df.columns if 'name' in c), None)
                change_col = next((c for c in df.columns if 'change' in c and 'stake' not in c), None)
                
                if name_col and change_col:
                    # Explicitly convert to string then clean to avoid 'NoneType' or 'Float' errors
                    df[change_col] = df[change_col].astype(str).str.replace(',', '').replace('+', '')
                    df[change_col] = pd.to_numeric(df[change_col], errors='coerce').fillna(0)
                    
                    # Filter for moves
                    move_df = df[(df[change_col] != 0) & 
                                (~df[name_col].str.contains('total|participants', case=False, na=False))].copy()
                    
                    if not move_df.empty:
                        # Success! Format exactly like your Dashboard
                        return {"date": check_date, "df": move_df[[name_col, change_col]]}
        return "NO_CHANGES"
    except Exception as e:
        print(f"Streamlit-Logic Error: {e}")
        return None

def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                  json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"})

# Run
hk_now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
msg = f"<b>📊 CCASS Report ({hk_now.strftime('%Y-%m-%d')})</b>\n\n"

for s in STOCKS:
    res = fetch_data(s)
    msg += f"<b>Stock: {s}</b>\n"
    if isinstance(res, dict):
        msg += f"<i>Date: {res['date']}</i>\n<pre>{res['df'].to_string(index=False)}</pre>\n\n"
    else:
        msg += "<i>No moves found.</i>\n\n"

send_telegram(msg)