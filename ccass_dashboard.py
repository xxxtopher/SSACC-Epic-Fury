import streamlit as st
import pandas as pd
import json
from curl_cffi import requests
import io

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

# 3. Sidebar Input
with st.sidebar:
    st.header("Search Settings")
    ticker_input = st.text_input("Enter HK Stock Code (e.g., 2497)", value="02497")
    # Date is optional; leaving it blank pulls the latest available T+2 data
    target_date = st.date_input("Target Date (Optional)", value=None)

# 4. Scraping Logic
def fetch_ccass_changes(issue_id, date_val=None):
    # Construct URL
    base_url = f"https://webbsite.0xmd.com/ccass/chldchg.asp?i={issue_id}&sort=chngdn"
    if date_val:
        base_url += f"&d={date_val}"
    
    headers = {
        'Referer': f'https://webbsite.0xmd.com/ccass/choldings.asp?i={issue_id}',
    }

    try:
        resp = requests.get(base_url, headers=headers, impersonate="chrome120", timeout=20)
        
        if resp.status_code == 403:
            return "403_ERROR", None
        
        # REMOVED engine='lxml' to support older Pandas versions
        tables = pd.read_html(io.StringIO(resp.text))
        
        for df in tables:
            if 'Change' in df.columns:
                df = df[df['Name'] != 'Total'].copy()
                # Ensure Change is string before replacing to avoid errors
                df['Change'] = pd.to_numeric(df['Change'].astype(str).str.replace(',', ''), errors='coerce')
                df = df[df['Change'] != 0].dropna(subset=['Name'])
                return "SUCCESS", df
                
        return "NO_TABLE", None
    except Exception as e:
        return str(e), None

# 5. Main Dashboard Logic
if ticker_input:
    issue_id = get_issue_id(ticker_input)
    
    if not issue_id:
        st.warning(f"Could not find Issue ID for Stock {ticker_input} in JSON.")
    else:
        with st.spinner(f"Fetching latest CCASS data for {ticker_input}..."):
            status, data = fetch_ccass_changes(issue_id, target_date)
            
            if status == "SUCCESS":
                st.subheader(f"Results for Stock {ticker_input} (Issue ID: {issue_id})")
                
                # Highlight columns
                cols = ['Name', 'Holding', 'Change', 'Stake %', 'Stake Δ %']
                available_cols = [c for c in cols if c in data.columns]
                
                # Apply styling to make changes easier to see
                def color_change(val):
                    color = 'red' if val < 0 else 'green'
                    return f'color: {color}'

                styled_df = data[available_cols].style.map(color_change, subset=['Change'])
                
                st.dataframe(styled_df, use_container_width=True, height=600)
                
                st.caption("Note: CCASS data is typically delayed by 2 trading days (T+2).")
            
            elif status == "403_ERROR":
                st.error("Access Forbidden (403). The server is blocking the script. Try again in a few minutes.")
            elif status == "NO_TABLE":
                st.info("Connection successful, but no broker changes were found for this date.")
            else:
                st.error(f"Error: {status}")