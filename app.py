# app.py - V5 FINAL - INDmoney INFO ONLY - No Auto Trade
# Jaise pehle wali website thi - Expiry load, Option Chain load, Har Stock ki jaankari
# Sirf JAANKARI dega, Trade AUTOMATIC nahi hoga. Trade aap khud dekh kar loge.
# INDmoney Secret Code sirf 1 cheez - Optional. Bina uske bhi chalega kyunki data NSE Public se hai.

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import sqlite3
import os
import requests
import base64
from io import StringIO

st.set_page_config(page_title="INDmoney Info Scanner - READ ONLY", layout="wide")

CAPITAL = 10000
DB_FILE = "trades.db"
CSV_FILE = "all_trades.csv"
GITHUB_CSV_PATH = "trades_diary/all_trades.csv"

# F&O Stocks - NSE ke 216 me se top wale - pehle wali website jaisa
FO_STOCKS = {
    "NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS",
    "INFY": "INFY.NS", "HDFCBANK": "HDFCBANK.NS", "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS", "TATAMOTORS": "TATAMOTORS.NS", "TATASTEEL": "TATASTEEL.NS",
    "KALYANJIL": "KALYANKJIL.NS", "M&M": "M&M.NS", "TITAN": "TITAN.NS",
    "ADANIENT": "ADANIENT.NS", "ADANIPORTS": "ADANIPORTS.NS", "AXISBANK": "AXISBANK.NS",
    "KOTAKBANK": "KOTAKBANK.NS", "LT": "LT.NS", "MARUTI": "MARUTI.NS",
    "ONGC": "ONGC.NS", "POWERGRID": "POWERGRID.NS", "NTPC": "NTPC.NS",
    "COALINDIA": "COALINDIA.NS", "BPCL": "BPCL.NS", "HINDALCO": "HINDALCO.NS",
    "JSWSTEEL": "JSWSTEEL.NS", "BAJFINANCE": "BAJFINANCE.NS", "BAJAJFINSV": "BAJAJFINSV.NS",
    "BHARTIARTL": "BHARTIARTL.NS", "ITC": "ITC.NS", "HCLTECH": "HCLTECH.NS",
    "WIPRO": "WIPRO.NS", "TECHM": "TECHM.NS", "SUNPHARMA": "SUNPHARMA.NS",
    "DRREDDY": "DRREDDY.NS", "CIPLA": "CIPLA.NS", "DIVISLAB": "DIVISLAB.NS",
    "EICHERMOT": "EICHERMOT.NS", "HEROMOTOCO": "HEROMOTOCO.NS", "GRASIM": "GRASIM.NS",
    "ULTRACEMCO": "ULTRACEMCO.NS", "SHRIRAMFIN": "SHRIRAMFIN.NS", "MUTHOOTFIN": "MUTHOOTFIN.NS",
    "UNIONBANK": "UNIONBANK.NS", "PNB": "PNB.NS", "CANBK": "CANBK.NS",
    "FEDERALBNK": "FEDERALBNK.NS", "IDFCFIRSTB": "IDFCFIRSTB.NS",
}

# Lot sizes - approx
LOT_SIZES = {"NIFTY": 75, "BANKNIFTY": 15, "RELIANCE": 250, "TCS": 175, "INFY": 800, "HDFCBANK": 550, "ICICIBANK": 1375, "SBIN": 1500, "TATAMOTORS": 1400, "TATASTEEL": 5500, "KALYANJIL": 3200, "M&M": 800, "TITAN": 350, "ADANIENT": 300, "ADANIPORTS": 1000, "AXISBANK": 1200, "KOTAKBANK": 800, "LT": 300, "MARUTI": 50, "ONGC": 3850, "POWERGRID": 3600, "NTPC": 5700, "COALINDIA": 2100, "BPCL": 1800, "HINDALCO": 2600, "JSWSTEEL": 1350, "BAJFINANCE": 125, "BAJAJFINSV": 500, "BHARTIARTL": 950, "ITC": 1600, "HCLTECH": 700, "WIPRO": 3000, "TECHM": 900, "SUNPHARMA": 700, "DRREDDY": 125, "CIPLA": 650, "DIVISLAB": 200, "EICHERMOT": 175, "HEROMOTOCO": 300, "GRASIM": 250, "ULTRACEMCO": 100, "SHRIRAMFIN": 300, "MUTHOOTFIN": 500, "UNIONBANK": 8000, "PNB": 8000, "CANBK": 7000, "FEDERALBNK": 10000, "IDFCFIRSTB": 10000}

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "show_diary" not in st.session_state:
    st.session_state.show_diary = False
if "scan_done" not in st.session_state:
    st.session_state.scan_done = False
if "scan_df" not in st.session_state:
    st.session_state.scan_df = None
if "github_last_sync" not in st.session_state:
    st.session_state.github_last_sync = "Abhi sync nahi hua"

# ---------- HELPERS ----------
def get_next_expiries(n=4):
    today = datetime.now().date()
    exps = []
    d = today
    for _ in range(30):
        d += timedelta(days=1)
        if d.weekday() == 3:  # Thursday
            exps.append(d)
            if len(exps) >= n:
                break
    return [e.strftime("%Y-%m-%d") for e in exps]

@st.cache_data(ttl=60)
def fetch_all_fo_quotes():
    """Sab F&O stocks ka LTP + Day % - Yahoo se, 60 sec cache, No Random"""
    rows = []
    for name, ticker in FO_STOCKS.items():
        try:
            df = yf.download(ticker, period="2d", interval="1d", progress=False, auto_adjust=False)
            if df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            ltp = float(df['Close'].iloc[-1])
            prev = float(df['Close'].iloc[-2]) if len(df) > 1 else ltp
            day_pct = round((ltp - prev) / prev * 100, 2) if prev else 0
            rows.append({"Stock": name, "LTP": round(ltp, 2), "Day %": day_pct})
        except:
            continue
    return pd.DataFrame(rows)

@st.cache_data(ttl=60)
def fetch_nse_option_chain_for_stock(symbol="NIFTY"):
    """NSE se asli Option Chain - bina login ke"""
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}
        sess = requests.Session()
        sess.get("https://www.nseindia.com", headers=headers, timeout=10)
        if symbol in ["NIFTY", "BANKNIFTY"]:
            url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        else:
            url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
        r = sess.get(url, headers=headers, timeout=12)
        if r.status_code == 200:
            return r.json(), "NSE LIVE"
    except:
        pass
    return None, "NSE FAIL"

def build_chain_df(nse_data, underlying_ltp):
    if nse_data is None:
        return pd.DataFrame(), 0, 0
    try:
        records = nse_data.get("records", {}).get("data", [])
        rows = []
        total_ce_oi = 0
        total_pe_oi = 0
        for item in records:
            s = item.get("strikePrice", 0)
            ce = item.get("CE", {})
            pe = item.get("PE", {})
            if ce:
                total_ce_oi += ce.get("openInterest", 0)
            if pe:
                total_pe_oi += pe.get("openInterest", 0)
            rows.append({
                "Strike": s,
                "CE OI": ce.get("openInterest", 0) if ce else 0,
                "CE OI Chg": ce.get("changeinOpenInterest", 0) if ce else 0,
                "CE LTP": ce.get("lastPrice", 0) if ce else 0,
                "CE IV": round(ce.get("impliedVolatility", 0), 1) if ce else 0,
                "PE OI": pe.get("openInterest", 0) if pe else 0,
                "PE OI Chg": pe.get("changeinOpenInterest", 0) if pe else 0,
                "PE LTP": pe.get("lastPrice", 0) if pe else 0,
                "PE IV": round(pe.get("impliedVolatility", 0), 1) if pe else 0,
            })
        df = pd.DataFrame(rows).sort_values("Strike")
        pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi else 0
        return df, pcr, len(df)
    except:
        return pd.DataFrame(), 0, 0

def find_best_10k_contract(chain_df, underlying_ltp, lot_size, expiry_label):
    """Rs 10,000 me 1 Lot wala best contract - Deterministic, No Random"""
    if chain_df.empty:
        return None
    atm = int(round(underlying_ltp / 10) * 10) if underlying_ltp < 1000 else int(round(underlying_ltp / 50) * 50)
    # ATM ke aas paas ke contracts me se jiska premium * lot <= 10000 aur sabse paas ATM ke
    candidates = []
    for _, row in chain_df.iterrows():
        for opt in ["CE", "PE"]:
            ltp_col = f"{opt} LTP"
            prem = float(row[ltp_col]) if row[ltp_col] else 0
            if prem <= 0:
                continue
            cost = prem * lot_size
            if cost <= 10000 and cost >= 1000:  # 1000 se kam wala bahut door ka hai, mat lo
                dist = abs(row["Strike"] - underlying_ltp)
                candidates.append({"Strike": row["Strike"], "Type": opt, "Premium": prem, "Cost": round(cost, 0), "Dist": dist, "OI Chg": row[f"{opt} OI Chg"]})
    if not candidates:
        return None
    candidates = sorted(candidates, key=lambda x: x["Dist"])
    best = candidates[0]
    best["Expiry"] = expiry_label
    best["Lot"] = lot_size
    best["SL"] = round(best["Premium"] * 0.70, 1)
    best["Target"] = round(best["Premium"] * 1.50, 1)
    return best

# ---------- DB ----------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, time TEXT, symbol TEXT, strike INTEGER, opt_type TEXT, entry REAL, sl REAL, target REAL, qty_lots INTEGER, qty_total REAL, capital_used REAL, risk REAL, status TEXT, exit_price REAL, pnl REAL, exit_time TEXT, reason TEXT)")
    conn.commit()
    conn.close()

def save_trade(trade):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO trades (date,time,symbol,strike,opt_type,entry,sl,target,qty_lots,qty_total,capital_used,risk,status,exit_price,pnl,exit_time,reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    (trade['date'], trade['time'], trade['symbol'], trade['strike'], trade['opt_type'], trade['entry'], trade['sl'], trade['target'], trade['qty_lots'], trade['qty_total'], trade['capital_used'], trade['risk'], trade['status'], None, None, None, trade['reason']))
    conn.commit()
    conn.close()
    conn2 = sqlite3.connect(DB_FILE)
    df2 = pd.read_sql("SELECT * FROM trades", conn2)
    df2.to_csv(CSV_FILE, index=False)
    conn2.close()
    if st.session_state.get("github_pat"):
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
            put_resp = requests.put(url, headers=headers, json=payload, timeout=15)
            st.session_state.github_last_sync = f"{'OK' if put_resp.status_code in [200,201] else 'Fail'} - {datetime.now().strftime('%H:%M:%S')}"
        except Exception as e:
            st.session_state.github_last_sync = f"Fail - {e}"
    return df2

def get_all_trades():
    if not os.path.exists(DB_FILE):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql("SELECT * FROM trades ORDER BY id DESC", conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df

def update_trade_status(trade_id, status, exit_price, pnl):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE trades SET status=?, exit_price=?, pnl=?, exit_time=? WHERE id=?", (status, exit_price, pnl, datetime.now().strftime("%H:%M:%S"), trade_id))
    conn.commit()
    conn.close()
    conn2 = sqlite3.connect(DB_FILE)
    df2 = pd.read_sql("SELECT * FROM trades", conn2)
    df2.to_csv(CSV_FILE, index=False)
    conn2.close()

init_db()

# ---------- LOGIN - SIRF INDmoney Secret Code - 1 Cheez ----------
if not st.session_state.authenticated:
    st.title("🔐 INDmoney Info Scanner - Login")
    st.write("**Sirf JAANKARI dega. Auto Trade NAHI karega. Trade aap khud dekh kar loge.**")
    st.success("INDmoney Mode - READ ONLY | Sirf 1 cheez chahiye - INDmoney Secret Code (Optional)")
    with st.form("login_form"):
        indmoney_secret = st.text_input("INDmoney Secret Code (Optional) - Sirf portfolio dekhne ke liye", type="password", placeholder="INDmoney App me jo Secret Code hai, khali bhi chhod sakte ho")
        st.caption("Bina Secret ke bhi chalega - Option Chain aur Stock ki jaankari NSE Public Data se aayegi, jo pehle wali website me bhi aati thi.")
        with st.expander("GitHub Auto-Save (Optional) - Ek hi CSV me"):
            gh_user = st.text_input("GitHub Username (Optional)")
            gh_repo = st.text_input("GitHub Repo Name (Optional)")
            gh_pat = st.text_input("GitHub PAT (Optional)", type="password")
        app_pin = st.text_input("Apna PIN (4 ank)", type="password", placeholder="jaise: 1234")
        submit = st.form_submit_button("🚀 Scanner Kholo", use_container_width=True)
        if submit:
            if not app_pin or len(app_pin) < 4:
                st.error("4 ank ka PIN daalo")
            else:
                st.session_state.authenticated = True
                st.session_state.indmoney_secret = indmoney_secret
                st.session_state.github_pat = gh_pat if 'gh_pat' in locals() else ""
                st.session_state.github_repo = f"{gh_user}/{gh_repo}" if 'gh_user' in locals() and gh_user and gh_repo else ""
                st.rerun()
    st.markdown("---")
    st.write("**Pehle wali website jaisa hi hai:** Expiry load hoga, Option Chain load hoga, Har Stock ki jaankari aayegi, Rs 10,000 wala Shortlist aayega. Fark sirf itna hai ki ye **Auto Trade nahi karega.** Sirf batayega - `Ye contract Rs 10,000 me aayega, SL ye hai, Target ye hai`. Trade lena hai ya nahi, ye aap khud dekh kar decide karoge.")
    if st.button("👀 Bina Secret ke Seedha Dekho"):
        st.session_state.authenticated = True
        st.session_state.indmoney_secret = ""
        st.session_state.github_pat = ""
        st.session_state.github_repo = ""
        st.rerun()
    st.stop()

# ---------- MAIN APP - Pehle wali website jaisa ----------
top_left, top_right = st.columns([4, 1])
with top_left:
    st.title("INDmoney Info Scanner - READ ONLY")
with top_right:
    st.write("")
    if st.button("📓 Trading Diary", use_container_width=True):
        st.session_state.show_diary = not st.session_state.show_diary
        st.rerun()

st.success("🟢 MODE: READ ONLY - Sirf Jaankari | Auto Trade OFF | Trade aap khud loge | Data: NSE Public + Yahoo | Cache 60 sec")
st.caption(f"INDmoney Secret: {'Diya hua hai' if st.session_state.get('indmoney_secret') else 'Nahi diya - fir bhi chal raha hai'} | GitHub CSV: trades_diary/all_trades.csv (Ek hi file) | Last Sync: {st.session_state.github_last_sync}")

# Dashboard top stats - pehle wali website jaisa
c1, c2, c3, c4 = st.columns(4)
c1.metric("Watched NSE F&O Stocks", f"{len(FO_STOCKS)}")
c2.metric("Quote Universe", f"{len(FO_STOCKS)}")
c3.metric("Refresh", "60s")
c4.metric("Mode", "READ ONLY")

# Diary Section - Kone wala button
if st.session_state.show_diary:
    st.markdown("## 📓 TRADING DIARY - Daily Trading Detail")
    trades_df_all = get_all_trades()
    if trades_df_all.empty:
        st.info("Abhi diary khali hai. Neeche se koi suggestion Save karo to yahan aayega.")
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
                cc1,cc2,cc3 = st.columns(3)
                cc1.write(f"**Kya Diya Tha:**\n- Entry: Rs {row['entry']}\n- Strike: {row['strike']} {row['opt_type']}\n- Capital: Rs {row['capital_used']}")
                cc2.write(f"**Kya Socha Tha:**\n- SL: Rs {row['sl']}\n- Target: Rs {row['target']}\n- Reason: {row['reason']}")
                cc3.write(f"**Kya Hua:**\n- Status: {row['status']}\n- Exit: Rs {row['exit_price'] if pd.notna(row['exit_price']) else 'Open'}\n- P&L: Rs {row['pnl'] if pd.notna(row['pnl']) else 0:.0f}")
                if row['status']=='OPEN':
                    b1,b2 = st.columns(2)
                    if b1.button(f"🎯 Target Hua - #{row['id']}", key=f"dt{row['id']}"):
                        pnl = (row['target']-row['entry'])*row['qty_total']
                        update_trade_status(row['id'], "TARGET HIT", row['target'], pnl)
                        st.rerun()
                    if b2.button(f"🛑 SL Hua - #{row['id']}", key=f"ds{row['id']}"):
                        pnl = (row['sl']-row['entry'])*row['qty_total']
                        update_trade_status(row['id'], "SL HIT", row['sl'], pnl)
                        st.rerun()
        st.download_button("⬇️ Ek hi CSV Download Karo (all_trades.csv)", data=trades_df_all.to_csv(index=False), file_name="all_trades.csv", mime="text/csv")
    if st.button("❌ Diary Band Karo"):
        st.session_state.show_diary = False
        st.rerun()
    st.divider()

# ---------- SCAN NOW - Fastest Rising / Falling ----------
st.markdown("### 🔍 F&O Scan")
if st.button("🔴 Scan Now - Sab Stocks ka Data Lao", use_container_width=True):
    with st.spinner("Sab stocks ka data la raha hoon... 10-15 sec lagega"):
        df_scan = fetch_all_fo_quotes()
        st.session_state.scan_df = df_scan
        st.session_state.scan_done = True
        st.rerun()

if st.session_state.scan_done and st.session_state.scan_df is not None and not st.session_state.scan_df.empty:
    df_scan = st.session_state.scan_df
    rising = df_scan.sort_values("Day %", ascending=False).head(10)
    falling = df_scan.sort_values("Day %", ascending=True).head(10)
    colR, colF = st.columns(2)
    with colR:
        st.markdown("#### 🟢 Fastest Rising F&O Stocks - Top 10")
        st.dataframe(rising, use_container_width=True, hide_index=True)
    with colF:
        st.markdown("#### 🔴 Fastest Falling F&O Stocks - Top 10")
        st.dataframe(falling, use_container_width=True, hide_index=True)
else:
    st.info("Scan Now dabao to sab stocks ki jaankari aayegi - Kaunsa tez badh raha hai, kaunsa gir raha hai.")

st.divider()

# ---------- EXPIRY + STOCK SELECT + OPTION CHAIN ----------
st.markdown("### 📅 Expiry + Stock Chuno - Option Chain Lao")
expiries = get_next_expiries(4)
colE, colS, colB = st.columns([2, 2, 1])
with colE:
    selected_expiry = st.selectbox("Expiry Chuno", expiries, index=0)
with colS:
    selected_stock = st.selectbox("Stock Chuno", list(FO_STOCKS.keys()), index=list(FO_STOCKS.keys()).index("KALYANJIL") if "KALYANJIL" in FO_STOCKS else 0)
with colB:
    st.write("")
    fetch_chain = st.button("📥 Fetch Option Chain", use_container_width=True)

if fetch_chain or "last_chain_stock" in st.session_state:
    if fetch_chain:
        st.session_state.last_chain_stock = selected_stock
        st.session_state.last_expiry = selected_expiry
    stock_to_fetch = st.session_state.get("last_chain_stock", selected_stock)
    expiry_to_show = st.session_state.get("last_expiry", selected_expiry)
    with st.spinner(f"{stock_to_fetch} ka Option Chain la raha hoon..."):
        nse_data, nse_status = fetch_nse_option_chain_for_stock(stock_to_fetch)
        chain_df, pcr, n_strikes = build_chain_df(nse_data, 0)
        # Underlying LTP - scan se ya Yahoo se
        try:
            ydf = yf.download(FO_STOCKS[stock_to_fetch], period="1d", interval="1m", progress=False, auto_adjust=False)
            if isinstance(ydf.columns, pd.MultiIndex):
                ydf.columns = ydf.columns.get_level_values(0)
            underlying_ltp = float(ydf['Close'].iloc[-1])
        except:
            underlying_ltp = 0
        st.success(f"✅ Option Chain loaded: {stock_to_fetch} - {expiry_to_show} - {n_strikes} strikes - {nse_status}")
        st.write(f"Loaded: {stock_to_fetch} - Expiry: {expiry_to_show} - {n_strikes} contracts")
        if not chain_df.empty:
            # ATM
            atm_strike = chain_df.iloc[(chain_df['Strike'] - underlying_ltp).abs().argsort()[:1]]['Strike'].values[0] if underlying_ltp else 0
            st.markdown(f"### 🔥 ₹10,000 Budget - One-Lot Option Shortlist - {stock_to_fetch}")
            st.caption("Scanner confirmation: Sirf jaankari hai. Ye signal nahi hai ki trade lo hi lo. Dekh kar khud decide karo.")
            best = find_best_10k_contract(chain_df, underlying_ltp, LOT_SIZES.get(stock_to_fetch, 100), expiry_to_show)
            if best:
                st.success(f"Best-fit contract: {stock_to_fetch} - {expiry_to_show} - {best['Strike']} {best['Type']} - Premium Rs {best['Premium']} - Cost Rs {best['Cost']} (1 Lot) - Budget Rs 10,000 me aayega")
                b1,b2,b3,b4,b5 = st.columns(5)
                b1.metric("Underlying / LTP", f"₹{underlying_ltp:.2f}")
                b2.metric("ATM Strike", f"{atm_strike:.0f}")
                b3.metric("PCR", f"{pcr:.2f}")
                b4.metric("Best Strike", f"{best['Strike']} {best['Type']}")
                b5.metric("Premium / Cost", f"Rs {best['Premium']} / Rs {best['Cost']:.0f}")
                c1,c2,c3 = st.columns(3)
                c1.metric("Entry (Premium)", f"Rs {best['Premium']}")
                c2.metric("Stop Loss", f"Rs {best['SL']}", f"Loss agar SL hua: Rs {(best['Premium']-best['SL'])*best['Lot']:.0f}")
                c3.metric("Target", f"Rs {best['Target']}", f"Profit agar Target hua: Rs {(best['Target']-best['Premium'])*best['Lot']:.0f}")
                st.write(f"**Detail:** {stock_to_fetch} - {expiry_to_show} - {best['Strike']} {best['Type']} - Premium Rs {best['Premium']} - Lot Size {best['Lot']} - Total Cost Rs {best['Cost']} - SL Rs {best['SL']} - Target Rs {best['Target']} - PCR {pcr}")
                st.info("⚠️ Ye sirf jaankari hai. Auto Buy nahi hoga. Trade lena hai to aap apne broker App me ja kar khud loge. Pehle dekh lo kaise kaam karta hai, uske baad hi trade lena.")
                # Save to Diary - Manual
                suggested = {"date": datetime.now().strftime("%Y-%m-%d"), "time": datetime.now().strftime("%H:%M:%S"), "symbol": stock_to_fetch, "strike": int(best['Strike']), "opt_type": best['Type'], "entry": float(best['Premium']), "sl": float(best['SL']), "target": float(best['Target']), "qty_lots": 1, "qty_total": float(best['Lot']), "capital_used": float(best['Cost']), "risk": float((best['Premium']-best['SL'])*best['Lot']), "status": "OPEN", "reason": f"10k Shortlist - {stock_to_fetch} - PCR {pcr} - Expiry {expiry_to_show}"}
                if st.button("📝 Is Jaankari ko Diary me Save Karo (Trade Liya to hi dabao)"):
                    save_trade(suggested)
                    st.success("Diary me save ho gaya! Ek hi CSV me update ho gaya. Upar Trading Diary me dekho.")
                    st.rerun()
            else:
                st.warning(f"{stock_to_fetch} me Rs 10,000 me koi 1 Lot wala contract nahi mila. Premium bahut zyada hai ya bahut kam hai.")
            st.markdown("### Full Option Chain Table")
            st.dataframe(chain_df, use_container_width=True, hide_index=True)
        else:
            st.error("Option Chain nahi mila. NSE ne block kiya hoga. 1 minute baad phir Fetch dabao.")

st.divider()

# ---------- NIFTY 9:15 INFO - Sirf Jaankari ----------
st.markdown("### 📊 Nifty 9:15 Info - Sirf Jaankari, Trade Aap Khud Loge")
try:
    nifty_df = yf.download("^NSEI", period="2d", interval="5m", progress=False, auto_adjust=False)
    if isinstance(nifty_df.columns, pd.MultiIndex):
        nifty_df.columns = nifty_df.columns.get_level_values(0)
    nifty_df = nifty_df.reset_index()
    nifty_df['Typical'] = (nifty_df['High'] + nifty_df['Low'] + nifty_df['Close'])/3
    nifty_df['VWAP'] = (nifty_df['Typical'] * nifty_df['Volume']).cumsum() / nifty_df['Volume'].cumsum().replace(0, np.nan)
    nifty_ltp = float(nifty_df['Close'].iloc[-1])
    nifty_vwap = float(nifty_df['VWAP'].iloc[-1])
    nifty_prev = float(nifty_df['Close'].iloc[-80]) if len(nifty_df)>80 else float(nifty_df['Close'].iloc[0])
    gap = (nifty_ltp - nifty_prev)/nifty_prev*100
    if nifty_ltp > nifty_vwap and gap > 0.15:
        n_dir = "BULLISH"
    elif nifty_ltp < nifty_vwap and gap < -0.15:
        n_dir = "BEARISH"
    else:
        n_dir = "SIDEWAYS"
    nc1,nc2,nc3,nc4 = st.columns(4)
    nc1.metric("Nifty LTP", f"{nifty_ltp:.2f}", f"{gap:.2f}%")
    nc2.metric("Nifty VWAP", f"{nifty_vwap:.2f}")
    nc3.metric("Direction", n_dir)
    nc4.metric("Mode", "INFO ONLY")
    st.write(f"Nifty {n_dir} hai. Ye sirf jaankari hai. Agar BULLISH hai to CE dekhna, BEARISH hai to PE dekhna, SIDEWAYS hai to NO TRADE hi best hai. Trade ka faisla aapka hai.")
except:
    st.write("Nifty data nahi mila, thodi der baad Refresh karo.")

st.divider()
st.write("1. Ye App Auto Trade NAHI karta. 2. Sirf jaankari deta hai. 3. Trade aap apne Broker App me khud loge. 4. Secret Code sirf is session me hai, GitHub code me nahi hai.")
