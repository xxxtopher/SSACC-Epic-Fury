import os
import random
import time
import io
import datetime
import pandas as pd
from curl_cffi import requests
from bs4 import BeautifulSoup

# Config
STOCKS = ["02497", "02501"]
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def fetch_data(ticker):
    # Search for Issue ID
    search_url = f"https://webbsite.0xmd.com/dbpub/stocksearch.asp?s={ticker}"
    try:
        resp = requests.get(search_url, impersonate="chrome120", timeout=15)
        import re
        match = re.search(r'i=(\d+)', resp.url) or re.search(r'i=(\d+)', resp.text)
        if not match: return None
        issue_id = match.group(1)

        # Look back 5 days
        for days_back in range(5):
            check_date = (datetime.datetime.utcnow() + datetime.timedelta(hours=8) - datetime.timedelta(days=days_back)).strftime('%Y-%m-%d')
            url = f"https://webbsite.0xmd.com/ccass/chldchg.asp?i={issue_id}&sort=chngdn&d={check_date}"
            
            time.sleep(random.uniform(2, 4))
            data_resp = requests.get(url, impersonate="chrome120", timeout=20)
            soup = BeautifulSoup(data_resp.text, 'html.parser')
            
            # Find all tables
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                if not rows: continue
                
                # Get headers from the first row that has <th> or <td>
                headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(['th', 'td'])]
                
                # We need a table with 'name' and something containing 'change'
                name_idx = next((i for i, h in enumerate(headers) if 'name' in h), None)
                change_idx = next((i for i, h in enumerate(headers) if 'change' in h and 'stake' not in h), None)
                stake_change_idx = next((i for i, h in enumerate(headers) if 'stake' in h and 'change' in h), None)

                if name_idx is not None and change_idx is not None:
                    data = []
                    for row in rows[1:]:
                        cols = row.find_all(['td', 'th'])
                        if len(cols) <= max(name_idx, change_idx): continue
                        
                        name = cols[name_idx].get_text(strip=True)
                        # Remove commas, plus signs, and whitespace
                        change_text = cols[change_idx].get_text(strip=True).replace(',', '').replace('+', '')
                        stake_text = cols[stake_change_idx].get_text(strip=True) if stake_change_idx is not None else "0"

                        try:
                            change_val = float(change_text) if change_text else 0
                        except ValueError:
                            change_val = 0
                            
                        # Ignore 'Total' and rows with 0 change
                        if change_val != 0 and 'total' not in name.lower() and 'participants' not in name.lower():
                            data.append({
                                "Name": name[:25], # Truncate for mobile
                                "Change": int(change_val),
                                "Stake Δ": stake_text
                            })
                    
                    if data:
                        df = pd.DataFrame(data)
                        return {"date": check_date, "df": df}
        
        return "NO_CHANGES"
    except Exception as e:
        print(f"Scraper Error for {ticker}: {e}")
        return None

def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    # Break long messages to avoid Telegram limits
    if len(text) > 4000: text = text[:3900] + "..."
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"})

# Execution
hk_now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
final_message = f"<b>📊 CCASS Report ({hk_now.strftime('%Y-%m-%d %H:%M')})</b>\n\n"

for stock in STOCKS:
    result = fetch_data(stock)
    final_message += f"<b>Stock: {stock}</b>\n"
    if isinstance(result, dict):
        final_message += f"<i>Date: {result['date']}</i>\n"
        final_message += f"<pre>{result['df'].to_string(index=False)}</pre>\n\n"
    else:
        final_message += "<i>No significant moves (Checked 5 days).</i>\n\n"

send_telegram(final_message)