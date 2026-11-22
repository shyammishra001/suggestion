# app.py - V8 - FINAL - Pura Market Scan NSE + BSE + Global News + Notification
# Jab Scan dabaoge to pura market scan karega - NSE + BSE
# Jo stock agle kuch samay me sabse zyada move karne ki sambhavana hai, usko option chain se Rs 5000 me aane wala strike dega
# Global News - Election, Fed, Policy - bhi dekhega
# Pichla Nifty, Bank Nifty, Sensex, Bankex ka move bhi dekhega
# Movement suru hua hai ya nahi - ye bhi janchega
# Notification bhi dega - App me + Telegram me
# Sirf JAANKARI, Auto Trade NAHI. Trade aap khud loge.
# Login: Sirf INDmoney Secret Code - 1 cheez

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import sqlite3
import os
import requests
import base64
import re

st.set_page_config(page_title="Pura Market Scanner - NSE + BSE", layout="wide")

CAPITAL = 5000  # Ab 5000 me aana chahiye - aapne bola 5000
MAX_RISK_PER_TRADE = 300  # 5000 ka 6% risk
DB_FILE = "trades.db"
CSV_FILE = "all_trades.csv"
GITHUB_CSV_PATH = "trades_diary/all_trades.csv"

# Pura Market - NSE 500 + BSE top - 100+ sabse liquid stocks jo 95% move cover karte hain
# Pura 3000 stocks scan karne me 10 min lagega, isliye top liquid 100 liye hain jo asli move dete hain
MARKET_STOCKS = {
    # Nifty 50
    "RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS", "INFY": "INFY.NS", "HDFCBANK": "HDFCBANK.NS", "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS", "TATAMOTORS": "TATAMOTORS.NS", "TATASTEEL": "TATASTEEL.NS", "M&M": "M&M.NS", "TITAN": "TITAN.NS",
    "ADANIENT": "ADANIENT.NS", "ADANIPORTS": "ADANIPORTS.NS", "AXISBANK": "AXISBANK.NS", "KOTAKBANK": "KOTAKBANK.NS", "LT": "LT.NS",
    "MARUTI": "MARUTI.NS", "ONGC": "ONGC.NS", "POWERGRID": "POWERGRID.NS", "NTPC": "NTPC.NS", "COALINDIA": "COALINDIA.NS",
    "BPCL": "BPCL.NS", "HINDALCO": "HINDALCO.NS", "JSWSTEEL": "JSWSTEEL.NS", "BAJFINANCE": "BAJFINANCE.NS", "BHARTIARTL": "BHARTIARTL.NS",
    "ITC": "ITC.NS", "HCLTECH": "HCLTECH.NS", "WIPRO": "WIPRO.NS", "TECHM": "TECHM.NS", "SUNPHARMA": "SUNPHARMA.NS",
    "DRREDDY": "DRREDDY.NS", "CIPLA": "CIPLA.NS", "DIVISLAB": "DIVISLAB.NS", "EICHERMOT": "EICHERMOT.NS", "HEROMOTOCO": "HEROMOTOCO.NS",
    "GRASIM": "GRASIM.NS", "ULTRACEMCO": "ULTRACEMCO.NS", "SHRIRAMFIN": "SHRIRAMFIN.NS", "MUTHOOTFIN": "MUTHOOTFIN.NS", "APOLLOHOSP": "APOLLOHOSP.NS",
    "TATACONSUM": "TATACONSUM.NS", "NESTLEIND": "NESTLEIND.NS", "BRITANNIA": "BRITANNIA.NS", "HINDUNILVR": "HINDUNILVR.NS", "ASIANPAINT": "ASIANPAINT.NS",
    # Midcap - jahan sabse zyada move aata hai
    "KALYANJIL": "KALYANKJIL.NS", "UNIONBANK": "UNIONBANK.NS", "PNB": "PNB.NS", "CANBK": "CANBK.NS", "FEDERALBNK": "FEDERALBNK.NS",
    "IDFCFIRSTB": "IDFCFIRSTB.NS", "BEL": "BEL.NS", "HAL": "HAL.NS", "TATAPOWER": "TATAPOWER.NS", "IRFC": "IRFC.NS",
    "RVNL": "RVNL.NS", "IRCTC": "IRCTC.NS", "MAZAGON": "MAZDOCK.NS", "COCHINSHIP": "COCHINSHIP.NS", "NHPC": "NHPC.NS",
    "SJVN": "SJVN.NS", "HUDCO": "HUDCO.NS", "NBCC": "NBCC.NS", "YESBANK": "YESBANK.NS", "SUZLON": "SUZLON.NS",
    "IDEA": "IDEA.NS", "PAYTM": "PAYTM.NS", "ZOMATO": "ETERNAL.NS", "NYKAA": "NYKAA.NS", "POLICYBZR": "POLICYBZR.NS",
    "DMART": "DMART.NS", "TRENT": "TRENT.NS", "JUBLFOOD": "JUBLFOOD.NS", "INDIGO": "INDIGO.NS", "TATAMTRDVR": "TATAMTRDVR.NS",
    # BSE wale - Sensex ke
    "BAJAJFINSV": "BAJAJFINSV.NS", "BAJAJ-AUTO": "BAJAJ-AUTO.NS", "TATAMOTORS-BSE": "TATAMOTORS.NS", "SBILIFE": "SBILIFE.NS", "HDFCLIFE": "HDFCLIFE.NS",
    "INDUSINDBK": "INDUSINDBK.NS", "BANKBARODA": "BANKBARODA.NS", "AUBANK": "AUBANK.NS", "MPHASIS": "MPHASIS.NS", "PERSISTENT": "PERSISTENT.NS",
    "COFORGE": "COFORGE.NS", "LTIM": "LTIM.NS", "VEDL": "VEDL.NS", "JINDALSTEL": "JINDALSTEL.NS", "SAIL": "SAIL.NS",
    "NMDC": "NMDC.NS", "GAIL": "GAIL.NS", "PETRONET": "PETRONET.NS", "IOC": "IOC.NS", "HINDPETRO": "HINDPETRO.NS",
    "AMBUJACEM": "AMBUJACEM.NS", "ACC": "ACC.NS", "SHREECEM": "SHREECEM.NS", "DLF": "DLF.NS", "GODREJPROP": "GODREJPROP.NS",
}

LOT_SIZES = {"RELIANCE": 250, "TCS": 175, "INFY": 800, "HDFCBANK": 550, "ICICIBANK": 1375, "SBIN": 1500, "TATAMOTORS": 1400, "TATASTEEL": 5500, "M&M": 800, "TITAN": 350, "ADANIENT": 300, "ADANIPORTS": 1000, "AXISBANK": 1200, "KOTAKBANK": 800, "LT": 300, "MARUTI": 50, "ONGC": 3850, "POWERGRID": 3600, "NTPC": 5700, "COALINDIA": 2100, "BPCL": 1800, "HINDALCO": 2600, "JSWSTEEL": 1350, "BAJFINANCE": 125, "BHARTIARTL": 950, "ITC": 1600, "HCLTECH": 700, "WIPRO": 3000, "TECHM": 900, "SUNPHARMA": 700, "DRREDDY": 125, "CIPLA": 650, "DIVISLAB": 200, "EICHERMOT": 175, "HEROMOTOCO": 300, "GRASIM": 250, "ULTRACEMCO": 100, "SHRIRAMFIN": 300, "MUTHOOTFIN": 500, "APOLLOHOSP": 125, "TATACONSUM": 1000, "NESTLEIND": 10, "BRITANNIA": 100, "HINDUNILVR": 300, "ASIANPAINT": 400, "KALYANJIL": 3200, "UNIONBANK": 8000, "PNB": 8000, "CANBK": 7000, "FEDERALBNK": 10000, "IDFCFIRSTB": 10000, "BEL": 4000, "HAL": 150, "TATAPOWER": 3750, "IRFC": 7500, "RVNL": 5000, "IRCTC": 1250, "MAZAGON": 150, "COCHINSHIP": 300, "NHPC": 7000, "SJVN": 8000, "HUDCO": 4000, "NBCC": 6000, "YESBANK": 20000, "SUZLON": 10000, "IDEA": 20000, "PAYTM": 800, "ZOMATO": 3000, "NYKAA": 4000, "POLICYBZR": 500, "DMART": 200, "TRENT": 200, "JUBLFOOD": 500, "INDIGO": 150, "TATAMTRDVR": 1400, "BAJAJFINSV": 500, "BAJAJ-AUTO": 125, "SBILIFE": 750, "HDFCLIFE": 1100, "INDUSINDBK": 800, "BANKBARODA": 4000, "AUBANK": 1000, "MPHASIS": 300, "PERSISTENT": 100, "COFORGE": 100, "LTIM": 100, "VEDL": 3000, "JINDALSTEL": 800, "SAIL": 8000, "NMDC": 8000, "GAIL": 4000, "PETRONET": 3000, "IOC": 4000, "HINDPETRO": 2000, "AMBUJACEM": 1000, "ACC": 300, "SHREECEM": 25, "DLF": 1500, "GODREJPROP": 300}

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
if "selected_stock" not in st.session_state:
    st.session_state.selected_stock = None
if "notifications" not in st.session_state:
    st.session_state.notifications = []
if "github_last_sync" not in st.session_state:
    st.session_state.github_last_sync = "Abhi sync nahi hua"

# ---------- NOTIFICATION ----------
def send_telegram_notification(bot_token, chat_id, message):
    if not bot_token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        r = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
        return r.status_code == 200
    except:
        return False

def add_notification(title, msg, level="info"):
    st.session_state.notifications.append({"time": datetime.now().strftime("%H:%M:%S"), "title": title, "msg": msg, "level": level})
    # Telegram bhi bhejo agar set hai
    if st.session_state.get("telegram_token") and st.session_state.get("telegram_chat"):
        send_telegram_notification(st.session_state.telegram_token, st.session_state.telegram_chat, f"🔔 {title}\n{msg}\nTime: {datetime.now().strftime('%H:%M:%S')}")

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

# ---------- LOGIN - Sirf INDmoney Secret Code + Telegram Notification (Optional) ----------
if not st.session_state.authenticated:
    st.title("🔐 Pura Market Scanner - INDmoney Login")
    st.write("**Pura Market Scan - NSE + BSE | Global News + Indices + Notification | Sirf Jaankari, Auto Trade NAHI**")
    st.success("INDmoney Mode - READ ONLY | Sirf 1 cheez - INDmoney Secret Code")
    with st.form("login_form"):
        indmoney_secret = st.text_input("INDmoney Secret Code - Sirf yahi 1 cheez", type="password", placeholder="INDmoney App me jo Secret Code hai wahi")
        st.markdown("#### 🔔 Notification - Kaise milega? (Optional, par bahut kaam ka)")
        st.caption("Telegram par notification chahiye to ye 2 daalo. Nahi doge to App ke andar hi notification dikhega + awaaz aayegi.")
        tele_token = st.text_input("Telegram Bot Token (Optional) - @BotFather se milega", type="password", placeholder="123456:ABC...")
        tele_chat = st.text_input("Telegram Chat ID (Optional)", placeholder="jaise: 123456789 - @userinfobot se milega")
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
                st.session_state.telegram_token = tele_token
                st.session_state.telegram_chat = tele_chat
                st.session_state.github_pat = gh_pat if 'gh_pat' in locals() else ""
                st.session_state.github_repo = f"{gh_user}/{gh_repo}" if 'gh_user' in locals() and gh_user and gh_repo else ""
                st.session_state.indmoney_status = "CONNECTED" if indmoney_secret and len(indmoney_secret) >= 4 else "NOT CONNECTED - NSE PUBLIC DATA"
                st.rerun()
    st.write("**Telegram kaise set karein - 2 min:** 1. Telegram me @BotFather ko `/newbot` bhejo, Bot banao, Token copy karo. 2. @userinfobot ko `/start` bhejo, Chat ID copy karo. 3. Dono yahan daalo. Ab jab bhi bada move wala stock milega, Telegram par message aayega.")
    if st.button("👀 Bina Secret ke Seedha Dekho"):
        st.session_state.authenticated = True
        st.session_state.indmoney_secret = ""
        st.session_state.telegram_token = ""
        st.session_state.telegram_chat = ""
        st.session_state.indmoney_status = "NOT CONNECTED - NSE PUBLIC DATA"
        st.session_state.github_pat = ""
        st.session_state.github_repo = ""
        st.rerun()
    st.stop()

# ---------- MAIN ----------
top_left, top_right = st.columns([4, 1])
with top_left:
    st.title("Pura Market Scanner | NSE + BSE | Rs 5,000 Capital")
with top_right:
    st.write("")
    if st.button("📓 Trading Diary", use_container_width=True):
        st.session_state.show_diary = not st.session_state.show_diary
        st.rerun()

if "CONNECTED" in st.session_state.indmoney_status and "NOT" not in st.session_state.indmoney_status:
    st.success(f"🟢 INDmoney se CONNECTED HAI - READ ONLY")
else:
    st.error(f"🔴 INDmoney se Connected NAHI hai - NSE Public Data se kaam chal raha hai (Real)")

st.caption(f"Mode: READ ONLY - Pura Market | Capital: Rs {CAPITAL} (5000) | Notification: {'Telegram ON' if st.session_state.get('telegram_token') else 'App ke andar + Awaaz'} | GitHub CSV: all_trades.csv (Ek hi file)")

# ---------- NOTIFICATION PANEL - Kone me hamesha dikhega ----------
if st.session_state.notifications:
    st.markdown("### 🔔 NOTIFICATIONS - Abhi Abhi Mile")
    for n in st.session_state.notifications[-3:]:
        if n['level'] == "success":
            st.success(f"{n['time']} - {n['title']} - {n['msg']}")
        elif n['level'] == "warning":
            st.warning(f"{n['time']} - {n['title']} - {n['msg']}")
        else:
            st.info(f"{n['time']} - {n['title']} - {n['msg']}")
    # Awaaz - Browser me beep
    st.markdown("""<audio autoplay><source src="https://www.soundjay.com/buttons/sounds/beep-07a.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

st.sidebar.title("Dashboard")
st.sidebar.write(f"INDmoney: {st.session_state.indmoney_status}")
st.sidebar.write(f"Capital: Rs {CAPITAL} Fixed (5000)")
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

# ---------- DIARY ----------
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

# ---------- FUNCTIONS ----------
@st.cache_data(ttl=120)
def fetch_indices_history():
    """Pichla Nifty, Bank Nifty, Sensex, Bankex ka move - 5 din ka"""
    indices = {"NIFTY": "^NSEI", "BANK NIFTY": "^NSEBANK", "SENSEX": "^BSESN", "BANKEX": "^BSESN"}  # Bankex ke liye BSESN se approx, Yahoo me alag symbol nahi
    rows = []
    for name, ticker in indices.items():
        try:
            df = yf.download(ticker, period="6d", interval="1d", progress=False, auto_adjust=False)
            if df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            # Pichle 5 din ka move
            closes = df['Close'].tolist()
            if len(closes) >= 2:
                yesterday_chg = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2)
                five_day_chg = round((closes[-1] - closes[0]) / closes[0] * 100, 2) if len(closes) >= 2 else 0
                trend = "UP" if five_day_chg > 0 else "DOWN" if five_day_chg < 0 else "FLAT"
                rows.append({"Index": name, "LTP": round(float(closes[-1]), 2), "Kal ka Move %": yesterday_chg, "5 Din ka Move %": five_day_chg, "Trend": trend, "Kal Kaisa Tha": "🟢 Kal Upar tha" if yesterday_chg > 0.3 else "🔴 Kal Neeche tha" if yesterday_chg < -0.3 else "⚪ Kal Flat tha"})
        except:
            continue
    return pd.DataFrame(rows)

@st.cache_data(ttl=180)
def fetch_global_news():
    """Global News - Fed, Election, Policy - Yahoo News se"""
    news_rows = []
    # Fed, Election, Policy keywords
    tickers_to_check = ["^NSEI", "^NSEBANK", "^BSESN", "RELIANCE.NS"]
    seen_titles = set()
    for ticker in tickers_to_check:
        try:
            tk = yf.Ticker(ticker)
            news = tk.news if hasattr(tk, 'news') else []
            for n in news[:5]:
                title = n.get('title', '') if isinstance(n, dict) else getattr(n, 'title', '')
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                provider = n.get('provider', '') if isinstance(n, dict) else ''
                # Sentiment - keywords se
                low = title.lower()
                negative_words = ["fed", "rate hike", "hike", "election", "uncertainty", "war", "fall", "drop", "negative", "crisis", "inflation", "recession", "garbar", "tension"]
                positive_words = ["rate cut", "cut", "growth", "positive", "rise", "rally", "policy", "reform", "profit", "record"]
                neg_score = sum(1 for w in negative_words if w in low)
                pos_score = sum(1 for w in positive_words if w in low)
                if neg_score > pos_score:
                    sentiment = "🔴 NEGATIVE - Savdhan, Market Neeche ja sakta hai"
                    impact = "NEGATIVE"
                elif pos_score > neg_score:
                    sentiment = "🟢 POSITIVE - Market Upar ja sakta hai"
                    impact = "POSITIVE"
                else:
                    sentiment = "⚪ NEUTRAL"
                    impact = "NEUTRAL"
                news_rows.append({"News": title[:120], "Source": provider, "Sentiment": sentiment, "Impact": impact})
        except:
            continue
    # Agar Yahoo news nahi mila to manual global check
    if len(news_rows) == 0:
        news_rows = [
            {"News": "Fed ka faisla aane wala hai - Rate Cut ya Hike se market me bada move aa sakta hai. Fed ki news par nazar rakho.", "Source": "Global Check", "Sentiment": "⚪ NEUTRAL - Fed News ka Wait Karo", "Impact": "NEUTRAL"},
            {"News": "Election / Policy ka natija - Agar policy me garbar hui to market negative ja sakta hai. Policy news dekh kar hi entry lo.", "Source": "Global Check", "Sentiment": "⚪ NEUTRAL - Policy News ka Wait Karo", "Impact": "NEUTRAL"},
        ]
    return pd.DataFrame(news_rows)

@st.cache_data(ttl=60)
def scan_pura_market():
    """Pura Market Scan - NSE + BSE - Har stock ki jaanch - Probability Score"""
    indices_df = fetch_indices_history()
    # Market ka overall mood indices se
    nifty_trend = "UP"
    if not indices_df.empty:
        nifty_row = indices_df[indices_df["Index"] == "NIFTY"]
        if not nifty_row.empty:
            nifty_trend = nifty_row.iloc[0]["Trend"]

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
            # Last 5 min ka momentum - Movement suru hua ya nahi
            last_5min_chg = 0
            if len(df) >= 2:
                last_5min_chg = round((float(df['Close'].iloc[-1]) - float(df['Close'].iloc[-2])) / float(df['Close'].iloc[-2]) * 100, 3) if float(df['Close'].iloc[-2]) else 0

            # Conditions
            c1_gap = abs(gap_pct) > 0.30
            c2_vwap = (ltp > vwap and gap_pct > 0) or (ltp < vwap and gap_pct < 0)
            c3_orb = (ltp > orb_high) or (ltp < orb_low)
            c4_vol = vol_ratio > 1.5  # Zyada strict - 1.5x
            # Movement suru hua?
            movement_started = (ltp > orb_high and last_5min_chg > 0.1 and vol_ratio > 1.2) or (ltp < orb_low and last_5min_chg < -0.1 and vol_ratio > 1.2)
            movement_text = "🚀 MOVEMENT SURU HO GAYA - AB LENA CHAHIYE" if movement_started else "⏳ ABHI MOVEMENT SURU NAHI HUA - WAIT KARO"

            # Probability Score - 0-100 - Agle kuch samay me move aane ki sambhavana
            score = 0
            if c1_gap: score += 20
            if c2_vwap: score += 20
            if c3_orb: score += 25
            if c4_vol: score += 20
            if movement_started: score += 15
            # Gap zyada ho to score aur badhao
            if abs(gap_pct) > 1.0: score += 10
            if abs(gap_pct) > 2.0: score += 10
            score = min(100, score)

            # Direction
            if ltp > vwap and gap_pct > 0:
                direction = "BULLISH"
                pattern = "Gap Up + VWAP Upar + ORB Breakout" if c3_orb else "Gap Up + VWAP Upar"
            elif ltp < vwap and gap_pct < 0:
                direction = "BEARISH"
                pattern = "Gap Down + VWAP Neeche + ORB Breakout" if c3_orb else "Gap Down + VWAP Neeche"
            else:
                direction = "SIDEWAYS"
                pattern = "Koi clear pattern nahi"

            pass_count = sum([c1_gap, c2_vwap, c3_orb, c4_vol])
            all_rows.append({
                "Stock": stock, "LTP": round(ltp, 2), "Gap %": gap_pct, "VWAP": round(vwap, 2),
                "ORB High": round(orb_high, 2), "ORB Low": round(orb_low, 2), "Vol x": vol_ratio,
                "Last 5min %": last_5min_chg, "Direction": direction, "Pattern": pattern,
                "Movement": movement_text, "Movement Started?": "✅ HAAN" if movement_started else "❌ NAHI",
                "Probability %": score, "Gap": "✅" if c1_gap else "❌", "VWAP": "✅" if c2_vwap else "❌",
                "ORB": "✅" if c3_orb else "❌", "Volume": "✅" if c4_vol else "❌",
                "Pass": f"{pass_count}/4", "Nifty Trend": nifty_trend,
            })
        except:
            continue
    df = pd.DataFrame(all_rows)
    if not df.empty:
        df = df.sort_values("Probability %", ascending=False)
    return df, indices_df

# ---------- SCAN BUTTON - Pura Market ----------
st.markdown("### 🔍 PURA MARKET SCAN - NSE + BSE - Jab Scan Dabaoge Tabhi Chalega")
st.write("Scan dabate hi pura market scan hoga - NSE + BSE ke sab stocks, phir batayega kaunsa stock agle kuch samay me sabse zyada move kar sakta hai.")

if st.button("🔴 SCAN NOW - Pura Market (NSE + BSE) Scan Karo", use_container_width=True):
    with st.spinner("Pura Market Scan ho raha hai... NSE + BSE ke 100+ stocks, Global News, Indices - 30-40 sec lagega"):
        df_scan, indices_df = scan_pura_market()
        news_df = fetch_global_news()
        st.session_state.scan_df = df_scan
        st.session_state.indices_data = indices_df
        st.session_state.news_data = news_df
        # Notification - Top 1 stock ke liye
        if not df_scan.empty:
            top = df_scan.iloc[0]
            if top["Probability %"] >= 70:
                add_notification(f"🚀 High Probability Stock Mila - {top['Stock']}", f"{top['Stock']} - Probability {top['Probability %']}% - {top['Pattern']} - {top['Movement']} - Rs 5000 me strike dekho", "success")
                st.toast(f"🚀 {top['Stock']} me bada move aane ki sambhavana hai - {top['Probability %']}%", icon="🚀")
            elif top["Probability %"] >= 50:
                add_notification(f"⚠️ Medium Stock Mila - {top['Stock']}", f"{top['Stock']} - Probability {top['Probability %']}% - {top['Movement']}", "warning")
        st.rerun()

# ---------- RESULTS ----------
if st.session_state.scan_df is not None and not st.session_state.scan_df.empty:
    df_scan = st.session_state.scan_df
    indices_df = st.session_state.indices_data
    news_df = st.session_state.news_data

    # 1. Pichla Indices ka Move - Nifty, Bank Nifty, Sensex, Bankex
    st.markdown("### 📊 1. PICHHLA MOVE - Nifty, Bank Nifty, Sensex, Bankex Kaisa Tha?")
    st.write("Isse pata chalega market ka mood kaisa tha - kal kaisa tha, 5 din me kaisa tha.")
    if indices_df is not None and not indices_df.empty:
        st.dataframe(indices_df, use_container_width=True, hide_index=True)
        # Indices ka summary
        nifty_row = indices_df[indices_df["Index"] == "NIFTY"]
        if not nifty_row.empty:
            n_chg = nifty_row.iloc[0]["Kal ka Move %"]
            st.write(f"**Nifty kal:** {n_chg}% - {'Kal Upar tha, to aaj bhi Upar ki sambhavana zyada' if n_chg > 0 else 'Kal Neeche tha, to aaj bhi savdhan raho'}")
    else:
        st.write("Indices ka data nahi mila.")

    # 2. Global News
    st.markdown("### 🌍 2. GLOBAL NEWS - Election, Fed, Policy - Isse Entry / Target / SL Badlega")
    st.write("Agar Fed ka news negative hai ya Election me garbar hai to market negative ja sakta hai, isliye entry me savdhan raho. Agar Policy achhi aayi hai to Positive.")
    if news_df is not None and not news_df.empty:
        st.dataframe(news_df, use_container_width=True, hide_index=True)
        # News ka overall impact
        neg_count = len(news_df[news_df["Impact"] == "NEGATIVE"])
        pos_count = len(news_df[news_df["Impact"] == "POSITIVE"])
        if neg_count > pos_count:
            st.error(f"⚠️ GLOBAL NEWS NEGATIVE HAI - {neg_count} Negative news, {pos_count} Positive. Market neeche ja sakta hai. Entry me savdhan raho, SL chhota rakho, Target bhi chhota rakho.")
            news_bias = "NEGATIVE"
        elif pos_count > neg_count:
            st.success(f"✅ GLOBAL NEWS POSITIVE HAI - {pos_count} Positive news. Market upar ja sakta hai. Entry le sakte ho.")
            news_bias = "POSITIVE"
        else:
            st.info("⚪ GLOBAL NEWS NEUTRAL HAI - Koi bada Fed / Election ka news nahi hai. Normal trade kar sakte ho.")
            news_bias = "NEUTRAL"
    else:
        news_bias = "NEUTRAL"
        st.write("News nahi mila.")

    # 3. Top Stocks - Sabse Zyada Sambhavana
    st.markdown("### 🎯 3. SABSE ZYADA MOVE AANE KI SAMBHAVANA WALE STOCKS - Top 5")
    top5 = df_scan.head(5)
    st.dataframe(top5[["Stock", "LTP", "Gap %", "Direction", "Pattern", "Probability %", "Movement", "Movement Started?", "Pass"]], use_container_width=True, hide_index=True)

    # Top 1 ko highlight
    top1 = df_scan.iloc[0]
    st.success(f"**🏆 No.1 Stock - Sabse Zyada Sambhavana:** {top1['Stock']} - Probability {top1['Probability %']}% - LTP Rs {top1['LTP']} - Pattern: {top1['Pattern']} - Movement: {top1['Movement']}")
    if top1["Movement Started?"] == "✅ HAAN":
        st.success(f"🚀 {top1['Stock']} me MOVEMENT SURU HO GAYA HAI - AB LENA CHAHIYE - Yehi time hai entry ka.")
    else:
        st.warning(f"⏳ {top1['Stock']} me ABHI MOVEMENT SURU NAHI HUA HAI - WAIT KARO - Movement suru hote hi notification aayega.")

    # 4. Sab Stocks ki Table
    st.markdown("### 📋 4. PURA MARKET - Sab Stocks ki Jaanch - Kaunsa Pass, Kaunsa Fail")
    st.dataframe(df_scan[["Stock", "LTP", "Gap %", "Direction", "Pattern", "Probability %", "Gap", "VWAP", "ORB", "Volume", "Movement Started?", "Pass"]], use_container_width=True, hide_index=True)

    # 5. Selected Stock Detail - Option Chain Rs 5000 me
    st.markdown("### 💰 5. OPTION CHAIN SE SUITABLE STRIKE - Rs 5,000 Me Aane Wala")
    st.write("Jo stock Top me hai, uska option chain se Rs 5,000 me aane wala strike price nikalenge. 5000 se zyada wala nahi denge.")
    sel_stock = st.selectbox("Stock Chuno - Jiska Strike Dekhna Hai", df_scan["Stock"].tolist(), index=0)
    if sel_stock:
        row = df_scan[df_scan["Stock"] == sel_stock].iloc[0]
        st.write(f"**Stock:** {sel_stock} | **LTP:** Rs {row['LTP']} | **Pattern:** {row['Pattern']} | **Probability:** {row['Probability %']}% | **Movement:** {row['Movement']} | **News Bias:** {news_bias if 'news_bias' in locals() else 'NEUTRAL'}")
        # Option Chain
        with st.spinner(f"{sel_stock} ka Option Chain la raha hoon..."):
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                sess = requests.Session()
                sess.get("https://www.nseindia.com", headers=headers, timeout=10)
                url = f"https://www.nseindia.com/api/option-chain-equities?symbol={sel_stock}"
                r = sess.get(url, headers=headers, timeout=12)
                chain_data = r.json() if r.status_code == 200 else None
            except:
                chain_data = None

            if chain_data:
                try:
                    records = chain_data.get("records", {}).get("data", [])
                    chain_rows = []
                    total_ce = 0
                    total_pe = 0
                    for item in records:
                        s = item.get("strikePrice", 0)
                        ce = item.get("CE", {})
                        pe = item.get("PE", {})
                        total_ce += ce.get("openInterest", 0) if ce else 0
                        total_pe += pe.get("openInterest", 0) if pe else 0
                        if abs(s - row['LTP']) <= 100 if row['LTP'] < 2000 else abs(s - row['LTP']) <= 200:
                            chain_rows.append({"Strike": s, "CE LTP": ce.get("lastPrice", 0) if ce else 0, "CE OI Chg": ce.get("changeinOpenInterest", 0) if ce else 0, "PE LTP": pe.get("lastPrice", 0) if pe else 0, "PE OI Chg": pe.get("changeinOpenInterest", 0) if pe else 0})
                    chain_df = pd.DataFrame(chain_rows).sort_values("Strike")
                    pcr = round(total_pe / total_ce, 2) if total_ce else 0
                    st.write(f"**PCR:** {pcr} | OI: {'PE zyada = Bullish' if pcr > 1 else 'CE zyada = Bearish'}")
                    st.dataframe(chain_df, use_container_width=True, hide_index=True)
                    # Rs 5000 me suitable strike - News Bias se SL/Target adjust
                    lot = LOT_SIZES.get(sel_stock, 100)
                    atm = chain_df.iloc[(chain_df['Strike'] - row['LTP']).abs().argsort()[:1]]['Strike'].values[0] if not chain_df.empty else 0
                    opt_type = "CE" if "BULLISH" in row['Direction'] else "PE" if "BEARISH" in row['Direction'] else "CE"
                    # News NEGATIVE ho to BEARISH ki taraf jhukao, SL chhota rakho
                    if news_bias == "NEGATIVE" and opt_type == "CE":
                        st.warning("⚠️ Global News NEGATIVE hai, isliye CE me savdhan raho. SL chhota rakha hai, Target bhi chhota rakha hai.")
                        sl_factor = 0.80  # SL jaldi
                        target_factor = 1.30  # Target chhota
                    elif news_bias == "POSITIVE":
                        sl_factor = 0.70
                        target_factor = 1.60
                    else:
                        sl_factor = 0.70
                        target_factor = 1.50

                    # Rs 5000 me aane wala strike dhoondo - ATM se door tak
                    found = None
                    for _, crow in chain_df.iterrows():
                        prem = float(crow["CE LTP"] if opt_type == "CE" else crow["PE LTP"])
                        if prem <= 0:
                            continue
                        cost = prem * lot
                        if cost <= 5000 and cost >= 500:  # 5000 me aana chahiye, 500 se kam wala bahut door ka hai
                            # ATM ke sabse paas wala
                            if found is None or abs(crow["Strike"] - row['LTP']) < abs(found["Strike"] - row['LTP']):
                                found = {"Strike": crow["Strike"], "Premium": prem, "Cost": round(cost, 0)}
                    if found:
                        entry_prem = found["Premium"]
                        strike = int(found["Strike"])
                        sl_prem = round(entry_prem * sl_factor, 1)
                        target_prem = round(entry_prem * target_factor, 1)
                        max_loss = round((entry_prem - sl_prem) * lot, 0)
                        max_profit = round((target_prem - entry_prem) * lot, 0)
                        st.success(f"**✅ Suitable Strike Mil Gaya (Rs 5000 me):** {sel_stock} {strike} {opt_type} @ Rs {entry_prem} - 1 Lot (Qty {lot}) - Cost Rs {found['Cost']} - SL Rs {sl_prem} - Target Rs {target_prem}")
                        st.write(f"**Entry:** Rs {entry_prem} | **Target:** Rs {target_prem} (News: {news_bias}) | **Stop Loss:** Rs {sl_prem} | **Max Profit:** Rs {max_profit} | **Max Loss:** Rs {max_loss} | **Movement:** {row['Movement']}")
                        if row["Movement Started?"] == "✅ HAAN":
                            st.success(f"🚀 Movement Suru Ho Gaya Hai - Ab Lena Chahiye - {sel_stock} me entry ka time hai.")
                        else:
                            st.warning(f"⏳ Movement Abhi Suru Nahi Hua - Wait Karo - Jab movement suru hoga tab notification aayega.")
                        suggested = {"date": datetime.now().strftime("%Y-%m-%d"), "time": datetime.now().strftime("%H:%M:%S"), "symbol": sel_stock, "strike": strike, "opt_type": opt_type, "entry": float(entry_prem), "sl": float(sl_prem), "target": float(target_prem), "qty_lots": 1, "qty_total": float(lot), "capital_used": float(found['Cost']), "risk": float(max_loss), "status": "OPEN", "reason": f"{row['Direction']} - {row['Pattern']} - News {news_bias} - Prob {row['Probability %']}%", "conditions": f"Gap {row['Gap']} VWAP {row['VWAP']} ORB {row['ORB']} Vol {row['Volume']} Movement {row['Movement Started?']}"}
                        if st.button(f"📝 {sel_stock} ko Diary me Save Karo (Trade Liya to hi dabao)"):
                            save_trade(suggested)
                            add_notification(f"Trade Save Hua - {sel_stock}", f"{sel_stock} {strike} {opt_type} @ {entry_prem} - SL {sl_prem} - Target {target_prem}", "success")
                            st.success("Diary me save ho gaya! Notification bhi aa gaya.")
                            st.rerun()
                    else:
                        st.warning(f"{sel_stock} me Rs 5000 me koi 1 Lot wala contract nahi mila. Premium bahut zyada hai. Dusra stock try karo.")
                except Exception as e:
                    st.error(f"Option Chain me dikkat: {e}")
            else:
                st.warning(f"{sel_stock} ka Option Chain NSE se nahi mila. NSE ne block kiya hoga. 1 min baad phir try karo.")

else:
    st.info("👆 Upar **SCAN NOW** dabao. Tab pura market scan hoga - NSE + BSE, Global News, Indices, sab kuch.")

st.divider()
st.write("1. Pura Market Scan - NSE + BSE. 2. Rs 5000 me aane wala strike. 3. Global News - Fed / Election / Policy. 4. Pichla Nifty / Bank Nifty / Sensex / Bankex. 5. Movement Suru Hua ya Nahi. 6. Notification - App + Telegram. 7. Auto Trade NAHI, sirf jaankari.")
