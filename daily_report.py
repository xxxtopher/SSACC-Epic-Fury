import os, random, time, io, datetime, pandas as pd
from curl_cffi import requests
from bs4 import BeautifulSoup

# HARDCODED MAPPING: Find these IDs once in your browser and put them here
# You can find these IDs by looking at the URL when you view a stock on the dashboard
ISSUE_MAP = {
    "02497": "34573", # Example: Replace with the actual ID from your browser URL
    "02501": "34574"  # Replace with the actual ID
}

STOCKS = ["02497", "02501"]
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def fetch_data(ticker):
    issue_id = ISSUE_MAP.get(ticker)
    if not issue_id:
        return f"Error: Could not resolve issue ID for {ticker}"

    # Use the same logic as your working dashboard
    for days_back in range(3):
        check_date = (datetime.datetime.utcnow() + datetime.timedelta(hours=8) - datetime.timedelta(days=days_back)).strftime('%Y-%m-%d')
        url = f"https://webbsite.0xmd.com/ccass/chldchg.asp?i={issue_id}&sort=chngdn&d={check_date}"
        
        headers = {
            'Referer': f'https://webbsite.0xmd.com/ccass/choldings.asp?i={issue_id}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        try:
            time.sleep(random.uniform(2, 4))
            resp = requests.get(url, headers=headers, impersonate="chrome120", timeout=20)
            
            # Use BeautifulSoup to find the specific table
            soup = BeautifulSoup(resp.text, 'html.parser')
            table = soup.find('table', {'class': None}) # The Webb-site tables often have no class
            
            if table:
                df = pd.read_html(io.StringIO(str(table)))[0]
                # ... [Keep your existing cleanup/filtering logic here] ...
                return {"date": check_date, "df": df}
        except Exception:
            continue
    return None