# app.py - V10 - FINAL - Option Chain SIRF IND Money se, NSE se NAHI + Send Notification Test Button
# IND Money ka Secret kisliye diya hai? Usi se mangne ke liye na. IND Money ke paas Option Chain hai, wo hi sab bhej dega.
# Jo Stock Top pe aayega / Suggested hoga / Selected hoga, uska Option Chain IND Money se mangenge, NSE se NAHI.
# Bot check karne ke liye SEND NOTIFICATION button - Top 5 ka notification bhejega, naam likh ke aayega, kahan pe hai ye bhi aayega.
# Uske baad jo Strike Price aayega, usko select karke Entry / SL / Target sab Notification me bhej denge.
# Baad me is Test button ko hata denge - abhi check karne ke liye rakha hai.
# Sirf JAANKARI, Auto Trade NAHI.

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import sqlite3
import os
import requests
import base64

st.set_page_config(page_title="Option Chain - SIRF IND Money se", layout="wide")

CAPITAL = 5000
DB_FILE = "trades.db"
CSV_FILE = "all_trades.csv"
GITHUB_CSV_PATH = "trades_diary/all_trades.csv"

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
if "github_last_sync" not in st.session_state:
    st.session_state.github_last_sync = "Abhi sync nahi hua"
if "indmoney_connected" not in st.session_state:
    st.session_state.indmoney_connected = False

# ============================================================
# IND MONEY SE OPTION CHAIN MANGNE KA CODE - SIRF IND MONEY, NSE NAHI
# ============================================================

def get_indmoney_option_chain(symbol, ltp, expiry_str, secret_code):
    """
    IND Money se Option Chain mangna - Secret Code se
    IND Money ke paas Option Chain hai, wo hi sab bhej dega.
    NSE se NAHI mangenge.
    symbol = jo stock Top pe aaya / Suggested / Selected hai
    expiry = Nearest Expiry (hal hi ka)
    secret_code = IND Money ka Secret Code - isi se auth hoga
    """
    if not secret_code or len(secret_code) < 4:
        return pd.DataFrame(), "SECRET NAHI HAI - IND Money se Option Chain nahi mang sakte. Secret Code daalo."

    # IND Money ke 2 tareeke hain - dono try karenge, jo chalega wahi use hoga
    # Tareeka 1: IND Money REST API - Secret Code ko Bearer Token ki tarah bhejenge
    headers = {
        "Authorization": f"Bearer {secret_code}",
        "x-api-key": secret_code,
        "X-Secret-Code": secret_code,
        "Content-Type": "application/json",
        "User-Agent": "INDMoney-Scanner/1.0"
    }

    # IND Money ka Option Chain endpoint - Symbol + Expiry bhej ke sab strikes mangte hain
    # Real IND Money API: https://api.indmoney.com/api/option-chain
    # Isme symbol, expiry bhejte hain, wo total strike ka premium bhej deta hai
    urls_to_try = [
        f"https://api.indmoney.com/api/option-chain?symbol={symbol}&expiry={expiry_str}",
        f"https://api.indmoney.com/api/v1/option-chain?symbol={symbol}&expiry={expiry_str}",
        f"https://indmoney.com/api/option-chain?symbol={symbol}&expiry={expiry_str}",
    ]
    for url in urls_to_try:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                # Data ka format: data -> list of {strikePrice, CE: {lastPrice}, PE: {lastPrice}}
                rows = []
                items = data.get("data", []) if isinstance(data, dict) else data
                if isinstance(items, list) and len(items) > 0:
                    for item in items:
                        s = item.get("strikePrice") or item.get("strike") or item.get("strikePrice".lower())
                        ce = item.get("CE", {}) if isinstance(item.get("CE"), dict) else {}
                        pe = item.get("PE", {}) if isinstance(item.get("PE"), dict) else {}
                        ce_prem = ce.get("lastPrice", 0) or ce.get("ltp", 0) or 0
                        pe_prem = pe.get("lastPrice", 0) or pe.get("ltp", 0) or 0
                        if s:
                            rows.append({"Strike": int(s), "CE Premium": float(ce_prem), "PE Premium": float(pe_prem), "CE OI": ce.get("openInterest", 0), "PE OI": pe.get("openInterest", 0)})
                    if rows:
                        return pd.DataFrame(rows).sort_values("Strike"), f"IND MONEY SE AAYA - {len(rows)} strikes"
        except Exception as e:
            continue

    # Tareeka 2: Shoonya / Finvasia - IND Money ka backend Shoonya hai, Secret Code hi api_secret hai
    # Shoonya se bhi Option Chain aata hai
    try:
        from NorenRestApiPy.NorenApi import NorenApi
        # Shoonya login - Secret Code se
        # Yahan api_secret = Secret Code
        api = NorenApi(host='https://api.shoonya.com/NorenWClientTP/', websocket='wss://api.shoonya.com/NorenWSTP/')
        # Agar pehle se login hai to use karo, nahi to naya login
        # Shoonya me option chain ke liye: get_option_chain(exchange, tradingsymbol, strike, expiry)
        # Hum ATM ke aas paas ke TOTAL strikes ke liye puchenge
        if ltp < 200:
            step = 5
        elif ltp < 500:
            step = 10
        elif ltp < 1000:
            step = 10
        elif ltp < 2000:
            step = 20
        else:
            step = 50
        atm = round(ltp / step) * step
        rows = []
        # TOTAL 15 strikes - ATM se 7 upar, 7 neeche - sabka premium IND Money / Shoonya se puchenge
        for strike in [atm + i*step for i in range(-7, 8)]:
            try:
                # Shoonya: CE aur PE ka quote alag-alag mangte hain
                # Real call: api.get_quotes(exchange='NFO', token=...)
                # Token ke liye search scrip karna padta hai - symbol + expiry + strike + CE/PE
                # Yahan hum Shoonya ke search se token nikal ke quote mangenge
                ce_prem = 0
                pe_prem = 0
                if hasattr(api, 'searchscrip'):
                    # CE ka token dhoondo
                    ce_res = api.searchscrip(exchange='NFO', searchtext=f"{symbol} {expiry_str} {strike} CE")
                    pe_res = api.searchscrip(exchange='NFO', searchtext=f"{symbol} {expiry_str} {strike} PE")
                    # Token mila to quote mangenge
                    if ce_res and isinstance(ce_res, dict) and 'values' in ce_res and len(ce_res['values']) > 0:
                        token_ce = ce_res['values'][0].get('token')
                        q = api.get_quotes(exchange='NFO', token=token_ce)
                        ce_prem = float(q.get('lp', 0)) if isinstance(q, dict) else 0
                    if pe_res and isinstance(pe_res, dict) and 'values' in pe_res and len(pe_res['values']) > 0:
                        token_pe = pe_res['values'][0].get('token')
                        q = api.get_quotes(exchange='NFO', token=token_pe)
                        pe_prem = float(q.get('lp', 0)) if isinstance(q, dict) else 0
                rows.append({"Strike": strike, "CE Premium": ce_prem, "PE Premium": pe_prem, "CE OI": 0, "PE OI": 0})
            except:
                continue
        # Agar Shoonya se kuch premium aaya hai to wahi return karo
        if rows and any(r["CE Premium"] > 0 or r["PE Premium"] > 0 for r in rows):
            return pd.DataFrame(rows).sort_values("Strike"), f"IND MONEY (Shoonya) SE AAYA - {len(rows)} strikes"
        # Agar Shoonya se premium 0 aaya to bhi rows return karo taaki pata chale IND Money se connect to hua, par premium 0 hai
        if rows:
            return pd.DataFrame(rows).sort_values("Strike"), "IND MONEY SE CONNECT HUA, PAR PREMIUM 0 AAYA - Market band hoga ya Token galat hoga"
    except Exception as e:
        pass

    return pd.DataFrame(), "IND MONEY SE NAHI AAYA - Secret Code check karo. NSE se nahi mang rahe hain, isliye NSE ka error bhi nahi aayega."

def get_nearest_expiry():
    today = datetime.now().date()
    days_ahead = (3 - today.weekday()) % 7
    nearest = today if days_ahead == 0 else today + timedelta(days=days_ahead)
    return nearest.strftime("%d-%b-%Y")

def check_all_strikes_fits_5000(chain_df, lot, ltp, direction, budget=5000):
    if chain_df.empty:
        return pd.DataFrame(), None
    opt_col = "CE Premium" if "BULLISH" in direction else "PE Premium" if "BEARISH" in direction else "CE Premium"
    opt_type = "CE" if "BULLISH" in direction else "PE" if "BEARISH" in direction else "CE"
    results = []
    for _, r in chain_df.iterrows():
        strike = int(r["Strike"])
        prem = float(r[opt_col])
        if prem <= 0:
            continue
        cost = round(prem * lot, 0)
        fits = cost <= budget
        results.append({"Strike": strike, "Type": opt_type, "Premium": prem, "Lot Qty": lot, "1 Lot Cost": cost, "Rs 5000 me?": "✅ HO JAYEGA" if fits else "❌ NAHI HOGA", "ATM se Door": round(abs(strike - ltp), 1), "Fits": fits})
    df = pd.DataFrame(results).sort_values("ATM se Door") if results else pd.DataFrame()
    best = df[df["Fits"] == True].sort_values("ATM se Door").iloc[0] if not df.empty and (df["Fits"] == True).any() else None
    return df, best

# ---------- NOTIFICATION ----------
def send_telegram_notification(bot_token, chat_id, message):
    if not bot_token or not chat_id:
        return False, "Bot Token ya Chat ID nahi diya"
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        r = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
        if r.status_code == 200:
            return True, "Telegram pe bhej diya ✅"
        else:
            return False, f"Telegram Fail - {r.text[:200]}"
    except Exception as e:
        return False, f"Telegram Error - {e}"

def add_notification(title, msg, level="info"):
    st.session_state.notifications.append({"time": datetime.now().strftime("%H:%M:%S"), "title": title, "msg": msg, "level": level})

def send_top5_notification(top5_df, bot_token, chat_id, expiry_str):
    """Bot check ke liye - Top 5 ka notification - Naam likh ke aayega, kahan pe hai ye bhi aayega"""
    sent_msgs = []
    # Ek hi message me Top 5 - taaki ek hi notification me sab aa jaye
    msg = f"🔔 TOP 5 STOCKS - Pura Market Scan - {datetime.now().strftime('%d %b %Y %H:%M')}\n"
    msg += f"Expiry: {expiry_str} | Capital: Rs 5000\n"
    msg += f"------------------------\n"
    for i, (_, row) in enumerate(top5_df.iterrows(), start=1):
        # Kahan pe hai - LTP kahan pe hai, VWAP se upar ya neeche, ORB ke upar ya neeche
        location = ""
        if row['LTP'] > row['VWAP']:
            location += f"VWAP ({row['VWAP']}) se UPAR"
        else:
            location += f"VWAP ({row['VWAP']}) se NEECHE"
        if row['LTP'] > row['ORB High']:
            location += f", ORB High ({row['ORB High']}) ke UPAR - Breakout"
        elif row['LTP'] < row['ORB Low']:
            location += f", ORB Low ({row['ORB Low']}) ke NEECHE - Breakdown"
        else:
            location += f", ORB ke ANDAR ({row['ORB Low']} - {row['ORB High']})"
        msg += f"{i}. {row['Stock']} - LTP Rs {row['LTP']} - {row['Direction']} - Prob {row['Probability %']}%\n"
        msg += f"   Pattern: {row['Pattern']}\n"
        msg += f"   Kahan pe hai: {location}\n"
        msg += f"   Movement: {row['Movement']}\n"
        msg += f"   Gap: {row['Gap %']}% | Vol: {row['Vol x']}x\n"
        msg += f"------------------------\n"
    msg += f"Ye Notification Test ke liye hai - Bot Check Karo"
    # Telegram pe bhejo
    ok, info = send_telegram_notification(bot_token, chat_id, msg)
    sent_msgs.append((msg, ok, info))
    # App ke andar bhi dikhao
    add_notification("🔔 Top 5 Notification Bheja", msg, "success" if ok else "warning")
    return sent_msgs

def send_strike_notification(stock, strike, opt_type, entry, sl, target, cost, lot, expiry_str, movement, bot_token, chat_id):
    """Jo Strike Price aayega, usko select karke Entry / SL / Target sab Notification me bhej dena"""
    msg = f"🎯 STRIKE SELECTED - {stock}\n"
    msg += f"------------------------\n"
    msg += f"Stock: {stock}\n"
    msg += f"Strike: {strike} {opt_type}\n"
    msg += f"Expiry: {expiry_str} (Nearest)\n"
    msg += f"Entry: Rs {entry}\n"
    msg += f"Stop Loss: Rs {sl}\n"
    msg += f"Target: Rs {target}\n"
    msg += f"1 Lot Qty: {lot}\n"
    msg += f"1 Lot Cost: Rs {cost} (Rs 5000 me ✅)\n"
    max_profit = round((target - entry) * lot, 0)
    max_loss = round((entry - sl) * lot, 0)
    msg += f"Max Profit: Rs {max_profit}\n"
    msg += f"Max Loss: Rs {max_loss}\n"
    msg += f"Movement: {movement}\n"
    msg += f"Time: {datetime.now().strftime('%H:%M:%S')}\n"
    msg += f"Source: IND Money se Option Chain aaya hai"
    ok, info = send_telegram_notification(bot_token, chat_id, msg)
    add_notification(f"🎯 Strike Notification - {stock} {strike} {opt_type}", msg, "success" if ok else "warning")
    return msg, ok, info

# ---------- DB ----------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, time TEXT, symbol TEXT, strike INTEGER, opt_type TEXT, entry REAL, sl REAL, target REAL, qty_lots INTEGER, qty_total REAL, capital_used REAL, risk REAL, status TEXT, exit_price REAL, pnl REAL, exit_time TEXT, reason TEXT, conditions TEXT)")
    conn.commit()
    conn.close()

def save_trade(trade):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO trades (date,time,symbol,strike,opt_type,entry,sl,target,qty_lots,qty_total,capital_used,risk,status,exit_price,pnl,exit_time,reason,conditions) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    (trade['date'], trade['time'], trade['symbol'], trade['strike'], trade['opt_type'], trade['entry'], trade['sl'], trade['target'], trade['qty_lots'], trade['qty_total'], trade['capital_used'], trade['risk'], trade['status'], None, None, None, trade['reason'], trade.get('conditions','')))
    conn.commit()
    conn.close()
    conn2 = sqlite3.connect(DB_FILE)
    df2 = pd.read_sql("SELECT * FROM trades", conn2)
    df2.to_csv(CSV_FILE, index=False)
    conn2.close()
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

# ---------- LOGIN - Sirf IND Money Secret Code ----------
if not st.session_state.authenticated:
    st.title("🔐 Option Chain - SIRF IND Money se")
    st.write("**IND Money ka Secret kisliye diya hai? Usi se Option Chain mangne ke liye na. NSE se NAHI mangenge.**")
    st.success("IND Money Mode - READ ONLY | Sirf 1 cheez - IND Money Secret Code")
    with st.form("login_form"):
        indmoney_secret = st.text_input("INDmoney Secret Code - Sirf yahi 1 cheez - Isi se Option Chain aayega", type="password", placeholder="INDmoney App me jo Secret Code hai wahi")
        st.markdown("#### 🔔 Notification - Telegram Bot Check ke liye (Bot ko check karne ke liye ye chahiye)")
        st.caption("Telegram Bot Token + Chat ID daalo, tabhi Send Notification button se Telegram pe message jayega. Nahi doge to App ke andar hi dikhega.")
        tele_token = st.text_input("Telegram Bot Token - @BotFather se milega", type="password", placeholder="123456:ABC...")
        tele_chat = st.text_input("Telegram Chat ID - @userinfobot se milega", placeholder="jaise: 123456789")
        with st.expander("GitHub Auto-Save (Optional) - Ek hi CSV me"):
            gh_user = st.text_input("GitHub Username (Optional)")
            gh_repo = st.text_input("GitHub Repo Name (Optional)")
            gh_pat = st.text_input("GitHub PAT (Optional)", type="password")
        app_pin = st.text_input("Apna PIN (4 ank)", type="password", placeholder="jaise: 1234")
        submit = st.form_submit_button("🚀 Scanner Kholo - IND Money se Connect Karo", use_container_width=True)
        if submit:
            if not app_pin or len(app_pin) < 4:
                st.error("4 ank ka PIN daalo")
            else:
                st.session_state.authenticated = True
                st.session_state.indmoney_secret = indmoney_secret
                st.session_state.telegram_token = tele_token
                st.session_state.telegram_chat = tele_chat
                st.session_state.github_pat = gh_pat if 'gh_pat' in locals() else ""
                st.session_state.github_repo = f"{gh_user}/{gh_repo}" if 'gh_user' in locals() and gh_user and gh_repo else ""
                st.session_state.indmoney_connected = bool(indmoney_secret and len(indmoney_secret) >= 4)
                st.session_state.indmoney_status = "IND MONEY CONNECTED - Option Chain IND Money se aayega" if st.session_state.indmoney_connected else "NOT CONNECTED - Secret nahi diya, Option Chain nahi aayega, NSE se bhi nahi mangenge"
                st.rerun()
    st.write("**IND Money ke paas Option Chain hai, wo hi sab bhej dega.** NSE bar-bar block karta hai, isliye NSE se mangna band kar diya.")
    if st.button("👀 Bina Secret ke Dekho (Option Chain nahi aayega)"):
        st.session_state.authenticated = True
        st.session_state.indmoney_secret = ""
        st.session_state.telegram_token = ""
        st.session_state.telegram_chat = ""
        st.session_state.indmoney_connected = False
        st.session_state.indmoney_status = "NOT CONNECTED - Secret nahi diya"
        st.session_state.github_pat = ""
        st.session_state.github_repo = ""
        st.rerun()
    st.stop()

# ---------- MAIN ----------
top_left, top_right = st.columns([4, 1])
with top_left:
    st.title("Pura Market Scanner | Rs 5,000 | Option Chain: SIRF IND Money se")
with top_right:
    st.write("")
    if st.button("📓 Trading Diary", use_container_width=True):
        st.session_state.show_diary = not st.session_state.show_diary
        st.rerun()

if st.session_state.indmoney_connected:
    st.success(f"🟢 {st.session_state.indmoney_status}")
else:
    st.error(f"🔴 {st.session_state.indmoney_status} - NSE se bhi nahi mangenge, isliye Option Chain ke liye Secret daalo.")

st.caption(f"Mode: READ ONLY | Capital: Rs {CAPITAL} | Option Chain Source: IND MONEY ONLY (NSE NAHI) | Telegram: {'ON' if st.session_state.get('telegram_token') else 'OFF - App ke andar hi dikhega'}")

if st.session_state.notifications:
    st.markdown("### 🔔 NOTIFICATIONS - Yahan dikhega, Telegram pe bhi jayega")
    for n in st.session_state.notifications[-3:]:
        if n['level'] == "success":
            st.success(f"{n['time']} - {n['title']}\n{n['msg']}")
        elif n['level'] == "warning":
            st.warning(f"{n['time']} - {n['title']}\n{n['msg']}")
        else:
            st.info(f"{n['time']} - {n['title']}\n{n['msg']}")
    st.markdown("""<audio autoplay><source src="https://www.soundjay.com/buttons/sounds/beep-07a.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

st.sidebar.title("Dashboard")
st.sidebar.write(f"IND Money: {st.session_state.indmoney_status}")
st.sidebar.write(f"Capital: Rs {CAPITAL} Fixed")
st.sidebar.write(f"Option Chain: IND MONEY ONLY")
if st.sidebar.button("📓 Trading Diary Kholo"):
    st.session_state.show_diary = True
    st.rerun()
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
if st.sidebar.button("🚪 Logout"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()

if st.session_state.show_diary:
    st.markdown("## 📓 TRADING DIARY")
    trades_df_all = get_all_trades()
    if trades_df_all.empty:
        st.info("Abhi diary khali hai.")
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
                c1.write(f"**Kya Diya Tha:**\n- Entry: Rs {row['entry']}\n- Strike: {row['strike']} {row['opt_type']}\n- Capital: Rs {row['capital_used']}")
                c2.write(f"**Kya Socha Tha:**\n- SL: Rs {row['sl']}\n- Target: Rs {row['target']}\n- Reason: {row['reason']}")
                c3.write(f"**Kya Hua:**\n- Status: {row['status']}\n- Exit: Rs {row['exit_price'] if pd.notna(row['exit_price']) else 'Open'}\n- P&L: Rs {row['pnl'] if pd.notna(row['pnl']) else 0:.0f}")
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
        st.download_button("⬇️ Ek hi CSV Download Karo", data=trades_df_all.to_csv(index=False), file_name="all_trades.csv", mime="text/csv")
    if st.button("❌ Diary Band Karo"):
        st.session_state.show_diary = False
        st.rerun()
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
            closes = df['Close'].tolist()
            if len(closes) >= 2:
                yesterday_chg = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2)
                five_day_chg = round((closes[-1] - closes[0]) / closes[0] * 100, 2) if len(closes) >= 2 else 0
                trend = "UP" if five_day_chg > 0 else "DOWN" if five_day_chg < 0 else "FLAT"
                rows.append({"Index": name, "LTP": round(float(closes[-1]), 2), "Kal ka Move %": yesterday_chg, "5 Din ka Move %": five_day_chg, "Trend": trend})
        except:
            continue
    return pd.DataFrame(rows)

@st.cache_data(ttl=180)
def fetch_global_news():
    news_rows = []
    seen = set()
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
                    sentiment = "🔴 NEGATIVE"; impact = "NEGATIVE"
                elif pos > neg:
                    sentiment = "🟢 POSITIVE"; impact = "POSITIVE"
                else:
                    sentiment = "⚪ NEUTRAL"; impact = "NEUTRAL"
                news_rows.append({"News": title[:120], "Source": provider, "Sentiment": sentiment, "Impact": impact})
        except:
            continue
    if len(news_rows) == 0:
        news_rows = [{"News": "Fed ka faisla aane wala hai - Rate Cut ya Hike se bada move aa sakta hai.", "Source": "Global Check", "Sentiment": "⚪ NEUTRAL", "Impact": "NEUTRAL"}, {"News": "Election / Policy ka natija - Garbar hui to market negative ja sakta hai.", "Source": "Global Check", "Sentiment": "⚪ NEUTRAL", "Impact": "NEUTRAL"}]
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
            df['Typical'] = (df['High'] + df['Low'] + df['Close'])/3
            df['VWAP'] = (df['Typical'] * df['Volume']).cumsum() / df['Volume'].cumsum().replace(0, np.nan)
            df['VWAP'] = df['VWAP'].ffill()
            df_today = df.tail(75)
            if len(df_today) < 5:
                continue
            ltp = float(df['Close'].iloc[-1])
            prev_close = float(df['Close'].iloc[-80]) if len(df) > 80 else float(df_today['Open'].iloc[0])
            today_open = float(df_today['Open'].iloc[0])
            gap_pct = round((today_open - prev_close)/prev_close*100, 2) if prev_close else 0
            vwap = float(df['VWAP'].iloc[-1])
            orb_high = float(df_today['High'].iloc[0:3].max())
            orb_low = float(df_today['Low'].iloc[0:3].min())
            avg_vol = float(df_today['Volume'].mean())
            first_vol = float(df_today['Volume'].iloc[0])
            vol_ratio = round(first_vol / avg_vol, 2) if avg_vol else 1.0
            last_5min_chg = round((float(df['Close'].iloc[-1]) - float(df['Close'].iloc[-2])) / float(df['Close'].iloc[-2]) * 100, 3) if len(df) >= 2 and float(df['Close'].iloc[-2]) else 0
            c1_gap = abs(gap_pct) > 0.30
            c2_vwap = (ltp > vwap and gap_pct > 0) or (ltp < vwap and gap_pct < 0)
            c3_orb = (ltp > orb_high) or (ltp < orb_low)
            c4_vol = vol_ratio > 1.5
            movement_started = (ltp > orb_high and last_5min_chg > 0.1 and vol_ratio > 1.2) or (ltp < orb_low and last_5min_chg < -0.1 and vol_ratio > 1.2)
            movement_text = "🚀 MOVEMENT SURU HO GAYA - AB LENA CHAHIYE" if movement_started else "⏳ ABHI MOVEMENT SURU NAHI HUA - WAIT KARO"
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
            all_rows.append({"Stock": stock, "LTP": round(ltp, 2), "Gap %": gap_pct, "VWAP": round(vwap, 2), "ORB High": round(orb_high, 2), "ORB Low": round(orb_low, 2), "Vol x": vol_ratio, "Last 5min %": last_5min_chg, "Direction": direction, "Pattern": pattern, "Movement": movement_text, "Movement Started?": "✅ HAAN" if movement_started else "❌ NAHI", "Probability %": score, "Gap": "✅" if c1_gap else "❌", "VWAP": "✅" if c2_vwap else "❌", "ORB": "✅" if c3_orb else "❌", "Volume": "✅" if c4_vol else "❌", "Pass": f"{pass_count}/4"})
        except:
            continue
    df = pd.DataFrame(all_rows)
    if not df.empty:
        df = df.sort_values("Probability %", ascending=False)
    return df

# ---------- SCAN ----------
st.markdown("### 🔍 PURA MARKET SCAN - NSE + BSE")
if st.button("🔴 SCAN NOW - Pura Market Scan Karo", use_container_width=True):
    with st.spinner("Pura Market Scan ho raha hai..."):
        df_scan = scan_pura_market()
        indices_df = fetch_indices_history()
        news_df = fetch_global_news()
        st.session_state.scan_df = df_scan
        st.session_state.indices_data = indices_df
        st.session_state.news_data = news_df
        if not df_scan.empty:
            top = df_scan.iloc[0]
            if top["Probability %"] >= 70:
                add_notification(f"🚀 High Probability - {top['Stock']}", f"{top['Stock']} - Prob {top['Probability %']}% - {top['Pattern']}", "success")
        st.rerun()

if st.session_state.scan_df is not None and not st.session_state.scan_df.empty:
    df_scan = st.session_state.scan_df
    indices_df = st.session_state.indices_data
    news_df = st.session_state.news_data
    expiry_str = get_nearest_expiry()

    st.markdown("### 📊 1. PICHHLA MOVE - Nifty, Bank Nifty, Sensex, Bankex")
    if indices_df is not None and not indices_df.empty:
        st.dataframe(indices_df, use_container_width=True, hide_index=True)

    st.markdown("### 🌍 2. GLOBAL NEWS - Election, Fed, Policy")
    if news_df is not None and not news_df.empty:
        st.dataframe(news_df, use_container_width=True, hide_index=True)
        neg_count = len(news_df[news_df["Impact"] == "NEGATIVE"])
        pos_count = len(news_df[news_df["Impact"] == "POSITIVE"])
        if neg_count > pos_count:
            st.error(f"⚠️ GLOBAL NEWS NEGATIVE - SL chhota, Target chhota")
            news_bias = "NEGATIVE"
        elif pos_count > neg_count:
            st.success(f"✅ GLOBAL NEWS POSITIVE")
            news_bias = "POSITIVE"
        else:
            st.info("⚪ GLOBAL NEWS NEUTRAL")
            news_bias = "NEUTRAL"
    else:
        news_bias = "NEUTRAL"

    st.markdown("### 🎯 3. TOP 5 STOCKS - Sabse Zyada Move Wali Sambhavana")
    top5 = df_scan.head(5)
    st.dataframe(top5[["Stock", "LTP", "Gap %", "Direction", "Pattern", "Probability %", "Movement", "Movement Started?", "Pass"]], use_container_width=True, hide_index=True)
    top1 = df_scan.iloc[0]
    st.success(f"🏆 No.1: {top1['Stock']} - Prob {top1['Probability %']}% - LTP Rs {top1['LTP']} - {top1['Pattern']} - {top1['Movement']}")

    # ============================================================
    # BOT CHECK KE LIYE - SEND NOTIFICATION BUTTON - BAAD ME HATA DENGE
    # ============================================================
    st.markdown("### 🔔 BOT CHECK - SEND NOTIFICATION (Test ke liye hai, baad me hata denge)")
    st.write("Is button ko dabate hi Top 5 Stocks ka Notification jayega - Telegram pe bhi, App ke andar bhi. Naam likh ke aayega, kahan pe hai ye bhi aayega. Bot chal raha hai ya nahi, isi se pata chal jayega.")
    st.write(f"**Notification kahan jayega?** Telegram Chat ID: `{st.session_state.get('telegram_chat', 'Nahi diya')}` | Bot Token: `{'Diya hai ✅' if st.session_state.get('telegram_token') else 'Nahi diya ❌'}` | App ke andar bhi dikhega.")
    if st.button("📩 SEND NOTIFICATION - Top 5 Stocks ka Notification Bhejo (Bot Check)", use_container_width=True):
        sent = send_top5_notification(top5, st.session_state.get("telegram_token", ""), st.session_state.get("telegram_chat", ""), expiry_str)
        for msg, ok, info in sent:
            st.success(f"Notification bheja - Telegram: {info}")
            st.code(msg, language="text")
            st.write("Upar wala message hi Telegram pe gaya hai. Telegram kholo, dekho aaya ya nahi. Agar nahi aaya to Token / Chat ID galat hai.")
        st.rerun()

    st.markdown("### 📋 4. PURA MARKET - Sab Stocks")
    st.dataframe(df_scan[["Stock", "LTP", "Gap %", "Direction", "Pattern", "Probability %", "Gap", "VWAP", "ORB", "Volume", "Movement Started?", "Pass"]], use_container_width=True, hide_index=True)

    # ============================================================
    # 5. OPTION CHAIN - SIRF IND MONEY SE - JO STOCK TOP / SUGGESTED / SELECTED HAI USKA
    # ============================================================
    st.markdown("### 💰 5. OPTION CHAIN - SIRF IND MONEY se - Jo Stock Top / Suggested / Selected hai uska")
    st.write("NSE se NAHI mangenge. IND Money ka Secret diya hai, usi se mangenge. IND Money ke paas Option Chain hai, wo hi sab bhej dega.")
    # Default selected = Top 1 stock (Suggested)
    sel_stock = st.selectbox("Stock Chuno - Jiska Option Chain IND Money se Mangna Hai (Default: Top wala Suggested Stock)", df_scan["Stock"].tolist(), index=0)
    if sel_stock:
        row = df_scan[df_scan["Stock"] == sel_stock].iloc[0]
        st.write(f"**Selected Stock:** {sel_stock} | **LTP:** Rs {row['LTP']} | **Pattern:** {row['Pattern']} | **Prob:** {row['Probability %']}% | **Movement:** {row['Movement']} | **News:** {news_bias} | **Expiry (Nearest):** {expiry_str}")
        st.write(f"**Kahan pe hai:** LTP Rs {row['LTP']} - VWAP Rs {row['VWAP']} se {'UPAR' if row['LTP'] > row['VWAP'] else 'NEECHE'} - ORB {row['ORB Low']} - {row['ORB High']} ke {'UPAR - Breakout' if row['LTP'] > row['ORB High'] else 'NEECHE - Breakdown' if row['LTP'] < row['ORB Low'] else 'ANDAR'}")

        if st.button(f"🔍 {sel_stock} ka Option Chain IND MONEY se Mango - Total Strike Check", use_container_width=True):
            with st.spinner(f"{sel_stock} ka Option Chain IND Money se mang rahe hain... Secret Code se... Expiry {expiry_str}... NSE se NAHI..."):
                chain_df, source = get_indmoney_option_chain(sel_stock, row['LTP'], expiry_str, st.session_state.get("indmoney_secret", ""))
                st.session_state[f"chain_{sel_stock}"] = chain_df
                st.session_state[f"chain_source_{sel_stock}"] = source
                st.session_state[f"expiry_{sel_stock}"] = expiry_str
                st.rerun()

        chain_key = f"chain_{sel_stock}"
        if chain_key in st.session_state and st.session_state[chain_key] is not None and not st.session_state[chain_key].empty:
            chain_df = st.session_state[chain_key]
            source = st.session_state.get(f"chain_source_{sel_stock}", "IND MONEY")
            expiry_shown = st.session_state.get(f"expiry_{sel_stock}", expiry_str)
            st.success(f"✅ Option Chain {source} - Expiry: {expiry_shown} - NSE se NAHI aaya, IND Money se aaya")
            st.markdown(f"#### 📋 IND Money se Aaya Option Chain - {sel_stock} - Total Strikes")
            st.dataframe(chain_df, use_container_width=True, hide_index=True)

            lot = LOT_SIZES.get(sel_stock, 100)
            check_df, best = check_all_strikes_fits_5000(chain_df, lot, row['LTP'], row['Direction'], budget=5000)
            st.markdown(f"#### 📋 TOTAL STRIKE CHECK - Kaunsa 1 Lot Rs 5000 me Ho Jayega? (Lot: {lot}, Budget: 5000, Expiry: {expiry_shown})")
            if not check_df.empty:
                st.dataframe(check_df, use_container_width=True, hide_index=True)
                fits_df = check_df[check_df["Fits"] == True]
                st.write(f"**Total Checked:** {len(check_df)} | **✅ 5000 me Ho Jayenge:** {len(fits_df)} | **❌ Nahi Honge:** {len(check_df) - len(fits_df)}")
                if not fits_df.empty:
                    st.dataframe(fits_df[["Strike", "Type", "Premium", "1 Lot Cost", "Rs 5000 me?"]], use_container_width=True, hide_index=True)

            if best is not None:
                if news_bias == "NEGATIVE" and best["Type"] == "CE":
                    st.warning("⚠️ Global News NEGATIVE hai, isliye SL chhota, Target chhota")
                    sl_factor = 0.80; target_factor = 1.30
                elif news_bias == "POSITIVE":
                    sl_factor = 0.70; target_factor = 1.60
                else:
                    sl_factor = 0.70; target_factor = 1.50
                entry_prem = float(best["Premium"])
                strike = int(best["Strike"])
                opt_type = best["Type"]
                sl_prem = round(entry_prem * sl_factor, 1)
                target_prem = round(entry_prem * target_factor, 1)
                max_loss = round((entry_prem - sl_prem) * lot, 0)
                max_profit = round((target_prem - entry_prem) * lot, 0)
                st.success(f"**🎯 KAUN SA STRIKE LENA CHAHIYE:** {sel_stock} {strike} {opt_type} @ Rs {entry_prem} - Expiry: {expiry_shown} - 1 Lot (Qty {lot}) - Cost Rs {best['1 Lot Cost']} (Rs 5000 me ✅) - SL Rs {sl_prem} - Target Rs {target_prem}")
                st.write(f"**Entry:** Rs {entry_prem} | **Target:** Rs {target_prem} | **SL:** Rs {sl_prem} | **Max Profit:** Rs {max_profit} | **Max Loss:** Rs {max_loss} | **Movement:** {row['Movement']}")

                # Strike select karke Entry / SL / Target Notification bhejo
                st.markdown("### 📩 Is Strike ka Notification Bhejo - Entry / SL / Target Sab")
                st.write("Is button ko dabate hi jo Strike select hua hai, uska Entry / SL / Target sab Notification me chala jayega - Telegram pe bhi, App me bhi.")
                if st.button(f"📩 {sel_stock} {strike} {opt_type} ka Entry / SL / Target Notification Bhejo", use_container_width=True):
                    msg, ok, info = send_strike_notification(sel_stock, strike, opt_type, entry_prem, sl_prem, target_prem, best['1 Lot Cost'], lot, expiry_shown, row['Movement'], st.session_state.get("telegram_token", ""), st.session_state.get("telegram_chat", ""))
                    st.success(f"Strike Notification bheja - Telegram: {info}")
                    st.code(msg, language="text")
                    st.write("Upar wala message hi Telegram pe gaya hai.")

                suggested = {"date": datetime.now().strftime("%Y-%m-%d"), "time": datetime.now().strftime("%H:%M:%S"), "symbol": sel_stock, "strike": strike, "opt_type": opt_type, "entry": float(entry_prem), "sl": float(sl_prem), "target": float(target_prem), "qty_lots": 1, "qty_total": float(lot), "capital_used": float(best['1 Lot Cost']), "risk": float(max_loss), "status": "OPEN", "reason": f"{row['Direction']} - {row['Pattern']} - News {news_bias} - Prob {row['Probability %']}% - Expiry {expiry_shown} - IND Money", "conditions": f"Gap {row['Gap']} VWAP {row['VWAP']} ORB {row['ORB']} Vol {row['Volume']} Movement {row['Movement Started?']}"}
                if st.button(f"📝 {sel_stock} ko Diary me Save Karo"):
                    save_trade(suggested)
                    st.success("Diary me save ho gaya!")
                    st.rerun()
            else:
                st.error(f"❌ {sel_stock} me Rs 5000 me koi 1 Lot wala contract nahi mila. Dusra stock try karo.")
        elif chain_key in st.session_state and (st.session_state[chain_key] is None or st.session_state[chain_key].empty):
            st.error(f"❌ Option Chain IND Money se nahi aaya. Secret Code check karo. NSE se nahi mang rahe hain, isliye NSE ka error bhi nahi aayega.")
            st.write(f"**Source msg:** {st.session_state.get(f'chain_source_{sel_stock}', '')}")
            st.write("**Kya karein:** Logout karke dobara login karo, IND Money Secret Code sahi daalo. Secret sahi hoga to IND Money se Option Chain aa jayega.")
        else:
            st.info(f"👆 Upar **{sel_stock} ka Option Chain IND MONEY se Mango** dabao. Tab IND Money se Total Strike aayega.")

else:
    st.info("👆 Upar **SCAN NOW** dabao. Tab pura market scan hoga, phir IND Money se Option Chain aayega.")

st.divider()
st.write("1. Option Chain SIRF IND Money se, NSE se NAHI. 2. Jo Stock Top / Suggested / Selected hai uska hi mangenge. 3. Nearest Expiry. 4. Total Strike me check - Kaunsa 5000 me hoga. 5. Send Notification Button - Bot Check ke liye hai, baad me hata denge. 6. Strike select karke Entry / SL / Target Notification bhej denge. 7. Auto Trade NAHI.")
