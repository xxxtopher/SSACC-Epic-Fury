import os
import random
import time
import io
import datetime
import pandas as pd
from curl_cffi import requests

# ==========================================
# 1. CONFIGURATION & MAPPING
# ==========================================
# These IDs are taken directly from the Webb-site/0xmd URLs
# 2497 -> 34573
# 2501 -> 34574
ISSUE_MAP = {
    "02497": "34757",
    "02501": "34573"
}

STOCKS = ["02497", "02501"]
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def fetch_ccass_changes(ticker):
    issue_id = ISSUE_MAP.get(ticker)
    if not issue_id:
        print(f"Skipping {ticker}: No Issue ID mapped.")
        return None

    # Check last 4 days to ensure we catch the T+2 settlement cycle
    for days_back in range(4):
        date_val = (datetime.datetime.utcnow() + datetime.timedelta(hours=8) - datetime.timedelta(days=days_back)).strftime('%Y-%m-%d')
        base_url = f"https://webbsite.0xmd.com/ccass/chldchg.asp?i={issue_id}&sort=chngdn&d={date_val}"
        
        # EXACT HEADERS FROM YOUR STREAMLIT DASHBOARD
        headers = {
            'Referer': f'https://webbsite.0xmd.com/ccass/choldings.asp?i={issue_id}',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-HK,en;q=0.9,zh-HK;q=0.8,zh;q=0.7',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        try:
            # Random sleep to mimic human behavior
            time.sleep(random.uniform(3.0, 6.0))
            
            resp = requests.get(
                base_url, 
                headers=headers, 
                impersonate="chrome120", 
                timeout=25
            )

            if resp.status_code != 200:
                continue

            # Parsing logic from your Streamlit dashboard
            tables = pd.read_html(io.StringIO(resp.text))
            
            for df in tables:
                if 'Change' in df.columns:
                    # Clean the 'Total' row
                    df = df[df['Name'] != 'Total'].copy()
                    
                    # Convert 'Change' to numeric (cleaning commas)
                    df['Change'] = pd.to_numeric(df['Change'].astype(str).str.replace(',', ''), errors='coerce')
                    
                    # Filter for non-zero moves
                    df = df[df['Change'] != 0].dropna(subset=['Name'])
                    
                    if not df.empty:
                        # Prepare columns for Telegram (Name, Change, Stake Δ %)
                        # We use .head(10) to keep the message concise
                        cols = [c for c in ['Name', 'Change', 'Stake Δ %'] if c in df.columns]
                        return {
                            "date": date_val, 
                            "df": df[cols].head(10)
                        }
        except Exception as e:
            print(f"Error fetching {ticker} for {date_val}: {e}")
            continue
            
    return None

def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram configuration missing.")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": text, 
        "parse_mode": "HTML"
    }
    
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Failed to send Telegram: {e}")

# ==========================================
# 2. MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    hk_now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    msg = f"<b>📊 CCASS Change Alert ({hk_now.strftime('%Y-%m-%d')})</b>\n\n"

    for ticker in STOCKS:
        print(f"Processing {ticker}...")
        result = fetch_ccass_changes(ticker)
        
        msg += f"<b>Stock: {ticker}</b>\n"
        if result:
            msg += f"<i>Settlement Date: {result['date']}</i>\n"
            # Format as a monospaced code block for better table alignment on mobile
            msg += f"<pre>{result['df'].to_string(index=False)}</pre>\n\n"
        else:
            msg += "<i>No movements detected in the last 4 days.</i>\n\n"

    send_telegram(msg)