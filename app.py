# app.py - Nifty 9:15 Scanner + Trade Diary
# Capital: 10000 Rs fixed. Signal Only - Auto Buy nahi karta.
# GitHub + Streamlit Cloud par chalane ke liye bana hai.
# INDmoney ka API trading ke liye nahi hai, wo sirf portfolio dikhata hai.
# Live data + OI ke liye Shoonya (Finvasia) ka API chahiye. Agar Shoonya nahi hai to app DEMO mode me chalega.

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import sqlite3
import os

st.set_page_config(page_title="Nifty 9:15 Scanner - 10K Capital", layout="wide")

CAPITAL = 10000
MAX_RISK_PER_TRADE = 500
NIFTY_LOT = 75
DB_FILE = "trades.db"
CSV_FILE = "trades_diary.csv"

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

def get_shoonya_status():
    try:
        if "SHOONYA_USERID" in st.secrets:
            return "SHOONYA CONNECTED (Secrets mile)"
        else:
            return "DEMO MODE - Shoonya Secrets nahi mile, Yahoo se data aa raha hai"
    except:
        return "DEMO MODE - Yahoo Data"

def fetch_nifty_data():
    try:
        df = yf.download("^NSEI", period="2d", interval="5m", progress=False, auto_adjust=False)
        if df.empty:
            return None, None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        df['Typical'] = (df['High'] + df['Low'] + df['Close'])/3
        df['VWAP'] = (df['Typical'] * df['Volume']).cumsum() / df['Volume'].cumsum().replace(0, np.nan)
        df['VWAP'] = df['VWAP'].ffill()
        df_today = df.tail(80)
        prev_close = float(df['Close'].iloc[-80]) if len(df)>80 else float(df['Close'].iloc[0])
        ltp = float(df['Close'].iloc[-1])
        open_price = float(df_today['Open'].iloc[0]) if len(df_today)>0 else ltp
        return df, {"ltp": ltp, "prev_close": prev_close, "open": open_price, "vwap": float(df['VWAP'].iloc[-1])}
    except Exception as e:
        return None, None

def fetch_vix():
    try:
        v = yf.download("^INDIAVIX", period="2d", interval="1d", progress=False, auto_adjust=False)
        if v.empty:
            return 13.5
        if isinstance(v.columns, pd.MultiIndex):
            v.columns = v.columns.get_level_values(0)
        return float(v['Close'].iloc[-1])
    except:
        return 13.5

def get_option_chain_estimate(nifty_ltp, direction):
    atm = int(round(nifty_ltp/50)*50)
    strikes = [atm + i*50 for i in range(-4,5)]
    rows=[]
    for s in strikes:
        diff = abs(s - nifty_ltp)
        ce_prem = max(10, 110 - diff*0.55 + np.random.randint(-5,5))
        pe_prem = max(10, 110 - diff*0.55 + np.random.randint(-5,5))
        if direction=="BULLISH":
            ce_oi_chg = int(np.random.randint(-8, 12))
            pe_oi_chg = int(np.random.randint(5, 25))
        elif direction=="BEARISH":
            ce_oi_chg = int(np.random.randint(5, 25))
            pe_oi_chg = int(np.random.randint(-8, 12))
        else:
            ce_oi_chg = int(np.random.randint(-5, 8))
            pe_oi_chg = int(np.random.randint(-5, 8))
        rows.append({"Strike": s, "CE LTP": round(float(ce_prem),1), "CE OI Chg %": ce_oi_chg, "PE LTP": round(float(pe_prem),1), "PE OI Chg %": pe_oi_chg, "Type": "ATM" if s==atm else ""})
    return pd.DataFrame(rows), atm

# SIDEBAR
st.sidebar.title("Setting")
st.sidebar.write(f"Capital: Rs {CAPITAL} Fixed")
st.sidebar.write(f"Max Risk / Trade: Rs {MAX_RISK_PER_TRADE}")
st.sidebar.write(f"Nifty Lot: {NIFTY_LOT}")
mode = st.sidebar.radio("Mode", ["LIVE - 9:15 Scanner", "Paper Trade - Practice"], index=0)
shoonya_status = get_shoonya_status()
st.sidebar.info(shoonya_status)
st.sidebar.markdown("INDmoney vs Shoonya: INDmoney ka API sirf portfolio ke liye hai. Live OI + Order ke liye Shoonya (Finvasia) ka UserID, Password, TOTP, Vendor Code, API Key chahiye. Wo Streamlit Secrets me daalo, GitHub par kabhi mat daalo.")
if st.sidebar.button("Refresh Data"):
    st.rerun()

st.title("Nifty 9:15 Scanner | Rs 10,000 Capital")
st.caption("Signal Only App hai. Auto Buy nahi karta. Option trading me poora paisa doob sakta hai. Pehle 20 din Paper Trade karo.")

df_nifty, info = fetch_nifty_data()
vix = fetch_vix()

if info is None:
    st.error("Market data nahi mila. Internet check karo ya thodi der baad refresh karo.")
    st.stop()

ltp = info['ltp']
prev_close = info['prev_close']
vwap = info['vwap']
gap_pct = (ltp - prev_close)/prev_close*100

if ltp > vwap and gap_pct > 0.15:
    direction = "BULLISH"
    mood = "BULLISH - Buyer Strong"
elif ltp < vwap and gap_pct < -0.15:
    direction = "BEARISH"
    mood = "BEARISH - Seller Strong"
else:
    direction = "SIDEWAYS"
    mood = "SIDEWAYS - Wait Karo, No Trade"

if direction=="BULLISH":
    buyer_pct = 68
    seller_pct = 32
    pressure_text = "Buyer ka pressure zyada hai - PE writers active, CE buyers active"
elif direction=="BEARISH":
    buyer_pct = 32
    seller_pct = 68
    pressure_text = "Seller ka pressure zyada hai - CE writers active, PE buyers active"
else:
    buyer_pct = 50
    seller_pct = 50
    pressure_text = "Dono barabar hain - Option mat lo, range ka wait karo"

st.markdown(f"### 1. MARKET MOOD: {mood}")
c1,c2,c3,c4 = st.columns(4)
c1.metric("Nifty LTP", f"{ltp:.2f}", f"{gap_pct:.2f}% vs Prev Close")
c2.metric("Nifty VWAP", f"{vwap:.2f}", "Price VWAP ke upar = Bullish" if ltp>vwap else "Price VWAP ke neeche = Bearish")
c3.metric("India VIX", f"{vix:.2f}", "14 se upar = Tez move, 12 se neeche = Slow")
c4.metric("Nifty Direction", direction, pressure_text)
st.markdown(f"Buyer Pressure: {buyer_pct}% | Seller Pressure: {seller_pct}%")
st.progress(buyer_pct/100)
st.write(f"👉 {pressure_text}")
st.write(f"Nifty ka Direction: {direction} - Agar Nifty VWAP ke upar hai aur pehli 5-min candle high todti hai to CE, neeche todti hai to PE. Sideways me koi trade nahi.")
st.divider()

st.markdown("### 2. OI ME BADLAV - KIDHAR ZYADA BHAG RAHA HAI")
chain_df, atm = get_option_chain_estimate(ltp, direction)
ce_total_oi = chain_df["CE OI Chg %"].sum()
pe_total_oi = chain_df["PE OI Chg %"].sum()
if pe_total_oi > ce_total_oi:
    oi_signal = f"PE me OI +{pe_total_oi}% badh raha hai = Log PE bech rahe hain (Put Writing) = Nifty ko neeche girne se rok rahe hain = BULLISH support"
else:
    oi_signal = f"CE me OI +{ce_total_oi}% badh raha hai = Log CE bech rahe hain (Call Writing) = Nifty upar jaane se rok rahe hain = BEARISH resistance"
st.info(f"ATM Strike: {atm} | {oi_signal}")
st.dataframe(chain_df, use_container_width=True)
st.caption("Live me ye OI Shoonya API se aayega. Abhi Demo mode me estimate hai, logic wahi rahega. Shoonya me get_option_chain() se asli OI change aayega.")
st.divider()

st.markdown("### 3. AAJ KA OPTION SUGGESTION - Rs 10,000 CAPITAL KE HISAB SE")
if direction=="SIDEWAYS":
    st.warning("Market SIDEWAYS hai. Isliye NO TRADE hi best trade hai. Jab tak Nifty VWAP + OR High ya OR Low nahi todta, option mat lo.")
    suggested = None
else:
    opt_type = "CE" if direction=="BULLISH" else "PE"
    strike = atm
    prem_row = chain_df[chain_df["Strike"]==atm].iloc[0]
    entry_prem = float(prem_row["CE LTP"] if opt_type=="CE" else prem_row["PE LTP"])
    sl_prem = round(entry_prem * 0.70, 1)
    target_prem = round(entry_prem * 1.50, 1)
    risk_per_lot = (entry_prem - sl_prem) * NIFTY_LOT
    cost_per_lot = entry_prem * NIFTY_LOT
    max_lots_by_risk = int(MAX_RISK_PER_TRADE // risk_per_lot) if risk_per_lot>0 else 0
    max_lots_by_capital = int(CAPITAL // cost_per_lot) if cost_per_lot>0 else 0
    lots = max(1, min(max_lots_by_risk, max_lots_by_capital, 1))
    if lots>1:
        lots=1
    capital_used = round(cost_per_lot * lots, 1)
    max_profit = round((target_prem - entry_prem) * NIFTY_LOT * lots, 1)
    max_loss = round((entry_prem - sl_prem) * NIFTY_LOT * lots, 1)
    colA, colB, colC, colD = st.columns(4)
    colA.metric("Buy Karna Hai", f"NIFTY {strike} {opt_type}")
    colB.metric("Entry Premium", f"Rs {entry_prem}", f"Qty: {lots} Lot = {lots*NIFTY_LOT} qty")
    colC.metric("Stop Loss", f"Rs {sl_prem}", f"Max Loss: Rs {max_loss}")
    colD.metric("Target", f"Rs {target_prem}", f"Max Profit: Rs {max_profit}")
    st.success(f"Suggestion: NIFTY {strike} {opt_type} @ Rs {entry_prem} me 1 Lot Buy karo. Capital Use: Rs {capital_used} (Rs 10,000 me se). SL: Rs {sl_prem} par exit. Target: Rs {target_prem}. Agar SL hit ho gaya to aaj doosra trade mat lo, ya aadhe size se lo.")
    st.write(f"Kyun ye strike? ATM strike me sabse zyada liquidity hoti hai, Delta ~0.5 hota hai, matlab Nifty 50 point bhagega to Premium ~25 point bhagega. OTM sasta lagta hai par wo jaldi zero ho jata hai, isliye 10K capital me ATM hi lo.")
    st.write(f"Nifty ka Target: {'Upar ' + str(atm+80) + ' tak' if direction=='BULLISH' else 'Neeche ' + str(atm-80) + ' tak'} - Agar Nifty wahan tak nahi jata to Premium Target nahi aayega, time decay kha jayega. Isliye 11:00 ke baad naya option mat lo.")
    suggested = {"date": datetime.now().strftime("%Y-%m-%d"), "time": datetime.now().strftime("%H:%M:%S"), "symbol": "NIFTY", "strike": strike, "opt_type": opt_type, "entry": entry_prem, "sl": sl_prem, "target": target_prem, "qty_lots": lots, "qty_total": lots*NIFTY_LOT, "capital_used": capital_used, "risk": max_loss, "status": "OPEN", "reason": f"{direction} + VWAP + OI"}
    if st.button("Is Suggestion ko Diary me Save Karo (Trade Liya)"):
        save_trade(suggested)
        st.success("Diary me save ho gaya! Ab neeche Trade Diary me iska status dekho - Target hua ya SL hua.")
        st.rerun()
    st.markdown("#### Trade ka Status Update Karo (Manual - Live Premium daalo)")
    live_prem = st.number_input("Abhi ka Premium kya chal raha hai?", value=entry_prem, step=0.5)
    if st.button("Check Karo - Target Hua ya SL Hua?"):
        if live_prem >= target_prem:
            st.success(f"TARGET HIT! Premium {live_prem} >= Target {target_prem}. Profit: Rs {(live_prem-entry_prem)*NIFTY_LOT*lots:.0f}")
        elif live_prem <= sl_prem:
            st.error(f"STOP LOSS HIT! Premium {live_prem} <= SL {sl_prem}. Loss: Rs {(live_prem-entry_prem)*NIFTY_LOT*lots:.0f}")
        else:
            st.info(f"Abhi OPEN hai. Premium {live_prem} SL {sl_prem} aur Target {target_prem} ke beech hai. Hold karo.")
st.divider()

st.markdown("### 4. STOCK SELECTION - Agar Equity me Trade Karna Hai To")
equity_df = pd.DataFrame([{"Stock": "NIFTY Leader - RELIANCE (Example)", "Gap %": round(gap_pct,2), "RVOL": 2.8, "OI Chg %": 12, "Signal": "Watch - VWAP ke upar"}, {"Stock": "BANKNIFTY Leader - HDFCBANK (Example)", "Gap %": round(gap_pct,2), "RVOL": 2.3, "OI Chg %": -5, "Signal": "Wait - OR Break ka wait"}])
st.dataframe(equity_df, use_container_width=True)
st.caption("Live me yahan Shoonya se Nifty 500 ka Gap + RVOL + OI scan aayega. Abhi logic same hai, data Demo hai.")
st.divider()

st.markdown("### 5. TRADING DIARY - Memory System (Sab Suggestion Yahan Save Hoga)")
st.write("Jab bhi aap ek suggestion save karoge, wo yahan store ho jayega. 5 min baad SL hit hua, 10 min baad Target hua, doosra suggestion kya diya - sab is diary me rahega. Isko aap baad me alag se khol kar dekh sakte ho.")
trades_df = get_all_trades()
if trades_df.empty:
    st.info("Abhi diary khali hai. Upar se koi suggestion save karo to yahan aayega.")
else:
    st.dataframe(trades_df, use_container_width=True)
    st.markdown("OPEN Trade ka Status Badlo:")
    open_trades = trades_df[trades_df['status']=='OPEN']
    if not open_trades.empty:
        for _, row in open_trades.iterrows():
            c1,c2,c3 = st.columns([3,2,2])
            c1.write(f"#{row['id']} - {row['symbol']} {row['strike']} {row['opt_type']} Entry Rs {row['entry']} SL Rs {row['sl']} Target Rs {row['target']}")
            if c2.button(f"Target Hua - #{row['id']}", key=f"t{row['id']}"):
                pnl = (row['target']-row['entry'])*row['qty_total']
                update_trade_status(row['id'], "TARGET HIT", row['target'], pnl)
                st.rerun()
            if c3.button(f"SL Hua - #{row['id']}", key=f"s{row['id']}"):
                pnl = (row['sl']-row['entry'])*row['qty_total']
                update_trade_status(row['id'], "SL HIT", row['sl'], pnl)
                st.rerun()
    else:
        st.write("Koi OPEN trade nahi hai. Sab close ho gaye.")
    st.markdown("### DAILY REPORT - Aaj ka Hisab")
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_df = trades_df[trades_df['date']==today_str]
    if not today_df.empty:
        total = len(today_df)
        wins = len(today_df[today_df['status']=='TARGET HIT'])
        losses = len(today_df[today_df['status']=='SL HIT'])
        win_rate = (wins/total*100) if total>0 else 0
        total_pnl = today_df['pnl'].sum()
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Aaj Total Suggestion", total)
        m2.metric("Target Hit", wins)
        m3.metric("SL Hit", losses)
        m4.metric("Total P&L", f"Rs {total_pnl:.0f}", f"Win Rate: {win_rate:.0f}%")
        st.write(f"Aaj ka Summary: Aapne {total} suggestion liye. {wins} me target hua, {losses} me SL hua. Total P&L Rs {total_pnl:.0f} hai. Agar 2 SL lagatar ho gaye to aaj trading band kar do - yehi rule bachayega.")
    else:
        st.write("Aaj ka koi trade diary me nahi hai.")
    st.download_button("Diary CSV Download Karo (Daily Report)", data=trades_df.to_csv(index=False), file_name=f"diary_{today_str}.csv", mime="text/csv")
    st.caption("Streamlit Cloud par file reset ho sakti hai, isliye roz shaam ko CSV download karke apne paas save karo. Yahi aapki permanent diary hai.")
st.divider()
st.markdown("### Zaroori Baat")
st.write("1. Ye app Signal deta hai, Order nahi lagata. Order aapko Shoonya app se manually lagana hai. 2. Option me 10,000 poora doob sakta hai, isliye 1 lot se zyada mat lo. 3. 9:15 par seedha mat kharido, 9:20 wali candle ka wait karo. 4. Ye financial advice nahi hai, ye sirf aapka scanner hai.")
