import os
import random
import time
import io
import datetime
import re
import pandas as pd
from curl_cffi import requests

# Config
STOCKS = ["02497", "02501"]
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def get_issue_id(ticker):
    target = ticker.zfill(5)
    search_url = f"https://webbsite.0xmd.com/dbpub/stocksearch.asp?s={target}"
    try:
        resp = requests.get(search_url, impersonate="chrome120", timeout=15)
        match = re.search(r'i=(\d+)', resp.url) or re.search(r'i=(\d+)', resp.text)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"Discovery failed for {target}: {e}")
    return None

def fetch_ccass_changes(issue_id):
    # Calculate Hong Kong date (T+2 context)
    # We check the last 3 days to ensure we find the most recent settled report
    for days_back in range(4):
        date_val = (datetime.datetime.utcnow() + datetime.timedelta(hours=8) - datetime.timedelta(days=days_back)).strftime('%Y-%m-%d')
        base_url = f"https://webbsite.0xmd.com/ccass/chldchg.asp?i={issue_id}&sort=chngdn&d={date_val}"
        
        # MIRROR STREAMLIT HEADERS
        headers = {
            'Referer': f'https://webbsite.0xmd.com/ccass/choldings.asp?i={issue_id}',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-HK,en;q=0.9,zh-HK;q=0.8,zh;q=0.7',
            'Upgrade-Insecure-Requests': '1',
        }

        try:
            time.sleep(random.uniform(3.0, 6.0))
            resp = requests.get(
                base_url, 
                headers=headers, 
                impersonate="chrome120", 
                timeout=25
            )

            if resp.status_code != 200:
                continue

            tables = pd.read_html(io.StringIO(resp.text))
            for df in tables:
                if 'Change' in df.columns:
                    df = df[df['Name'] != 'Total'].copy()
                    df['Change'] = pd.to_numeric(df['Change'].astype(str).str.replace(',', ''), errors='coerce')
                    df = df[df['Change'] != 0].dropna(subset=['Name'])
                    
                    if not df.empty:
                        # Success: Return the date and the formatted dataframe
                        # We limit columns to match the mobile Telegram view
                        cols_to_show = [c for c in ['Name', 'Change', 'Stake %'] if c in df.columns]
                        return {"date": date_val, "df": df[cols_to_show].head(10)} # Top 10 moves
        except Exception as e:
            print(f"Error on date {date_val}: {e}")
            continue
            
    return None

def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    requests.post(url, json=payload)

# Execution logic
hk_now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
final_message = f"<b>📊 CCASS Change Alert ({hk_now.strftime('%Y-%m-%d')})</b>\n\n"

for ticker in STOCKS:
    issue_id = get_issue_id(ticker)
    if issue_id:
        result = fetch_ccass_changes(issue_id)
        final_message += f"<b>Stock: {ticker}</b>\n"
        if result:
            final_message += f"<i>Date: {result['date']}</i>\n"
            # Format the dataframe as a code block for readability
            final_message += f"<pre>{result['df'].to_string(index=False)}</pre>\n\n"
        else:
            final_message += "<i>No movements found in last 3 days.</i>\n\n"
    else:
        final_message += f"<b>Stock: {ticker}</b>\n<i>Error: Could not resolve Issue ID</i>\n\n"

send_telegram(final_message)