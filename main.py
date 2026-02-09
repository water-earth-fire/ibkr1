import requests
import time
import xml.etree.ElementTree as ET
import pandas as pd
import os

# 1. Configuration (Loaded from GitHub Secrets)
IB_TOKEN = os.getenv("IB_TOKEN")
QUERY_ID = os.getenv("QUERY_ID")
TG_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def fetch_ibkr_xml():
    base_url = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
    
    # Step 1: Ask IBKR to prepare the report
    request_url = f"{base_url}/SendRequest?t={IB_TOKEN}&q={QUERY_ID}&v=3"
    r = requests.get(request_url)
    root = ET.fromstring(r.content)
    
    if root.find("Status").text == "Success":
        ref_code = root.find("ReferenceCode").text
        print(f"Report requested (Ref: {ref_code}). Waiting 30s for file to be ready...")
        time.sleep(30) # Crucial: Reports aren't instant
        
        # Step 2: Download the report
        download_url = f"{base_url}/GetStatement?t={IB_TOKEN}&q={ref_code}&v=3"
        report_data = requests.get(download_url)
        return report_data.content
    else:
        print(f"Error: {root.find('ErrorMessage').text}")
        return None

def process_and_send(xml_content):
    root = ET.fromstring(xml_content)
    
    # 1. Find NAV
    nav_node = root.find(".//NetAssetValueNAVInBase")
    total_nav = float(nav_node.get("total")) if nav_node is not None else 0.0

    # 2. Extract Contributors
    perf_data = []
    # Using the exact tag from your IBKR configuration
    for node in root.findall(".//RealizedUnrealizedPerformanceSummaryInBase"):
        symbol = node.get('symbol')
        if symbol and symbol != 'Total':
            realized = float(node.get('totalRealizedPnl') or 0)
            unrealized = float(node.get('totalUnrealizedPnl') or 0)
            perf_data.append({'symbol': symbol, 'pnl': realized + unrealized})

    df = pd.DataFrame(perf_data)
    total_pnl = df['pnl'].sum()
    
    # 3. Format Message
    msg = f"📉 *Daily IBKR Report*\n━━━━━━━━━━━━━━━\n"
    msg += f"🏦 *NAV:* ${total_nav:,.2f}\n"
    msg += f"💰 *PnL:* {'+' if total_pnl > 0 else ''}${total_pnl:,.2f}\n\n"
    
    msg += "*Top Contributors:*\n"
    for _, r in df.nlargest(3, 'pnl').iterrows():
        msg += f"• {r['symbol']}: +${r['pnl']:,.2f}\n"

    msg += "\n*Top Detractors:*\n"
    for _, r in df.nsmallest(3, 'pnl').iterrows():
        msg += f"• {r['symbol']}: -${abs(r['pnl']):,.2f}\n"

    # 4. Send to Telegram
    tg_url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(tg_url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

# Execution logic
xml = fetch_ibkr_xml()
if xml:
    process_and_send(xml)
