# app.py - V13 - Clean - No Chat ID Button, No Token/Chat ID Show, Sirf Chala Gaya
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import sqlite3
import os
import requests
import base64

st.set_page_config(page_title="Scanner", layout="wide")

CAPITAL = 5000
DB_FILE = "trades.db"
CSV_FILE = "all_trades.csv"
GITHUB_CSV_PATH = "trades_diary/all_trades.csv"

# Telegram - Code me Token / Chat ID NAHI likha hai, Secrets me rahega, koi read nahi kar payega
# Streamlit Cloud -> Settings -> Secrets me daalo:
# TELEGRAM_BOT_TOKEN = "yahan token"
# TELEGRAM_CHAT_ID = "yahan chat id"
# GitHub me ye file jayegi, Secrets nahi jayega, isliye koi Token nahi dekh payega
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
if "notifications" not in st.session_state:
    st.session_state.notifications = []
if "indmoney_connected" not in st.session_state:
    st.session_state.indmoney_connected = False
if "auto_sent" not in st.session_state:
    st.session_state.auto_sent = False

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
    ok = send_telegram(msg)
    return ok

def send_strike(stock, strike, opt_type, entry, sl, target, cost, lot, expiry_str, movement):
    entry_f = safe_float(entry); sl_f = safe_float(sl); target_f = safe_float(target); cost_f = safe_float(cost); lot_f = safe_float(lot)
    max_profit = round((target_f - entry_f) * lot_f, 0); max_loss = round((entry_f - sl_f) * lot_f, 0)
    msg = f"STRIKE SELECTED - {stock}\n------------------------\nStock: {stock}\nStrike: {safe_int(strike)} {opt_type}\nExpiry: {expiry_str}\nEntry: Rs {entry_f}\nStop Loss: Rs {sl_f}\nTarget: Rs {target_f}\n1 Lot Qty: {safe_int(lot_f)}\n1 Lot Cost: Rs {cost_f:.0f}\nMax Profit: Rs {max_profit:.0f}\nMax Loss: Rs {max_loss:.0f}\nMovement: {movement}\nTime: {datetime.now().strftime('%H:%M:%S')}"
    ok = send_telegram(msg)
    return ok

def get_option_chain(symbol, ltp, expiry_str, secret_code):
    if secret_code and len(secret_code) >= 4:
        headers = {"Authorization": f"Bearer {secret_code}", "x-api-key": secret_code, "Content-Type": "application/json", "User-Agent": "INDMoney-Scanner/1.0"}
        for url in [f"https://api.indmoney.com/api/option-chain?symbol={symbol}&expiry={expiry_str}", f"https://api.indmoney.com/api/v1/option-chain?symbol={symbol}&expiry={expiry_str}"]:
            try:
                r = requests.get(url, headers=headers, timeout=8)
                if r.status_code == 200:
                    data = r.json()
                    items = data.get("data", []) if isinstance(data, dict) else data
                    rows = []
                    if isinstance(items, list) and len(items) > 0:
                        for item in items:
                            s = item.get("strikePrice") or item.get("strike")
                            ce = item.get("CE", {}) if isinstance(item.get("CE"), dict) else {}
                            pe = item.get("PE", {}) if isinstance(item.get("PE"), dict) else {}
                            if s:
                                rows.append({"Strike": safe_int(s), "CE Premium": safe_float(ce.get("lastPrice", 0)), "PE Premium": safe_float(pe.get("lastPrice", 0))})
                        if rows:
                            return pd.DataFrame(rows).sort_values("Strike"), "IND MONEY"
            except:
                continue
    try:
        ticker_sym = MARKET_STOCKS.get(symbol, f"{symbol}.NS")
        tk = yf.Ticker(ticker_sym)
        expiries = tk.options if hasattr(tk, 'options') else []
        if expiries and len(expiries) > 0:
            nearest_yahoo_expiry = expiries[0]
            opt = tk.option_chain(nearest_yahoo_expiry)
            calls = opt.calls; puts = opt.puts
            merged = pd.merge(calls[["strike", "lastPrice"]], puts[["strike", "lastPrice"]], on="strike", how="outer", suffixes=("_CE", "_PE"))
            merged = merged.rename(columns={"strike": "Strike", "lastPrice_CE": "CE Premium", "lastPrice_PE": "PE Premium"})
            merged["CE Premium"] = merged["CE Premium"].fillna(0).apply(safe_float)
            merged["PE Premium"] = merged["PE Premium"].fillna(0).apply(safe_float)
            merged["Strike"] = merged["Strike"].apply(safe_int)
            merged = merged.sort_values("Strike")
            if not merged.empty and (merged["CE Premium"] > 0).any():
                return merged, f"YAHOO - {nearest_yahoo_expiry}"
    except:
        pass
    return pd.DataFrame(), "NAHI AAYA"

def get_nearest_expiry():
    today = datetime.now().date()
    days_ahead = (3 - today.weekday()) % 7
    nearest = today if days_ahead == 0 else today + timedelta(days=days_ahead)
    return nearest.strftime("%d-%b-%Y")

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
        results.append({"Strike": strike, "Type": opt_type, "Premium": prem, "Lot Qty": safe_int(lot_f), "1 Lot Cost": cost, "Rs 5000 me?": "✅ HO JAYEGA" if fits else "❌ NAHI HOGA", "ATM se Door": round(abs(strike - ltp_f), 1), "Fits": fits})
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
    st.title("Scanner")
    with st.form("login_form"):
        indmoney_secret = st.text_input("INDmoney Secret Code", type="password")
        app_pin = st.text_input("PIN (4 ank)", type="password")
        submit = st.form_submit_button("Scanner Kholo", use_container_width=True)
        if submit:
            if not app_pin or len(app_pin) < 4:
                st.error("4 ank ka PIN daalo")
            else:
                st.session_state.authenticated = True
                st.session_state.indmoney_secret = indmoney_secret
                st.session_state.indmoney_connected = bool(indmoney_secret and len(indmoney_secret) >= 4)
                st.rerun()
    if st.button("Bina Secret ke Dekho"):
        st.session_state.authenticated = True
        st.session_state.indmoney_secret = ""
        st.session_state.indmoney_connected = False
        st.rerun()
    st.stop()

top_left, top_right = st.columns([4, 1])
with top_left:
    st.title("Scanner | Rs 5,000")
with top_right:
    st.write("")
    if st.button("Trading Diary", use_container_width=True):
        st.session_state.show_diary = not st.session_state.show_diary
        st.rerun()

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
            # AUTO - Prob 70+ hai to khud hi bhej dega, press karne ki zaroorat nahi
            if safe_float(top.get("Probability %", 0)) >= 70:
                expiry_auto = get_nearest_expiry()
                ok_auto = send_top5(df_scan.head(5), expiry_auto)
                st.session_state.auto_sent = ok_auto
        st.rerun()

if st.session_state.scan_df is not None and not st.session_state.scan_df.empty:
    df_scan = st.session_state.scan_df; indices_df = st.session_state.indices_data; news_df = st.session_state.news_data; expiry_str = get_nearest_expiry()
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
    # Sirf Stock Send - Press karo to bhejega, Auto bhi bhejega
    if st.button("SEND NOTIFICATION", use_container_width=True):
        ok = send_top5(top5, expiry_str)
        if ok:
            st.success("Chala gaya ✅")
        else:
            st.error("Nahi gaya ❌")
    st.markdown("### 4. PURA MARKET")
    st.dataframe(df_scan[["Stock", "LTP", "Gap %", "Direction", "Pattern", "Probability %", "Gap", "VWAP", "ORB", "Volume", "Movement Started?", "Pass"]], use_container_width=True, hide_index=True)
    st.markdown("### 5. OPTION CHAIN")
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
        st.write(f"Selected: {sel_stock} | LTP: Rs {sel_ltp:.1f} | Pattern: {row.get('Pattern','')} | Prob: {sel_prob:.0f}% | Expiry: {expiry_str}")
        st.write(f"Kahan pe hai: LTP Rs {sel_ltp:.1f} - VWAP Rs {sel_vwap:.1f} se {vwap_txt} - ORB {sel_orb_low:.1f} - {sel_orb_high:.1f} ke {orb_txt}")
        if st.button(f"{sel_stock} ka Option Chain Mango", use_container_width=True):
            with st.spinner("Option Chain mang rahe hain..."):
                chain_df, source = get_option_chain(sel_stock, sel_ltp, expiry_str, st.session_state.get("indmoney_secret", ""))
                st.session_state[f"chain_{sel_stock}"] = chain_df; st.session_state[f"chain_source_{sel_stock}"] = source; st.session_state[f"expiry_{sel_stock}"] = expiry_str
                st.rerun()
        chain_key = f"chain_{sel_stock}"
        if chain_key in st.session_state and st.session_state[chain_key] is not None and not st.session_state[chain_key].empty:
            chain_df = st.session_state[chain_key]; source = st.session_state.get(f"chain_source_{sel_stock}", ""); expiry_shown = st.session_state.get(f"expiry_{sel_stock}", expiry_str)
            st.success(f"Option Chain aaya - {source} - Expiry: {expiry_shown}")
            st.dataframe(chain_df, use_container_width=True, hide_index=True)
            lot = LOT_SIZES.get(sel_stock, 100)
            check_df, best = check_all_strikes(chain_df, lot, sel_ltp, row.get("Direction", ""), budget=5000)
            if not check_df.empty:
                st.dataframe(check_df, use_container_width=True, hide_index=True)
                fits_df = check_df[check_df["Fits"] == True]
                st.write(f"Total Checked: {len(check_df)} | 5000 me Ho Jayenge: {len(fits_df)}")
                if not fits_df.empty:
                    st.dataframe(fits_df[["Strike", "Type", "Premium", "1 Lot Cost", "Rs 5000 me?"]], use_container_width=True, hide_index=True)
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
                st.success(f"STRIKE: {sel_stock} {strike} {opt_type} @ Rs {entry_prem} - Cost Rs {best_cost:.0f} - SL Rs {sl_prem} - Target Rs {target_prem}")
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
            st.error("Option Chain nahi aaya.")
        else:
            st.info(f"{sel_stock} ka Option Chain Mango dabao.")
else:
    st.info("SCAN NOW dabao.")
