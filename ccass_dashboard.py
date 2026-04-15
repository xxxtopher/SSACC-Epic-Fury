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
    # Check if ticker is a direct key
    if target in index_data:
        return index_data[target].get('filename')
    # Search within values if keys are "ID-XXXX"
    for key, val in index_data.items():
        if isinstance(val, dict) and val.get('ticker') == target:
            return val.get('filename')
    return None

# 4. Scraping Logic
@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_ccass_changes(issue_id, date_val=None):
    # Expanded browser list for better rotation
    browsers = ["chrome", "chrome110", "chrome120", "edge101"]
    
    # Webb-site change URL
    base_url = f"https://webbsite.0xmd.com/ccass/chldchg.asp?i={issue_id}&sort=chngdn"
    if date_val:
        base_url += f"&d={date_val}"
    
    headers = {
        'Referer': f'https://webbsite.0xmd.com/ccass/choldings.asp?i={issue_id}',
        'Accept-Language': 'en-HK,en;q=0.9,zh-HK;q=0.8,zh;q=0.7',
    }

    try:
        # Random sleep to mimic human browsing (2 to 5 seconds)
        time.sleep(random.uniform(2.0, 5.0))

        # Select a browser and use a fallback if one fails
        selected_browser = random.choice(browsers) 
        
        # Use curl_cffi to bypass TLS fingerprinting (403 fix)
        resp = requests.get(
            base_url, 
            headers=headers, 
            impersonate=random.choice(browsers), 
            timeout=25
        )
    except Exception:
            # Fallback to standard 'chrome' if a specific version fails
            resp = requests.get(
                base_url, 
                headers=headers, 
                impersonate="chrome", 
                timeout=25
            )
        
        if resp.status_code == 403:
            return "403_BLOCK", None
        
        # Parse all tables on the page
        # Using io.StringIO to avoid future warnings from Pandas
        tables = pd.read_html(io.StringIO(resp.text))
        
        for df in tables:
            # Check for the correct data table
            if 'Change' in df.columns:
                # 1. Drop the summary total row
                df = df[df['Name'] != 'Total'].copy()
                
                # 2. Clean numeric data
                df['Change'] = pd.to_numeric(df['Change'].astype(str).str.replace(',', ''), errors='coerce')
                
                # 3. Filter for active moves and valid names
                df = df[df['Change'] != 0].dropna(subset=['Name'])
                
                return "SUCCESS", df
                
        return "NO_TABLE", None

    except Exception as e:
        # Return the error string so Streamlit can display it
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