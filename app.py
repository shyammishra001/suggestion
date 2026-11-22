# app.py - V14 - INDstocks API Docs ke hisab se FIXED - Option Chain ab IND se aayega
# Docs: https://api-docs.indstocks.com/getting-started/ Step 2, Step 3 + https://api-docs.indstocks.com/utility/ Option Chain
# Galti jo pehle thi:
# 1. URL galat tha - api.indmoney.com/api/option-chain - Sahi hai api.indstocks.com/market/option-chain
# 2. Header galat tha - Bearer lagaya tha - Docs me sirf {'Authorization': access_token} hai, Bearer NAHI
# 3. Param galat tha - symbol bheja tha - Docs me exchange + segment + underlying-scrip (SECURITY_ID) + expiry YYYY-MM-DD + strike_count chahiye
# 4. Response galat samjha tha - list samjha tha - Docs me data.strikes dict hai, strike se keyed hai, har strike me ce/pe hai
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import sqlite3
import os
import requests
import base64
import io

st.set_page_config(page_title="Scanner - INDstocks FIXED", layout="wide")

CAPITAL = 5000
DB_FILE = "trades.db"
CSV_FILE = "all_trades.csv"
GITHUB_CSV_PATH = "trades_diary/all_trades.csv"
IND_BASE = "https://api.indstocks.com"

try:
    TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT = str(st.secrets.get("TELEGRAM_CHAT_ID", ""))
except:
    TELEGRAM_TOKEN = ""
    TELEGRAM_CHAT = ""

MARKET_STOCKS = {
    "RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS", "INFY": "INFY.NS", "HDFCBANK": "HDFCBANK.NS", "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS", "TATAMOTORS": "TATAMOTORS.NS", "TATASTEEL": "TATASTEEL.NS", "M&M": "M&M.NS", "TITAN": "TITAN.NS",
    "ADANIENT": "ADANIENT.NS", "ADANIPORTS": "ADANIPORTS.NS", "AXISBANK": "AXISBANK.NS", "KOTAKBANK": "KOTAKBANK.NS", "LT": "LT.NS",
    "MARUTI": "MARUTI.NS", "ONGC": "ONGC.NS", "POWERGRID": "POWERGRID.NS", "NTPC": "NTPC.NS", "COALINDIA": "COALINDIA.NS",
    "BPCL": "BPCL.NS", "HINDALCO": "HINDALCO.NS", "JSWSTEEL": "JSWSTEEL.NS", "BAJFINANCE": "BAJFINANCE.NS", "BHARTIARTL": "BHARTIARTL.NS",
    "ITC": "ITC.NS", "HCLTECH": "HCLTECH.NS", "WIPRO": "WIPRO.NS", "TECHM": "TECHM.NS", "SUNPHARMA": "SUNPHARMA.NS",
    "DRREDDY": "DRREDDY.NS", "CIPLA": "CIPLA.NS", "DIVISLAB": "DIVISLAB.NS", "EICHERMOT": "EICHERMOT.NS", "HEROMOTOCO": "HEROMOTOCO.NS",
    "GRASIM": "GRASIM.NS", "ULTRACEMCO": "ULTRACEMCO.NS", "SHRIRAMFIN": "SHRIRAMFIN.NS", "MUTHOOTFIN": "MUTHOOTFIN.NS", "APOLLOHOSP": "APOLLOHOSP.NS",
    "TATACONSUM": "TATACONSUM.NS", "NESTLEIND": "NESTLEIND.NS", "BRITANNIA": "BRITANNIA.NS", "HINDUNILVR": "HINDUNILVR.NS", "ASIANPAINT": "ASIANPAINT.NS",
    "KALYANJIL": "KALYANKJIL.NS", "UNIONBANK": "UNIONBANK.NS", "PNB": "PNB.NS", "CANBK": "CANBK.NS", "FEDERALBNK": "FEDERALBNK.NS",
    "IDFCFIRSTB": "IDFCFIRSTB.NS", "BEL": "BEL.NS", "HAL": "HAL.NS", "TATAPOWER": "TATAPOWER.NS", "IRFC": "IRFC.NS",
    "RVNL": "RVNL.NS", "IRCTC": "IRCTC.NS", "MAZAGON": "MAZDOCK.NS", "COCHINSHIP": "COCHINSHIP.NS", "NHPC": "NHPC.NS",
    "SJVN": "SJVN.NS", "HUDCO": "HUDCO.NS", "NBCC": "NBCC.NS", "YESBANK": "YESBANK.NS", "SUZLON": "SUZLON.NS",
    "IDEA": "IDEA.NS", "PAYTM": "PAYTM.NS", "ZOMATO": "ETERNAL.NS", "NYKAA": "NYKAA.NS", "POLICYBZR": "POLICYBZR.NS",
    "DMART": "DMART.NS", "TRENT": "TRENT.NS", "JUBLFOOD": "JUBLFOOD.NS", "INDIGO": "INDIGO.NS",
    "BAJAJFINSV": "BAJAJFINSV.NS", "BAJAJ-AUTO": "BAJAJ-AUTO.NS", "SBILIFE": "SBILIFE.NS", "HDFCLIFE": "HDFCLIFE.NS",
    "INDUSINDBK": "INDUSINDBK.NS", "BANKBARODA": "BANKBARODA.NS", "AUBANK": "AUBANK.NS", "MPHASIS": "MPHASIS.NS", "PERSISTENT": "PERSISTENT.NS",
    "COFORGE": "COFORGE.NS", "LTIM": "LTIM.NS", "VEDL": "VEDL.NS", "JINDALSTEL": "JINDALSTEL.NS", "SAIL": "SAIL.NS",
    "NMDC": "NMDC.NS", "GAIL": "GAIL.NS", "PETRONET": "PETRONET.NS", "IOC": "IOC.NS", "HINDPETRO": "HINDPETRO.NS",
    "AMBUJACEM": "AMBUJACEM.NS", "ACC": "ACC.NS", "SHREECEM": "SHREECEM.NS", "DLF": "DLF.NS", "GODREJPROP": "GODREJPROP.NS",
}
LOT_SIZES = {"RELIANCE": 250, "TCS": 175, "INFY": 800, "HDFCBANK": 550, "ICICIBANK": 1375, "SBIN": 1500, "TATAMOTORS": 1400, "TATASTEEL": 5500, "M&M": 800, "TITAN": 350, "ADANIENT": 300, "ADANIPORTS": 1000, "AXISBANK": 1200, "KOTAKBANK": 800, "LT": 300, "MARUTI": 50, "ONGC": 3850, "POWERGRID": 3600, "NTPC": 5700, "COALINDIA": 2100, "BPCL": 1800, "HINDALCO": 2600, "JSWSTEEL": 1350, "BAJFINANCE": 125, "BHARTIARTL": 950, "ITC": 1600, "HCLTECH": 700, "WIPRO": 3000, "TECHM": 900, "SUNPHARMA": 700, "DRREDDY": 125, "CIPLA": 650, "DIVISLAB": 200, "EICHERMOT": 175, "HEROMOTOCO": 300, "GRASIM": 250, "ULTRACEMCO": 100, "SHRIRAMFIN": 300, "MUTHOOTFIN": 500, "APOLLOHOSP": 125, "TATACONSUM": 1000, "NESTLEIND": 10, "BRITANNIA": 100, "HINDUNILVR": 300, "ASIANPAINT": 400, "KALYANJIL": 3200, "UNIONBANK": 8000, "PNB": 8000, "CANBK": 7000, "FEDERALBNK": 10000, "IDFCFIRSTB": 10000, "BEL": 4000, "HAL": 150, "TATAPOWER": 3750, "IRFC": 7500, "RVNL": 5000, "IRCTC": 1250, "MAZAGON": 150, "COCHINSHIP": 300, "NHPC": 7000, "SJVN": 8000, "HUDCO": 4000, "NBCC": 6000, "YESBANK": 20000, "SUZLON": 10000, "IDEA": 20000, "PAYTM": 800, "ZOMATO": 3000, "NYKAA": 4000, "POLICYBZR": 500, "DMART": 200, "TRENT": 200, "JUBLFOOD": 500, "INDIGO": 150, "BAJAJFINSV": 500, "BAJAJ-AUTO": 125, "SBILIFE": 750, "HDFCLIFE": 1100, "INDUSINDBK": 800, "BANKBARODA": 4000, "AUBANK": 1000, "MPHASIS": 300, "PERSISTENT": 100, "COFORGE": 100, "LTIM": 100, "VEDL": 3000, "JINDALSTEL": 800, "SAIL": 8000, "NMDC": 8000, "GAIL": 4000, "PETRONET": 3000, "IOC": 4000, "HINDPETRO": 2000, "AMBUJACEM": 1000, "ACC": 300, "SHREECEM": 25, "DLF": 1500, "GODREJPROP": 300}
# Docs se pakka wale SECURITY_ID - RELIANCE 2885, TCS 11536 docs me likha hai
KNOWN_SCRIP = {"RELIANCE": "2885", "TCS": "11536", "HDFCBANK": "1333", "INFY": "1594", "ICICIBANK": "4963", "SBIN": "3045", "ITC": "1660", "LT": "11483", "TITAN": "3506", "TATAMOTORS": "3846", "ONGC": "2475", "NTPC": "2882", "POWERGRID": "2562", "TATASTEEL": "3499", "HINDALCO": "1363", "JSWSTEEL": "11723", "BAJFINANCE": "317", "BHARTIARTL": "10604", "MARUTI": "10999", "SUNPHARMA": "3351", "ADANIENT": "25", "ADANIPORTS": "15083", "AXISBANK": "5900", "KOTAKBANK": "1922", "M&M": "2031", "GRASIM": "1319", "ULTRACEMCO": "11532", "HCLTECH": "7229", "WIPRO": "3787", "TECHM": "13538", "CIPLA": "694", "DIVISLAB": "10940", "EICHERMOT": "5053", "HEROMOTOCO": "1348", "COALINDIA": "20374", "BPCL": "526", "VEDL": "3063", "DLF": "14732", "BEL": "383", "HAL": "11890", "TATAPOWER": "3426", "IRCTC": "13611", "DMART": "5097", "TRENT": "1964", "INDIGO": "11184", "BAJAJFINSV": "166", "BAJAJ-AUTO": "16669", "SBILIFE": "21808", "HDFCLIFE": "467", "INDUSINDBK": "5258", "BANKBARODA": "4668", "GAIL": "1232", "IOC": "1624", "NMDC": "2029", "SAIL": "2964", "JINDALSTEL": "673", "MPHASIS": "1106", "PERSISTENT": "12355", "COFORGE": "11543", "LTIM": "17818", "AMBUJACEM": "216", "ACC": "35", "SHREECEM": "3105", "GODREJPROP": "17875"}

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "show_diary" not in st.session_state:
    st.session_state.show_diary = False
if "scan_df" not in st.session_state:
    st.session_state.scan_df = None
if "news_data" not in st.session_state:
    st.session_state.news_data = None
if "indices_data" not in st.session_state:
    st.session_state.indices_data = None
if "auto_sent" not in st.session_state:
    st.session_state.auto_sent = False
if "indmoney_connected" not in st.session_state:
    st.session_state.indmoney_connected = False
if "indmoney_debug" not in st.session_state:
    st.session_state.indmoney_debug = ""

def safe_float(val, default=0.0):
    try:
        if val is None:
            return float(default)
        if isinstance(val, pd.Series):
            if len(val) == 0:
                return float(default)
            val = val.iloc[0]
        if isinstance(val, np.ndarray):
            if val.size == 0:
                return float(default)
            val = val.flat[0]
        if isinstance(val, (list, tuple)):
            if len(val) == 0:
                return float(default)
            val = val[0]
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return float(default)
        return float(f)
    except:
        return float(default)

def safe_int(val, default=0):
    try:
        return int(safe_float(val, default))
    except:
        return int(default)

# ---------- INDstocks API - Docs ke hisab se EXACT ----------
def ind_headers(token):
    # Docs Step 2: headers = {'Authorization': access_token} - Bearer NAHI lagana
    return {"Authorization": token.strip(), "Content-Type": "application/json"}

def ind_test_profile(token):
    # Step 2: GET /user/profile - Token sahi hai ya expire ho gaya, ye yahan se pata chalega
    try:
        r = requests.get(f"{IND_BASE}/user/profile", headers=ind_headers(token), timeout=10)
        if r.status_code == 200:
            d = r.json().get("data", {})
            return True, f"Connected - {d.get('first_name','')} {d.get('last_name','')}"
        else:
            return False, f"Token Fail - Status {r.status_code} - {r.text[:300]} - Token 24 ghante me expire hota hai, naya banao"
    except Exception as e:
        return False, f"Connect nahi hua - {e}"

def ind_get_expiries(underlying, token):
    # Docs Contracts: GET /market/instruments/expiries?underlying=NIFTY&segment=DERIVATIVE - list ascending me aati hai, pehli wali Nearest hai
    try:
        r = requests.get(f"{IND_BASE}/market/instruments/expiries", headers=ind_headers(token), params={"underlying": underlying, "segment": "DERIVATIVE"}, timeout=10)
        if r.status_code == 200:
            data = r.json().get("data", [])
            if data:
                return data, ""
            return [], "Expiries khali aayi"
        return [], f"Expiries Fail - {r.status_code} - {r.text[:300]}"
    except Exception as e:
        return [], f"Expiries Error - {e}"

def ind_get_scrip(symbol, token):
    # Docs Instruments: GET /market/instruments?source=equity - CSV aati hai, usme SYMBOL_NAME se SECURITY_ID nikalna hai
    # Pehle KNOWN map se try karo, nahi mila to CSV se nikalo
    if symbol in KNOWN_SCRIP:
        return KNOWN_SCRIP[symbol], "KNOWN"
    try:
        r = requests.get(f"{IND_BASE}/market/instruments", headers=ind_headers(token), params={"source": "equity"}, timeout=20)
        if r.status_code == 200:
            df = pd.read_csv(io.StringIO(r.text))
            # Columns: SECURITY_ID, SYMBOL_NAME, TRADING_SYMBOL
            col_sym = "SYMBOL_NAME" if "SYMBOL_NAME" in df.columns else df.columns[0]
            col_id = "SECURITY_ID" if "SECURITY_ID" in df.columns else df.columns[2]
            match = df[df[col_sym].astype(str).str.upper() == symbol.upper()]
            if not match.empty:
                return str(match.iloc[0][col_id]), "CSV"
            # TRADING_SYMBOL se bhi try karo
            if "TRADING_SYMBOL" in df.columns:
                match2 = df[df["TRADING_SYMBOL"].astype(str).str.upper() == symbol.upper()]
                if not match2.empty:
                    return str(match2.iloc[0][col_id]), "CSV"
        return "", f"CSV me {symbol} nahi mila - Status {r.status_code}"
    except Exception as e:
        return "", f"Scrip Error - {e}"

def ind_get_option_chain(symbol, token):
    # Docs Option Chain: GET /market/option-chain?exchange=NSE&segment=EQUITY&underlying-scrip=2885&expiry=YYYY-MM-DD&strike_count=25
    # Response: data.strikes = { "24450": {"ce": {...last_price...}, "pe": {...}} } - dict hai, list NAHI
    if not token or len(token.strip()) < 10:
        return pd.DataFrame(), "Token nahi diya", "", "", ""
    # 1. Expiry nikalo - Nearest wali
    expiries, err_exp = ind_get_expiries(symbol, token)
    if not expiries:
        return pd.DataFrame(), f"Expiry nahi mili - {err_exp}", "", "", ""
    expiry_yyyy_mm_dd = str(expiries[0])  # YYYY-MM-DD format me hi aati hai
    # 2. Scrip nikalo
    scrip, scrip_src = ind_get_scrip(symbol, token)
    if not scrip:
        return pd.DataFrame(), f"Scrip nahi mila - {scrip_src}", expiry_yyyy_mm_dd, "", ""
    # 3. Option Chain mango - strike_count 25 matlab ATM ke dono taraf 25-25 = 51 strikes
    try:
        params = {"exchange": "NSE", "segment": "EQUITY", "underlying-scrip": scrip, "expiry": expiry_yyyy_mm_dd, "strike_count": 25}
        r = requests.get(f"{IND_BASE}/market/option-chain", headers=ind_headers(token), params=params, timeout=15)
        if r.status_code != 200:
            return pd.DataFrame(), f"IND Fail - Status {r.status_code} - {r.text[:500]}", expiry_yyyy_mm_dd, scrip, ""
        j = r.json()
        data = j.get("data", {})
        strikes_dict = data.get("strikes", {})
        underlying_ltp = safe_float(data.get("underlying_ltp", 0))
        if not strikes_dict:
            return pd.DataFrame(), f"IND se strikes khali aaye - {str(j)[:400]}", expiry_yyyy_mm_dd, scrip, str(underlying_ltp)
        rows = []
        for strike_str, legs in strikes_dict.items():
            try:
                strike = safe_int(float(strike_str))
                ce = legs.get("ce", {}) if isinstance(legs, dict) else {}
                pe = legs.get("pe", {}) if isinstance(legs, dict) else {}
                rows.append({
                    "Strike": strike,
                    "CE Premium": safe_float(ce.get("last_price", 0)),
                    "PE Premium": safe_float(pe.get("last_price", 0)),
                    "CE OI": safe_int(ce.get("oi", 0)),
                    "PE OI": safe_int(pe.get("oi", 0)),
                    "CE IV": safe_float(ce.get("iv", 0)),
                    "PE IV": safe_float(pe.get("iv", 0)),
                    "CE Delta": safe_float((ce.get("greeks", {}) or {}).get("delta", 0)),
                    "PE Delta": safe_float((pe.get("greeks", {}) or {}).get("delta", 0)),
                    "CE Bid": safe_float(ce.get("top_bid_price", 0)),
                    "CE Ask": safe_float(ce.get("top_ask_price", 0)),
                    "PE Bid": safe_float(pe.get("top_bid_price", 0)),
                    "PE Ask": safe_float(pe.get("top_ask_price", 0)),
                })
            except:
                continue
        df = pd.DataFrame(rows).sort_values("Strike").reset_index(drop=True)
        if df.empty:
            return pd.DataFrame(), "Parse ke baad khali", expiry_yyyy_mm_dd, scrip, str(underlying_ltp)
        return df, f"IND SE AAYA - {len(df)} strikes", expiry_yyyy_mm_dd, scrip, str(underlying_ltp)
    except Exception as e:
        return pd.DataFrame(), f"Option Chain Error - {e}", expiry_yyyy_mm_dd, scrip, ""

def ind_get_quote(symbol, token):
    # Docs Step 3: GET /market/quotes/full?scrip-codes=NSE_2885 - LTP check ke liye
    try:
        scrip, _ = ind_get_scrip(symbol, token)
        if not scrip:
            return 0, "Scrip nahi"
        r = requests.get(f"{IND_BASE}/market/quotes/full", headers=ind_headers(token), params={"scrip-codes": f"NSE_{scrip}"}, timeout=10)
        if r.status_code == 200:
            data = r.json().get("data", {})
            for k, v in data.items():
                return safe_float(v.get("live_price", 0)), "OK"
        return 0, f"Quote Fail {r.status_code}"
    except Exception as e:
        return 0, str(e)

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": str(TELEGRAM_CHAT), "text": message}, timeout=12)
        return r.status_code == 200
    except:
        return False

def send_top5(top5_df, expiry_str):
    msg = f"TOP 5 - {datetime.now().strftime('%d %b %Y %H:%M')}\nExpiry: {expiry_str} | Capital: Rs 5000\n------------------------\n"
    for i, (_, row) in enumerate(top5_df.iterrows(), start=1):
        stock_name = str(row.get("Stock", ""))
        ltp = safe_float(row.get("LTP", 0)); vwap = safe_float(row.get("VWAP", 0)); orb_high = safe_float(row.get("ORB High", 0)); orb_low = safe_float(row.get("ORB Low", 0)); prob = safe_float(row.get("Probability %", 0)); gap = safe_float(row.get("Gap %", 0)); vol = safe_float(row.get("Vol x", 0))
        direction = str(row.get("Direction", "")); pattern = str(row.get("Pattern", "")); movement = str(row.get("Movement", ""))
        if ltp > vwap:
            vwap_pos = f"VWAP ({vwap:.1f}) se UPAR"
        else:
            vwap_pos = f"VWAP ({vwap:.1f}) se NEECHE"
        if ltp > orb_high:
            orb_pos = f"ORB High ({orb_high:.1f}) ke UPAR - Breakout"
        elif ltp < orb_low:
            orb_pos = f"ORB Low ({orb_low:.1f}) ke NEECHE - Breakdown"
        else:
            orb_pos = f"ORB ke ANDAR ({orb_low:.1f} - {orb_high:.1f})"
        msg += f"{i}. {stock_name} - LTP Rs {ltp:.1f} - {direction} - Prob {prob:.0f}%\n   Pattern: {pattern}\n   Kahan pe hai: {vwap_pos}, {orb_pos}\n   Movement: {movement}\n   Gap: {gap:.2f}% | Vol: {vol:.1f}x\n------------------------\n"
    return send_telegram(msg)

def send_strike(stock, strike, opt_type, entry, sl, target, cost, lot, expiry_str, movement):
    entry_f = safe_float(entry); sl_f = safe_float(sl); target_f = safe_float(target); cost_f = safe_float(cost); lot_f = safe_float(lot)
    max_profit = round((target_f - entry_f) * lot_f, 0); max_loss = round((entry_f - sl_f) * lot_f, 0)
    msg = f"STRIKE SELECTED - {stock}\n------------------------\nStock: {stock}\nStrike: {safe_int(strike)} {opt_type}\nExpiry: {expiry_str}\nEntry: Rs {entry_f}\nStop Loss: Rs {sl_f}\nTarget: Rs {target_f}\n1 Lot Qty: {safe_int(lot_f)}\n1 Lot Cost: Rs {cost_f:.0f}\nMax Profit: Rs {max_profit:.0f}\nMax Loss: Rs {max_loss:.0f}\nMovement: {movement}\nTime: {datetime.now().strftime('%H:%M:%S')}"
    return send_telegram(msg)

def check_all_strikes(chain_df, lot, ltp, direction, budget=5000):
    if chain_df is None or chain_df.empty:
        return pd.DataFrame(), None
    lot_f = safe_float(lot); ltp_f = safe_float(ltp)
    opt_col = "CE Premium" if "BULLISH" in str(direction) else "PE Premium" if "BEARISH" in str(direction) else "CE Premium"
    opt_type = "CE" if "BULLISH" in str(direction) else "PE" if "BEARISH" in str(direction) else "CE"
    results = []
    for _, r in chain_df.iterrows():
        strike = safe_int(r.get("Strike", 0)); prem = safe_float(r.get(opt_col, 0))
        if prem <= 0:
            continue
        cost = round(prem * lot_f, 0); fits = cost <= budget
        results.append({"Strike": strike, "Type": opt_type, "Premium": prem, "Lot Qty": safe_int(lot_f), "1 Lot Cost": cost, "Rs 5000 me?": "✅ HO JAYEGA" if fits else "❌ NAHI HOGA", "ATM se Door": round(abs(strike - ltp_f), 1), "Fits": fits, "OI": safe_int(r.get("CE OI", 0) if opt_type == "CE" else r.get("PE OI", 0)), "IV": safe_float(r.get("CE IV", 0) if opt_type == "CE" else r.get("PE IV", 0))})
    df = pd.DataFrame(results).sort_values("ATM se Door") if results else pd.DataFrame()
    best = df[df["Fits"] == True].sort_values("ATM se Door").iloc[0] if not df.empty and (df["Fits"] == True).any() else None
    return df, best

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, time TEXT, symbol TEXT, strike INTEGER, opt_type TEXT, entry REAL, sl REAL, target REAL, qty_lots INTEGER, qty_total REAL, capital_used REAL, risk REAL, status TEXT, exit_price REAL, pnl REAL, exit_time TEXT, reason TEXT, conditions TEXT)")
    conn.commit(); conn.close()

def save_trade(trade):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO trades (date,time,symbol,strike,opt_type,entry,sl,target,qty_lots,qty_total,capital_used,risk,status,exit_price,pnl,exit_time,reason,conditions) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    (trade['date'], trade['time'], trade['symbol'], trade['strike'], trade['opt_type'], trade['entry'], trade['sl'], trade['target'], trade['qty_lots'], trade['qty_total'], trade['capital_used'], trade['risk'], trade['status'], None, None, None, trade['reason'], trade.get('conditions','')))
    conn.commit(); conn.close()
    conn2 = sqlite3.connect(DB_FILE)
    df2 = pd.read_sql("SELECT * FROM trades", conn2)
    df2.to_csv(CSV_FILE, index=False); conn2.close()
    if st.session_state.get("github_pat") and st.session_state.get("github_repo"):
        try:
            csv_text = df2.to_csv(index=False)
            content_b64 = base64.b64encode(csv_text.encode()).decode()
            headers = {"Authorization": f"token {st.session_state.github_pat}", "Accept": "application/vnd.github+json"}
            url = f"https://api.github.com/repos/{st.session_state.github_repo}/contents/{GITHUB_CSV_PATH}"
            get_resp = requests.get(url, headers=headers, timeout=10)
            sha = get_resp.json().get("sha") if get_resp.status_code==200 else None
            payload = {"message": f"Diary update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "content": content_b64}
            if sha:
                payload["sha"] = sha
            requests.put(url, headers=headers, json=payload, timeout=15)
        except:
            pass
    return df2

def get_all_trades():
    if not os.path.exists(DB_FILE):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql("SELECT * FROM trades ORDER BY id DESC", conn)
    except:
        df = pd.DataFrame()
    conn.close(); return df

def update_trade_status(trade_id, status, exit_price, pnl):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE trades SET status=?, exit_price=?, pnl=?, exit_time=? WHERE id=?", (status, exit_price, pnl, datetime.now().strftime("%H:%M:%S"), trade_id))
    conn.commit(); conn.close()
    conn2 = sqlite3.connect(DB_FILE)
    df2 = pd.read_sql("SELECT * FROM trades", conn2)
    df2.to_csv(CSV_FILE, index=False); conn2.close()

init_db()

if not st.session_state.authenticated:
    st.title("Scanner - INDstocks")
    st.info("IND Token 24 ghante me expire hota hai. Roz subah naya Token banao: indstocks.com -> Login -> /app/api-trading/access-tokens -> Claim Your API Access -> Generate -> Copy karke yahan daalo.")
    with st.form("login_form"):
        indmoney_secret = st.text_input("INDstocks Access Token - indstocks.com se - Roz naya wala", type="password", placeholder="indstocks.com/app/api-trading/access-tokens se Copy kiya hua Token")
        app_pin = st.text_input("PIN (4 ank)", type="password")
        submit = st.form_submit_button("Scanner Kholo", use_container_width=True)
        if submit:
            if not app_pin or len(app_pin) < 4:
                st.error("4 ank ka PIN daalo")
            elif not indmoney_secret or len(indmoney_secret) < 10:
                st.error("IND Token daalo - Bina Token ke Option Chain nahi aayega")
            else:
                ok, msg = ind_test_profile(indmoney_secret)
                if not ok:
                    st.error(msg)
                    st.write("Token galat hai ya expire ho gaya hai. indstocks.com pe jaake naya Token banao, phir daalo.")
                else:
                    st.session_state.authenticated = True
                    st.session_state.indmoney_secret = indmoney_secret
                    st.session_state.indmoney_connected = True
                    st.session_state.indmoney_debug = msg
                    st.rerun()
    if st.button("Bina Token ke Dekho - Option Chain nahi aayega"):
        st.session_state.authenticated = True
        st.session_state.indmoney_secret = ""
        st.session_state.indmoney_connected = False
        st.rerun()
    st.stop()

top_left, top_right = st.columns([4, 1])
with top_left:
    st.title("Scanner | Rs 5,000 | INDstocks FIXED")
with top_right:
    st.write("")
    if st.button("Trading Diary", use_container_width=True):
        st.session_state.show_diary = not st.session_state.show_diary
        st.rerun()

if st.session_state.indmoney_connected:
    st.success(f"IND CONNECTED - {st.session_state.get('indmoney_debug','')}")
else:
    st.error("IND NOT CONNECTED - Option Chain nahi aayega")

st.sidebar.title("Dashboard")
if st.sidebar.button("Trading Diary Kholo"):
    st.session_state.show_diary = True; st.rerun()
if st.sidebar.button("Refresh Data"):
    st.cache_data.clear(); st.rerun()
if st.sidebar.button("Logout"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()

if st.session_state.show_diary:
    st.markdown("## TRADING DIARY")
    trades_df_all = get_all_trades()
    if trades_df_all.empty:
        st.info("Diary khali hai.")
    else:
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_df = trades_df_all[trades_df_all['date']==today_str]
        if not today_df.empty:
            total=len(today_df); wins=len(today_df[today_df['status']=='TARGET HIT']); losses=len(today_df[today_df['status']=='SL HIT'])
            win_rate=(wins/total*100) if total>0 else 0; total_pnl=today_df['pnl'].sum()
            m1,m2,m3,m4 = st.columns(4)
            m1.metric("Aaj Total", total); m2.metric("Target Hit", wins); m3.metric("SL Hit", losses); m4.metric("Total P&L", f"Rs {total_pnl:.0f}", f"Win Rate: {win_rate:.0f}%")
        for _, row in trades_df_all.iterrows():
            status_emoji = "🎯" if row['status']=='TARGET HIT' else "🛑" if row['status']=='SL HIT' else "⏳"
            with st.expander(f"{status_emoji} {row['date']} {row['time']} - {row['symbol']} {row['strike']} {row['opt_type']} - {row['status']} - P&L Rs {row['pnl'] if pd.notna(row['pnl']) else 0:.0f}"):
                c1,c2,c3 = st.columns(3)
                c1.write(f"Entry: Rs {row['entry']}\nStrike: {row['strike']} {row['opt_type']}\nCapital: Rs {row['capital_used']}")
                c2.write(f"SL: Rs {row['sl']}\nTarget: Rs {row['target']}\nReason: {row['reason']}")
                c3.write(f"Status: {row['status']}\nExit: Rs {row['exit_price'] if pd.notna(row['exit_price']) else 'Open'}\nP&L: Rs {row['pnl'] if pd.notna(row['pnl']) else 0:.0f}")
                if row['status']=='OPEN':
                    b1,b2 = st.columns(2)
                    if b1.button(f"Target Hua - #{row['id']}", key=f"dt{row['id']}"):
                        pnl = (row['target']-row['entry'])*row['qty_total']
                        update_trade_status(row['id'], "TARGET HIT", row['target'], pnl); st.rerun()
                    if b2.button(f"SL Hua - #{row['id']}", key=f"ds{row['id']}"):
                        pnl = (row['sl']-row['entry'])*row['qty_total']
                        update_trade_status(row['id'], "SL HIT", row['sl'], pnl); st.rerun()
        st.download_button("CSV Download Karo", data=trades_df_all.to_csv(index=False), file_name="all_trades.csv", mime="text/csv")
    if st.button("Diary Band Karo"):
        st.session_state.show_diary = False; st.rerun()
    st.divider()

@st.cache_data(ttl=120)
def fetch_indices_history():
    indices = {"NIFTY": "^NSEI", "BANK NIFTY": "^NSEBANK", "SENSEX": "^BSESN", "BANKEX": "^BSESN"}
    rows = []
    for name, ticker in indices.items():
        try:
            df = yf.download(ticker, period="6d", interval="1d", progress=False, auto_adjust=False)
            if df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            close_series = df['Close']
            if isinstance(close_series, pd.DataFrame):
                close_series = close_series.iloc[:, 0]
            closes = [safe_float(x) for x in close_series.tolist()]
            if len(closes) >= 2:
                yesterday_chg = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2) if closes[-2] != 0 else 0
                five_day_chg = round((closes[-1] - closes[0]) / closes[0] * 100, 2) if closes[0] != 0 else 0
                trend = "UP" if five_day_chg > 0 else "DOWN" if five_day_chg < 0 else "FLAT"
                rows.append({"Index": name, "LTP": round(float(closes[-1]), 2), "Kal ka Move %": yesterday_chg, "5 Din ka Move %": five_day_chg, "Trend": trend})
        except:
            continue
    return pd.DataFrame(rows)

@st.cache_data(ttl=180)
def fetch_global_news():
    news_rows = []; seen = set()
    for ticker in ["^NSEI", "^NSEBANK", "^BSESN"]:
        try:
            tk = yf.Ticker(ticker)
            news = tk.news if hasattr(tk, 'news') else []
            for n in news[:5]:
                title = n.get('title', '') if isinstance(n, dict) else getattr(n, 'title', '')
                if not title or title in seen:
                    continue
                seen.add(title)
                provider = n.get('provider', '') if isinstance(n, dict) else ''
                low = title.lower()
                neg = sum(1 for w in ["fed", "rate hike", "hike", "election", "uncertainty", "war", "fall", "drop", "negative", "crisis", "inflation", "recession"] if w in low)
                pos = sum(1 for w in ["rate cut", "cut", "growth", "positive", "rise", "rally", "policy", "reform", "profit", "record"] if w in low)
                if neg > pos:
                    sentiment = "NEGATIVE"; impact = "NEGATIVE"
                elif pos > neg:
                    sentiment = "POSITIVE"; impact = "POSITIVE"
                else:
                    sentiment = "NEUTRAL"; impact = "NEUTRAL"
                news_rows.append({"News": title[:120], "Source": provider, "Sentiment": sentiment, "Impact": impact})
        except:
            continue
    if len(news_rows) == 0:
        news_rows = [{"News": "Fed ka faisla aane wala hai.", "Source": "Global Check", "Sentiment": "NEUTRAL", "Impact": "NEUTRAL"}]
    return pd.DataFrame(news_rows)

@st.cache_data(ttl=60)
def scan_pura_market():
    all_rows = []
    for stock, ticker in MARKET_STOCKS.items():
        try:
            df = yf.download(ticker, period="2d", interval="5m", progress=False, auto_adjust=False)
            if df.empty or len(df) < 10:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.reset_index()
            for col in ['High', 'Low', 'Close', 'Volume', 'Open']:
                if col in df.columns and isinstance(df[col], pd.DataFrame):
                    df[col] = df[col].iloc[:, 0]
            df['Typical'] = (df['High'].apply(safe_float) + df['Low'].apply(safe_float) + df['Close'].apply(safe_float))/3
            df['VWAP'] = (df['Typical'] * df['Volume'].apply(safe_float)).cumsum() / df['Volume'].apply(safe_float).cumsum().replace(0, np.nan)
            df['VWAP'] = df['VWAP'].ffill()
            df_today = df.tail(75)
            if len(df_today) < 5:
                continue
            ltp = safe_float(df['Close'].iloc[-1]); prev_close = safe_float(df['Close'].iloc[-80]) if len(df) > 80 else safe_float(df_today['Open'].iloc[0]); today_open = safe_float(df_today['Open'].iloc[0])
            gap_pct = round((today_open - prev_close)/prev_close*100, 2) if prev_close != 0 else 0
            vwap = safe_float(df['VWAP'].iloc[-1]); orb_high = safe_float(df_today['High'].iloc[0:3].max()); orb_low = safe_float(df_today['Low'].iloc[0:3].min())
            avg_vol = safe_float(df_today['Volume'].mean()); first_vol = safe_float(df_today['Volume'].iloc[0]); vol_ratio = round(first_vol / avg_vol, 2) if avg_vol != 0 else 1.0
            last_5min_chg = round((safe_float(df['Close'].iloc[-1]) - safe_float(df['Close'].iloc[-2])) / safe_float(df['Close'].iloc[-2]) * 100, 3) if len(df) >= 2 and safe_float(df['Close'].iloc[-2]) != 0 else 0
            c1_gap = abs(gap_pct) > 0.30; c2_vwap = (ltp > vwap and gap_pct > 0) or (ltp < vwap and gap_pct < 0); c3_orb = (ltp > orb_high) or (ltp < orb_low); c4_vol = vol_ratio > 1.5
            movement_started = (ltp > orb_high and last_5min_chg > 0.1 and vol_ratio > 1.2) or (ltp < orb_low and last_5min_chg < -0.1 and vol_ratio > 1.2)
            movement_text = "MOVEMENT SURU HO GAYA" if movement_started else "ABHI MOVEMENT SURU NAHI HUA"
            score = 0
            if c1_gap: score += 20
            if c2_vwap: score += 20
            if c3_orb: score += 25
            if c4_vol: score += 20
            if movement_started: score += 15
            if abs(gap_pct) > 1.0: score += 10
            if abs(gap_pct) > 2.0: score += 10
            score = min(100, score)
            if ltp > vwap and gap_pct > 0:
                direction = "BULLISH"; pattern = "Gap Up + VWAP Upar + ORB Breakout" if c3_orb else "Gap Up + VWAP Upar"
            elif ltp < vwap and gap_pct < 0:
                direction = "BEARISH"; pattern = "Gap Down + VWAP Neeche + ORB Breakout" if c3_orb else "Gap Down + VWAP Neeche"
            else:
                direction = "SIDEWAYS"; pattern = "Koi clear pattern nahi"
            pass_count = sum([c1_gap, c2_vwap, c3_orb, c4_vol])
            all_rows.append({"Stock": str(stock), "LTP": round(float(ltp), 2), "Gap %": float(gap_pct), "VWAP": round(float(vwap), 2), "ORB High": round(float(orb_high), 2), "ORB Low": round(float(orb_low), 2), "Vol x": float(vol_ratio), "Last 5min %": float(last_5min_chg), "Direction": str(direction), "Pattern": str(pattern), "Movement": str(movement_text), "Movement Started?": "HAAN" if movement_started else "NAHI", "Probability %": int(score), "Gap": "✅" if c1_gap else "❌", "VWAP": "✅" if c2_vwap else "❌", "ORB": "✅" if c3_orb else "❌", "Volume": "✅" if c4_vol else "❌", "Pass": f"{pass_count}/4"})
        except:
            continue
    df = pd.DataFrame(all_rows)
    if not df.empty:
        df = df.sort_values("Probability %", ascending=False)
    return df

if st.button("SCAN NOW", use_container_width=True):
    with st.spinner("Scan ho raha hai..."):
        df_scan = scan_pura_market(); indices_df = fetch_indices_history(); news_df = fetch_global_news()
        st.session_state.scan_df = df_scan; st.session_state.indices_data = indices_df; st.session_state.news_data = news_df
        st.session_state.auto_sent = False
        if not df_scan.empty:
            top = df_scan.iloc[0]
            if safe_float(top.get("Probability %", 0)) >= 70:
                expiry_auto = "IND se aayegi"
                ok_auto = send_top5(df_scan.head(5), expiry_auto)
                st.session_state.auto_sent = ok_auto
        st.rerun()

if st.session_state.scan_df is not None and not st.session_state.scan_df.empty:
    df_scan = st.session_state.scan_df; indices_df = st.session_state.indices_data; news_df = st.session_state.news_data
    if st.session_state.get("auto_sent"):
        st.success("Chala gaya ✅")
    st.markdown("### 1. PICHHLA MOVE")
    if indices_df is not None and not indices_df.empty:
        st.dataframe(indices_df, use_container_width=True, hide_index=True)
    st.markdown("### 2. GLOBAL NEWS")
    if news_df is not None and not news_df.empty:
        st.dataframe(news_df, use_container_width=True, hide_index=True)
        neg_count = len(news_df[news_df["Impact"] == "NEGATIVE"]); pos_count = len(news_df[news_df["Impact"] == "POSITIVE"])
        if neg_count > pos_count:
            news_bias = "NEGATIVE"
        elif pos_count > neg_count:
            news_bias = "POSITIVE"
        else:
            news_bias = "NEUTRAL"
    else:
        news_bias = "NEUTRAL"
    st.markdown("### 3. TOP 5 STOCKS")
    top5 = df_scan.head(5)
    st.dataframe(top5[["Stock", "LTP", "Gap %", "Direction", "Pattern", "Probability %", "Movement", "Movement Started?", "Pass"]], use_container_width=True, hide_index=True)
    top1 = df_scan.iloc[0]; top1_stock = str(top1.get("Stock", "")); top1_prob = safe_float(top1.get("Probability %", 0)); top1_ltp = safe_float(top1.get("LTP", 0))
    st.success(f"No.1: {top1_stock} - Prob {top1_prob:.0f}% - LTP Rs {top1_ltp:.1f}")
    if st.button("SEND NOTIFICATION", use_container_width=True):
        ok = send_top5(top5, "IND se")
        if ok:
            st.success("Chala gaya ✅")
        else:
            st.error("Nahi gaya ❌")
    st.markdown("### 4. PURA MARKET")
    st.dataframe(df_scan[["Stock", "LTP", "Gap %", "Direction", "Pattern", "Probability %", "Gap", "VWAP", "ORB", "Volume", "Movement Started?", "Pass"]], use_container_width=True, hide_index=True)
    st.markdown("### 5. OPTION CHAIN - INDstocks se hi aayega, NSE Website se NAHI, Yahoo se NAHI")
    sel_stock = st.selectbox("Stock Chuno", df_scan["Stock"].tolist(), index=0)
    if sel_stock:
        row = df_scan[df_scan["Stock"] == sel_stock].iloc[0]
        sel_ltp = safe_float(row.get("LTP", 0)); sel_vwap = safe_float(row.get("VWAP", 0)); sel_orb_high = safe_float(row.get("ORB High", 0)); sel_orb_low = safe_float(row.get("ORB Low", 0)); sel_prob = safe_float(row.get("Probability %", 0))
        if sel_ltp > sel_vwap:
            vwap_txt = "UPAR"
        else:
            vwap_txt = "NEECHE"
        if sel_ltp > sel_orb_high:
            orb_txt = "UPAR - Breakout"
        elif sel_ltp < sel_orb_low:
            orb_txt = "NEECHE - Breakdown"
        else:
            orb_txt = "ANDAR"
        st.write(f"Selected: {sel_stock} | LTP: Rs {sel_ltp:.1f} | Pattern: {row.get('Pattern','')} | Prob: {sel_prob:.0f}%")
        st.write(f"Kahan pe hai: LTP Rs {sel_ltp:.1f} - VWAP Rs {sel_vwap:.1f} se {vwap_txt} - ORB {sel_orb_low:.1f} - {sel_orb_high:.1f} ke {orb_txt}")
        if st.button(f"{sel_stock} ka Option Chain Mango - INDstocks se", use_container_width=True):
            with st.spinner("INDstocks se Option Chain mang rahe hain - Docs wala tareeka..."):
                chain_df, source, expiry_yyyy, scrip_used, ind_ltp = ind_get_option_chain(sel_stock, st.session_state.get("indmoney_secret", ""))
                st.session_state[f"chain_{sel_stock}"] = chain_df; st.session_state[f"chain_source_{sel_stock}"] = source; st.session_state[f"expiry_{sel_stock}"] = expiry_yyyy; st.session_state[f"scrip_{sel_stock}"] = scrip_used; st.session_state[f"indltp_{sel_stock}"] = ind_ltp
                st.rerun()
        chain_key = f"chain_{sel_stock}"
        if chain_key in st.session_state and st.session_state[chain_key] is not None and not st.session_state[chain_key].empty:
            chain_df = st.session_state[chain_key]; source = st.session_state.get(f"chain_source_{sel_stock}", ""); expiry_shown = st.session_state.get(f"expiry_{sel_stock}", ""); scrip_shown = st.session_state.get(f"scrip_{sel_stock}", ""); ind_ltp_shown = st.session_state.get(f"indltp_{sel_stock}", "")
            st.success(f"✅ {source} - Expiry: {expiry_shown} - Scrip: {scrip_shown} - IND LTP: {ind_ltp_shown} - Total Strikes: {len(chain_df)}")
            st.dataframe(chain_df, use_container_width=True, hide_index=True)
            lot = LOT_SIZES.get(sel_stock, 100)
            check_df, best = check_all_strikes(chain_df, lot, sel_ltp, row.get("Direction", ""), budget=5000)
            st.markdown(f"#### TOTAL STRIKE CHECK - Kaunsa 1 Lot Rs 5000 me Ho Jayega? (Lot: {lot}, Expiry: {expiry_shown})")
            if not check_df.empty:
                st.dataframe(check_df, use_container_width=True, hide_index=True)
                fits_df = check_df[check_df["Fits"] == True]
                st.write(f"Total Checked: {len(check_df)} | 5000 me Ho Jayenge: {len(fits_df)}")
                if not fits_df.empty:
                    st.dataframe(fits_df[["Strike", "Type", "Premium", "1 Lot Cost", "Rs 5000 me?", "OI", "IV"]], use_container_width=True, hide_index=True)
            if best is not None:
                if news_bias == "NEGATIVE" and str(best.get("Type", "")) == "CE":
                    sl_factor = 0.80; target_factor = 1.30
                elif news_bias == "POSITIVE":
                    sl_factor = 0.70; target_factor = 1.60
                else:
                    sl_factor = 0.70; target_factor = 1.50
                entry_prem = safe_float(best.get("Premium", 0)); strike = safe_int(best.get("Strike", 0)); opt_type = str(best.get("Type", "CE"))
                sl_prem = round(entry_prem * sl_factor, 1); target_prem = round(entry_prem * target_factor, 1)
                max_loss = round((entry_prem - sl_prem) * safe_float(lot), 0); max_profit = round((target_prem - entry_prem) * safe_float(lot), 0); best_cost = safe_float(best.get("1 Lot Cost", 0))
                st.success(f"STRIKE: {sel_stock} {strike} {opt_type} @ Rs {entry_prem} - Expiry: {expiry_shown} - Cost Rs {best_cost:.0f} - SL Rs {sl_prem} - Target Rs {target_prem}")
                st.write(f"Entry: Rs {entry_prem} | Target: Rs {target_prem} | SL: Rs {sl_prem} | Max Profit: Rs {max_profit:.0f} | Max Loss: Rs {max_loss:.0f}")
                if st.button(f"{sel_stock} {strike} {opt_type} ka Notification Bhejo", use_container_width=True):
                    ok = send_strike(sel_stock, strike, opt_type, entry_prem, sl_prem, target_prem, best_cost, lot, expiry_shown, str(row.get("Movement", "")))
                    if ok:
                        st.success("Chala gaya ✅")
                    else:
                        st.error("Nahi gaya ❌")
                suggested = {"date": datetime.now().strftime("%Y-%m-%d"), "time": datetime.now().strftime("%H:%M:%S"), "symbol": sel_stock, "strike": strike, "opt_type": opt_type, "entry": float(entry_prem), "sl": float(sl_prem), "target": float(target_prem), "qty_lots": 1, "qty_total": float(lot), "capital_used": float(best_cost), "risk": float(max_loss), "status": "OPEN", "reason": f"{row.get('Direction','')} - {row.get('Pattern','')} - News {news_bias} - Prob {sel_prob:.0f}% - Expiry {expiry_shown} - {source}", "conditions": f"Gap {row.get('Gap','')} VWAP {row.get('VWAP','')} ORB {row.get('ORB','')} Vol {row.get('Volume','')} Movement {row.get('Movement Started?','')}"}
                if st.button(f"{sel_stock} ko Diary me Save Karo"):
                    save_trade(suggested); st.success("Diary me save ho gaya!"); st.rerun()
            else:
                st.error(f"{sel_stock} me Rs 5000 me koi 1 Lot wala contract nahi mila.")
        elif chain_key in st.session_state and (st.session_state[chain_key] is None or st.session_state[chain_key].empty):
            st.error(f"❌ Option Chain nahi aaya - Wajah: {st.session_state.get(f'chain_source_{sel_stock}','')}")
            st.write(f"Expiry try ki thi: {st.session_state.get(f'expiry_{sel_stock}','')} | Scrip try kiya tha: {st.session_state.get(f'scrip_{sel_stock}','')}")
            st.write("Sabse common wajah: Token 24 ghante me expire ho gaya hai. indstocks.com pe jaake naya Token banao, Logout karke dobara Login karo.")
        else:
            st.info(f"{sel_stock} ka Option Chain Mango dabao.")
else:
    st.info("SCAN NOW dabao.")
