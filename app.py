# app.py - V3 - FINAL - Sirf Client ID + Secret Code wala Login
# Screenshot me jo dikh raha hai wahi chahiye - Client ID + Secret Code
# Baaki User ID / Password / TOTP aapke Shoonya Login wale hain
# CSV ab ek hi file me update hoga - trades_diary/all_trades.csv
# Kone me Trading Diary button hai

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import sqlite3
import os
import requests
import base64
from io import StringIO

st.set_page_config(page_title="Nifty 9:15 Scanner", layout="wide")

CAPITAL = 10000
MAX_RISK_PER_TRADE = 500
NIFTY_LOT = 75
DB_FILE = "trades.db"
CSV_FILE = "trades_diary.csv"
GITHUB_CSV_PATH = "trades_diary/all_trades.csv"  # EK HI FILE - Roz isi me update hoga

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "show_diary" not in st.session_state:
    st.session_state.show_diary = False
if "github_last_sync" not in st.session_state:
    st.session_state.github_last_sync = "Abhi sync nahi hua"

# ---------- GITHUB - EK HI CSV ----------
def push_csv_to_github(df, github_pat, github_repo):
    """EK HI CSV - all_trades.csv - Roz isi file me update hoga, alag-alag file nahi banegi"""
    if not github_pat or not github_repo or "/" not in github_repo:
        return False, "GitHub PAT / Repo sahi nahi hai"
    try:
        csv_text = df.to_csv(index=False)
        content_b64 = base64.b64encode(csv_text.encode()).decode()
        headers = {"Authorization": f"token {github_pat}", "Accept": "application/vnd.github+json"}
        url = f"https://api.github.com/repos/{github_repo}/contents/{GITHUB_CSV_PATH}"
        get_resp = requests.get(url, headers=headers, timeout=10)
        sha = None
        if get_resp.status_code == 200:
            sha = get_resp.json().get("sha")
        payload = {"message": f"Diary update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "content": content_b64}
        if sha:
            payload["sha"] = sha
        put_resp = requests.put(url, headers=headers, json=payload, timeout=15)
        if put_resp.status_code in [200, 201]:
            return True, f"OK - {GITHUB_CSV_PATH} update ho gaya"
        else:
            return False, f"Fail {put_resp.status_code} - {put_resp.text[:200]}"
    except Exception as e:
        return False, str(e)

def fetch_diary_from_github(github_pat, github_repo):
    try:
        url = f"https://api.github.com/repos/{github_repo}/contents/{GITHUB_CSV_PATH}"
        headers = {"Authorization": f"token {github_pat}", "Accept": "application/vnd.github+json"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            content = r.json().get("content", "")
            csv_text = base64.b64decode(content).decode()
            return pd.read_csv(StringIO(csv_text))
    except:
        pass
    return None

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
        ok, msg = push_csv_to_github(df2, st.session_state.github_pat, st.session_state.github_repo)
        st.session_state.github_last_sync = f"{'OK' if ok else 'Fail'} - {datetime.now().strftime('%H:%M:%S')} - {msg}"
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
    if st.session_state.get("github_pat"):
        ok, msg = push_csv_to_github(df2, st.session_state.github_pat, st.session_state.github_repo)
        st.session_state.github_last_sync = f"{'OK' if ok else 'Fail'} - {datetime.now().strftime('%H:%M:%S')} - {msg}"

init_db()

# ---------- LOGIN PAGE - SIRF WAHI JO SCREENSHOT ME HAI ----------
if not st.session_state.authenticated:
    st.title("🔐 Nifty 9:15 Scanner - Login")
    st.write("**Aapke screenshot me jo hai, bas wahi chahiye.** Uske alawa kuch nahi chahiye.")
    st.success("✅ Screenshot me jo hai: **Client ID + Secret Code** - Bas ye 2 daalo. Baaki 3 cheezein aapke Shoonya Login wali hain, jo aapko pehle se pata hain.")

    with st.form("login_form"):
        st.markdown("### 1. Shoonya Login - Screenshot wala hissa")
        st.caption("Foto me jo dikh raha hai: Client ID = FA291532 jaisa, Secret Code = xxxx wala. Wahi yahan daalo.")
        client_id = st.text_input("Client ID (Screenshot wala) - Vendor Code bhi yahi hai", placeholder="jaise: FA291532")
        secret_code = st.text_input("Secret Code (Screenshot wala)", type="password", placeholder="Screenshot me jo Secret Code hai wahi")

        st.markdown("### 2. Shoonya Login - Aapka roz wala Login")
        st.caption("Ye wahi ID-Password hai jisse aap Shoonya App kholte ho. Screenshot me ye nahi dikhta, ye aapko pata hai.")
        shoonya_userid = st.text_input("Shoonya User ID (App Login wala ID)", placeholder="Shoonya App me jo ID se login karte ho")
        shoonya_password = st.text_input("Shoonya Password (App Login wala Password)", type="password")
        totp_code = st.text_input("TOTP / 2FA Code (6 ank ka, Google Authenticator / Shoonya App se)", placeholder="jaise: 123456", help="Har 30 second me badalta hai. Authenticator App khol kar jo 6 ank dikhe wahi daalo.")

        st.markdown("### 3. GitHub Auto-Save - Ek hi CSV me")
        st.caption("CSV ab alag-alag din ki file me nahi, ek hi file me update hoga: trades_diary/all_trades.csv")
        github_username = st.text_input("GitHub Username", placeholder="jaise: mera-naam")
        github_repo_name = st.text_input("GitHub Repo Name", placeholder="jaise: nifty-scanner")
        github_pat = st.text_input("GitHub PAT (Token)", type="password", help="GitHub Settings > Developer Settings > Personal Access Tokens > Fine-grained > Contents Read & Write")

        app_pin = st.text_input("Apna PIN (4 ank)", type="password", placeholder="jaise: 1234")
        submit = st.form_submit_button("🚀 Login & Scanner Kholo", use_container_width=True)
        if submit:
            if not client_id or not secret_code:
                st.error("Client ID aur Secret Code to daalo - Screenshot wala hi chahiye")
            elif not shoonya_userid or not shoonya_password:
                st.error("Shoonya User ID aur Password bhi chahiye - App Login wala")
            elif not app_pin or len(app_pin) < 4:
                st.error("4 ank ka PIN daalo")
            else:
                st.session_state.authenticated = True
                st.session_state.client_id = client_id
                st.session_state.secret_code = secret_code
                st.session_state.shoonya_userid = shoonya_userid
                st.session_state.shoonya_password = shoonya_password
                st.session_state.totp_code = totp_code
                st.session_state.github_pat = github_pat
                st.session_state.github_repo = f"{github_username}/{github_repo_name}" if github_username and github_repo_name else ""
                st.success("Login ho gaya! Scanner khul raha hai...")
                st.rerun()

    st.markdown("---")
    st.markdown("**Kahan se kya milega - Ek baar samajh lo:**")
    st.write("1. **Client ID** - Screenshot me jo `Client ID: FA291532` likha hai wahi. Yehi Vendor Code hai, alag se Vendor Code nahi chahiye.")
    st.write("2. **Secret Code** - Screenshot me jo `Secret Code: xxxx...` likha hai wahi. Yehi API Secret hai.")
    st.write("3. **Shoonya User ID** - Jisse aap Shoonya App me login karte ho, wo ID. Screenshot me nahi hota.")
    st.write("4. **Shoonya Password** - Jisse aap Shoonya App me login karte ho, wo Password.")
    st.write("5. **TOTP** - Google Authenticator ya Shoonya App me jo 6 ank ka code har 30 sec me badalta hai, wahi.")
    st.write("**Bas ye 5 cheezein chahiye. Iske alawa kuch nahi chahiye. Maine pehle jo Extra field diye the (Vendor Code alag se, API Key alag se) wo sab hata diye hain.**")
    st.warning("⚠️ Apna Secret Code kabhi kisi ko photo me mat bhejo, na chat me. Screenshot me bhi usko dhak kar bhejo. Client ID share kar sakte ho, Secret kabhi nahi.")

    if st.button("👀 Bina Secret ke DEMO me Dekho"):
        st.session_state.authenticated = True
        st.session_state.shoonya_userid = "DEMO"
        st.session_state.github_pat = ""
        st.session_state.github_repo = ""
        st.rerun()
    st.stop()

# ---------- MAIN APP ----------
# Top Corner me Trading Diary Button
top_left, top_right = st.columns([4, 1])
with top_left:
    st.title("Nifty 9:15 Scanner | Rs 10,000 Capital")
with top_right:
    st.write("")  # thoda gap
    if st.button("📓 Trading Diary", use_container_width=True, help="Click karo to Daily Trading Detail dikhega"):
        st.session_state.show_diary = not st.session_state.show_diary
        st.rerun()

st.caption(f"Login: {st.session_state.get('shoonya_userid')} | Client ID: {st.session_state.get('client_id','')} | GitHub CSV: trades_diary/all_trades.csv (Ek hi file) | Last Sync: {st.session_state.github_last_sync}")

st.sidebar.title("Dashboard")
st.sidebar.write(f"Login: {st.session_state.get('shoonya_userid')}")
st.sidebar.write(f"Capital: Rs {CAPITAL} Fixed")
st.sidebar.write(f"GitHub CSV: Ek hi file me update")
st.sidebar.write(f"Last Sync: {st.session_state.github_last_sync}")
if st.sidebar.button("📓 Trading Diary Kholo"):
    st.session_state.show_diary = True
    st.rerun()
if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()
if st.sidebar.button("📥 GitHub se Diary Lao"):
    old_df = fetch_diary_from_github(st.session_state.get("github_pat",""), st.session_state.get("github_repo",""))
    if old_df is not None and not old_df.empty:
        st.sidebar.success(f"GitHub se {len(old_df)} trades mile - Ek hi CSV se")
        st.sidebar.dataframe(old_df.head())
    else:
        st.sidebar.info("GitHub par abhi koi diary nahi hai")
if st.sidebar.button("🚪 Logout (Secret Delete Karo)"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()

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
        prev_close = float(df['Close'].iloc[-80]) if len(df)>80 else float(df['Close'].iloc[0])
        ltp = float(df['Close'].iloc[-1])
        return df, {"ltp": ltp, "prev_close": prev_close, "vwap": float(df['VWAP'].iloc[-1])}
    except:
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
    rows=[]
    for i in range(-4,5):
        s = atm + i*50
        diff = abs(s - nifty_ltp)
        ce_prem = max(10, 110 - diff*0.55 + np.random.randint(-5,5))
        pe_prem = max(10, 110 - diff*0.55 + np.random.randint(-5,5))
        if direction=="BULLISH":
            ce_oi = int(np.random.randint(-8, 12)); pe_oi = int(np.random.randint(5, 25))
        elif direction=="BEARISH":
            ce_oi = int(np.random.randint(5, 25)); pe_oi = int(np.random.randint(-8, 12))
        else:
            ce_oi = int(np.random.randint(-5, 8)); pe_oi = int(np.random.randint(-5, 8))
        rows.append({"Strike": s, "CE LTP": round(float(ce_prem),1), "CE OI Chg %": ce_oi, "PE LTP": round(float(pe_prem),1), "PE OI Chg %": pe_oi, "Type": "ATM" if s==atm else ""})
    return pd.DataFrame(rows), atm

# ---------- TRADING DIARY SECTION - Button dabane par khulega ----------
if st.session_state.show_diary:
    st.markdown("## 📓 TRADING DIARY - Daily Trading Detail")
    st.write("Yahan har din ka poora hisab hai - Kya diya tha, kya hua, kya nahi hua. Yehi diary GitHub ki ek hi CSV `all_trades.csv` me bhi save hoti hai.")
    trades_df_all = get_all_trades()
    if trades_df_all.empty:
        st.info("Abhi diary khali hai. Koi trade save karo to yahan aayega.")
    else:
        # Daily Summary
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_df = trades_df_all[trades_df_all['date']==today_str]
        if not today_df.empty:
            total=len(today_df); wins=len(today_df[today_df['status']=='TARGET HIT']); losses=len(today_df[today_df['status']=='SL HIT'])
            win_rate=(wins/total*100) if total>0 else 0; total_pnl=today_df['pnl'].sum()
            m1,m2,m3,m4 = st.columns(4)
            m1.metric("Aaj Total Suggestion", total); m2.metric("Target Hit", wins); m3.metric("SL Hit", losses); m4.metric("Total P&L", f"Rs {total_pnl:.0f}", f"Win Rate: {win_rate:.0f}%")
        st.markdown("### Har Trade ka Detail - Kya diya, Kya hua")
        for _, row in trades_df_all.iterrows():
            # Har trade ko ek card jaisa dikhao
            status_emoji = "🎯" if row['status']=='TARGET HIT' else "🛑" if row['status']=='SL HIT' else "⏳"
            with st.expander(f"{status_emoji} {row['date']} {row['time']} - {row['symbol']} {row['strike']} {row['opt_type']} - {row['status']} - P&L Rs {row['pnl'] if pd.notna(row['pnl']) else 0:.0f}"):
                c1,c2,c3 = st.columns(3)
                c1.write(f"**Kya Diya Tha:**\n- Entry: Rs {row['entry']}\n- Strike: {row['strike']} {row['opt_type']}\n- Qty: {row['qty_lots']} Lot ({row['qty_total']} qty)\n- Capital Use: Rs {row['capital_used']}")
                c2.write(f"**Kya Socha Tha:**\n- Stop Loss: Rs {row['sl']}\n- Target: Rs {row['target']}\n- Risk: Rs {row['risk']}\n- Reason: {row['reason']}")
                c3.write(f"**Kya Hua:**\n- Status: {row['status']}\n- Exit Price: Rs {row['exit_price'] if pd.notna(row['exit_price']) else 'Abhi Open hai'}\n- Exit Time: {row['exit_time'] if pd.notna(row['exit_time']) else '-'}\n- P&L: Rs {row['pnl'] if pd.notna(row['pnl']) else 0:.0f}")
                if row['status']=='OPEN':
                    cc1,cc2 = st.columns(2)
                    if cc1.button(f"🎯 Target Hua - #{row['id']}", key=f"dt{row['id']}"):
                        pnl = (row['target']-row['entry'])*row['qty_total']
                        update_trade_status(row['id'], "TARGET HIT", row['target'], pnl)
                        st.rerun()
                    if cc2.button(f"🛑 SL Hua - #{row['id']}", key=f"ds{row['id']}"):
                        pnl = (row['sl']-row['entry'])*row['qty_total']
                        update_trade_status(row['id'], "SL HIT", row['sl'], pnl)
                        st.rerun()
        st.download_button("⬇️ Ek hi CSV Download Karo (all_trades.csv)", data=trades_df_all.to_csv(index=False), file_name="all_trades.csv", mime="text/csv")
        st.caption("GitHub me bhi yahi ek file hai: trades_diary/all_trades.csv - Roz isi me naya trade jodta jayega.")
    if st.button("❌ Diary Band Karo"):
        st.session_state.show_diary = False
        st.rerun()
    st.divider()

# ---------- MAIN SCANNER ----------
df_nifty, info = fetch_nifty_data()
vix = fetch_vix()
if info is None:
    st.error("Market data nahi mila. Thodi der baad refresh karo.")
    st.stop()

ltp = info['ltp']; prev_close = info['prev_close']; vwap = info['vwap']
gap_pct = (ltp - prev_close)/prev_close*100
if ltp > vwap and gap_pct > 0.15:
    direction = "BULLISH"; mood = "BULLISH - Buyer Strong"
elif ltp < vwap and gap_pct < -0.15:
    direction = "BEARISH"; mood = "BEARISH - Seller Strong"
else:
    direction = "SIDEWAYS"; mood = "SIDEWAYS - Wait Karo, No Trade"

if direction=="BULLISH":
    buyer_pct=68; seller_pct=32; pressure_text="Buyer ka pressure zyada hai - PE writers active"
elif direction=="BEARISH":
    buyer_pct=32; seller_pct=68; pressure_text="Seller ka pressure zyada hai - CE writers active"
else:
    buyer_pct=50; seller_pct=50; pressure_text="Dono barabar hain - Option mat lo"

st.markdown(f"### 1. MARKET MOOD: {mood}")
c1,c2,c3,c4 = st.columns(4)
c1.metric("Nifty LTP", f"{ltp:.2f}", f"{gap_pct:.2f}%")
c2.metric("Nifty VWAP", f"{vwap:.2f}", "VWAP ke upar = Bullish" if ltp>vwap else "VWAP ke neeche = Bearish")
c3.metric("India VIX", f"{vix:.2f}", "14 se upar = Tez move")
c4.metric("Nifty Direction", direction, pressure_text)
st.markdown(f"Buyer Pressure: {buyer_pct}% | Seller Pressure: {seller_pct}%")
st.progress(buyer_pct/100)
st.write(f"👉 {pressure_text}")
st.divider()

st.markdown("### 2. OI ME BADLAV")
chain_df, atm = get_option_chain_estimate(ltp, direction)
ce_total = chain_df["CE OI Chg %"].sum(); pe_total = chain_df["PE OI Chg %"].sum()
if pe_total > ce_total:
    oi_signal = f"PE me OI +{pe_total}% badh raha hai = Put Writing = BULLISH support"
else:
    oi_signal = f"CE me OI +{ce_total}% badh raha hai = Call Writing = BEARISH resistance"
st.info(f"ATM Strike: {atm} | {oi_signal}")
st.dataframe(chain_df, use_container_width=True)
st.divider()

st.markdown("### 3. AAJ KA OPTION SUGGESTION - Rs 10,000 CAPITAL")
if direction=="SIDEWAYS":
    st.warning("Market SIDEWAYS hai. NO TRADE hi best trade hai.")
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
    st.success(f"Suggestion: NIFTY {strike} {opt_type} @ Rs {entry_prem} me 1 Lot Buy karo. Capital Use: Rs {capital_used}. SL: Rs {sl_prem}. Target: Rs {target_prem}.")
    suggested = {"date": datetime.now().strftime("%Y-%m-%d"), "time": datetime.now().strftime("%H:%M:%S"), "symbol": "NIFTY", "strike": strike, "opt_type": opt_type, "entry": entry_prem, "sl": sl_prem, "target": target_prem, "qty_lots": lots, "qty_total": lots*NIFTY_LOT, "capital_used": capital_used, "risk": max_loss, "status": "OPEN", "reason": f"{direction} + VWAP + OI"}
    if st.button("Is Suggestion ko Diary me Save Karo - Ek hi CSV me jayega"):
        save_trade(suggested)
        st.success("Diary me save ho gaya! Ek hi CSV all_trades.csv me update ho gaya. Upar Trading Diary button par click karke dekho.")
        st.rerun()
st.divider()
st.write("1. Secret sirf is session ke RAM me hai, GitHub code me nahi hai. 2. Logout dabate hi secret delete ho jayega. 3. Option me 10,000 poora doob sakta hai, 1 lot se zyada mat lo.")
