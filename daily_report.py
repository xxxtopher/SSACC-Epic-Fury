import os, random, time, io, datetime
import pandas as pd
from curl_cffi import requests
from bs4 import BeautifulSoup

STOCKS = ["02497", "02501"]
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def fetch_data(ticker):
    try:
        # Step 1: Resolve Issue ID
        search_url = f"https://webbsite.0xmd.com/dbpub/stocksearch.asp?s={ticker}"
        resp = requests.get(search_url, impersonate="chrome120", timeout=15)
        import re
        match = re.search(r'i=(\d+)', resp.url) or re.search(r'i=(\d+)', resp.text)
        if not match: return None
        issue_id = match.group(1)

        # Step 2: Iterate back through 5 days
        for days_back in range(5):
            check_date = (datetime.datetime.utcnow() + datetime.timedelta(hours=8) - datetime.timedelta(days=days_back)).strftime('%Y-%m-%d')
            url = f"https://webbsite.0xmd.com/ccass/chldchg.asp?i={issue_id}&sort=chngdn&d={check_date}"
            
            time.sleep(random.uniform(2, 4))
            data_resp = requests.get(url, impersonate="chrome120", timeout=20)
            soup = BeautifulSoup(data_resp.text, 'html.parser')
            
            rows = soup.find_all('tr')
            extracted_data = []

            for row in rows:
                cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                if len(cells) < 3: continue

                # Look for rows that have a number with a '+' or '-' or a large integer
                # and don't contain 'Total'
                row_text = " ".join(cells).lower()
                if 'total' in row_text or 'participants' in row_text:
                    continue

                # Attempt to find the "Change" column by looking for numbers that aren't the Ticker
                for i, cell in enumerate(cells):
                    clean_val = cell.replace(',', '').replace('+', '')
                    if clean_val.lstrip('-').isdigit():
                        val = int(clean_val)
                        if val != 0 and abs(val) > 100: # Ignore tiny rounding errors
                            # We found a movement row! 
                            # Usually: Name is Col 0 or 1, Change is Col 2 or 3
                            name = cells[0] if i > 0 else cells[1]
                            stake = cells[-1] if '%' in cells[-1] else "N/A"
                            extracted_data.append({"Name": name[:20], "Change": val, "Stake": stake})
                            break # Move to next row
            
            if extracted_data:
                return {"date": check_date, "df": pd.DataFrame(extracted_data)}
        
        return "NO_CHANGES"
    except Exception as e:
        print(f"Aggressive Scraper Error: {e}")
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