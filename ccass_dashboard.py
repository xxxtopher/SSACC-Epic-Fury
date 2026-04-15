import streamlit as st
import pandas as pd
import json
from curl_cffi import requests
import io
import random
import time

# 1. Page Configuration
st.set_page_config(page_title="HK CCASS 1-Day Change", layout="wide")
st.title("📈 CCASS 1-Day Broker Change Tracker")

# 2. Load the Index Mapping
@st.cache_data
def load_index():
    try:
        with open('stocks_index.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading stocks_index.json: {e}")
        return {}

index_data = load_index()

def get_issue_id(ticker):
    target = ticker.zfill(5)
    
    # 1. Check local JSON first (Performance)
    if target in index_data:
        return index_data[target].get('filename')
    
    # 2. If not found, try to "discover" it from the website
    st.info(f"Ticker {target} not in local index. Attempting to discover Issue ID...")
    
    # Webb-site's internal search endpoint
    search_url = f"https://webbsite.0xmd.com/dbpub/stocksearch.asp?s={target}"
    
    try:
        # Use the same stealthy request logic
        resp = requests.get(search_url, impersonate="chrome120", timeout=10)
        
        # We look for the pattern "i=XXXX" in the redirected URL or the page text
        import re
        # Search for digits following "i=" in the response URL or content
        match = re.search(r'i=(\d+)', resp.url) or re.search(r'i=(\d+)', resp.text)
        
        if match:
            new_id = match.group(1)
            # Add to local index so we don't scrape it again this session
            index_data[target] = {"filename": new_id, "ticker": target}
            st.success(f"Found new Issue ID: {new_id} for {target}")
            return new_id
            
    except Exception as e:
        st.error(f"Discovery failed: {e}")
        
    return None

# 4. Scraping Logic
@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_ccass_changes(issue_id, date_val=None):
    browsers = ["chrome", "chrome110", "chrome120", "edge101"]
    base_url = f"https://webbsite.0xmd.com/ccass/chldchg.asp?i={issue_id}&sort=chngdn"
    if date_val:
        base_url += f"&d={date_val}"
    
    headers = {
        'Referer': f'https://webbsite.0xmd.com/ccass/choldings.asp?i={issue_id}',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-HK,en;q=0.9,zh-HK;q=0.8,zh;q=0.7',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Cache-Control': 'max-age=0',
    }

    try:
        time.sleep(random.uniform(3.0, 7.0))
        
        # 1. First Attempt
        try:
            resp = requests.get(
                base_url, 
                headers=headers, 
                impersonate=random.choice(browsers), 
                timeout=25
            )
        except Exception:
            # 2. Fallback Attempt (only runs if 1st fails)
            resp = requests.get(
                base_url, 
                headers=headers, 
                impersonate="chrome", 
                timeout=25
            )

        # 3. Check for 403 before parsing
        if resp.status_code == 403:
            return "403_BLOCK", None

        # 4. Parsing Logic (OUTSIDE the except block so it always runs)
        tables = pd.read_html(io.StringIO(resp.text))
        
        for df in tables:
            if 'Change' in df.columns:
                df = df[df['Name'] != 'Total'].copy()
                df['Change'] = pd.to_numeric(df['Change'].astype(str).str.replace(',', ''), errors='coerce')
                df = df[df['Change'] != 0].dropna(subset=['Name'])
                return "SUCCESS", df
                
        return "NO_TABLE", None

    except Exception as e:
        return f"Error: {str(e)}", None

# 3. Sidebar Input
with st.sidebar:
    st.header("Search Settings")
    with st.form("search_form"):
        ticker_input = st.text_input("Enter HK Stock Code", value="02497")
        target_date = st.date_input("Target Date (Optional)", value=None)
        submit_button = st.form_submit_button("Fetch Data")

# 5. Main Dashboard Logic
# Change this line to check for the button click, not just the presence of text
if submit_button:
    issue_id = get_issue_id(ticker_input)
    
    if not issue_id:
        st.warning(f"Could not find Issue ID for Stock {ticker_input} in JSON.")
    else:
        with st.spinner(f"Fetching latest CCASS data for {ticker_input}..."):
            status, data = fetch_ccass_changes(issue_id, target_date)
            
            if status == "SUCCESS":
                st.subheader(f"Results for Stock {ticker_input} (Issue ID: {issue_id})")
                
                # Filter to requested columns
                cols = ['Name', 'Holding', 'Change', 'Stake %', 'Stake Δ %']
                available_cols = [c for c in cols if c in data.columns]
                
                # Styling function
                def color_change(val):
                    return 'color: red' if val < 0 else 'color: green'

                # Render the styled dataframe
                styled_df = data[available_cols].style.map(color_change, subset=['Change'])
                st.dataframe(styled_df, use_container_width=True, height=600)
                
                st.caption("Note: CCASS data is typically delayed by 2 trading days (T+2).")
            
            elif status == "403_BLOCK": # Match the string returned in your fetch function
                st.error("Access Forbidden (403). The server is blocking the cloud IP. Please try again later.")
            elif status == "NO_TABLE":
                st.info("Connection successful, but no broker changes were found for this date.")
            else:
                st.error(f"Status: {status}")