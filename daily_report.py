import os, random, time, io, datetime
import pandas as pd
from curl_cffi import requests
from bs4 import BeautifulSoup

STOCKS = ["02497", "02501"]
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def fetch_data(ticker):
    try:
        # 1. Get Issue ID
        search_url = f"https://webbsite.0xmd.com/dbpub/stocksearch.asp?s={ticker}"
        resp = requests.get(search_url, impersonate="chrome120", timeout=15)
        import re
        match = re.search(r'i=(\d+)', resp.url) or re.search(r'i=(\d+)', resp.text)
        if not match: return None
        issue_id = match.group(1)

        # 2. Check last 5 days
        for days_back in range(5):
            check_date = (datetime.datetime.utcnow() + datetime.timedelta(hours=8) - datetime.timedelta(days=days_back)).strftime('%Y-%m-%d')
            url = f"https://webbsite.0xmd.com/ccass/chldchg.asp?i={issue_id}&sort=chngdn&d={check_date}"
            
            time.sleep(random.uniform(2, 4))
            data_resp = requests.get(url, impersonate="chrome120", timeout=20)
            soup = BeautifulSoup(data_resp.text, 'html.parser')
            
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                if len(rows) < 2: continue
                
                # Check headers for "Name" and "Change"
                headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(['th', 'td'])]
                name_idx = next((i for i, h in enumerate(headers) if 'name' in h), None)
                change_idx = next((i for i, h in enumerate(headers) if 'change' in h and 'stake' not in h), None)
                stake_idx = next((i for i, h in enumerate(headers) if 'stake' in h and 'change' in h), None)

                if name_idx is not None and change_idx is not None:
                    data = []
                    for row in rows[1:]:
                        cols = row.find_all(['td', 'th'])
                        if len(cols) <= max(name_idx, change_idx): continue
                        
                        name = cols[name_idx].get_text(strip=True)
                        change_txt = cols[change_idx].get_text(strip=True).replace(',', '').replace('+', '')
                        stake_txt = cols[stake_idx].get_text(strip=True) if stake_idx is not None else "0%"
                        
                        try:
                            val = float(change_txt) if change_txt else 0
                            if val != 0 and 'total' not in name.lower():
                                data.append({"Name": name[:20], "Change": int(val), "Δ%": stake_txt})
                        except: continue
                    
                    if data:
                        return {"date": check_date, "df": pd.DataFrame(data)}
        return "NO_CHANGES"
    except Exception as e:
        print(f"Error on {ticker}: {e}")
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