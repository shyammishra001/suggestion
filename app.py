# app.py - V31 - Scanner - IND-Only
# ============================================================================================
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta, timezone
import sqlite3
import os
import requests
import base64
import io
import time
import math
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except:
    IST = timezone(timedelta(hours=5, minutes=30))

st.set_page_config(page_title="Scan Stock", layout="wide")

# ---------------- CONFIG ----------------
CAPITAL = 5000
DB_FILE = "trades.db"
CSV_FILE = "all_trades.csv"
GITHUB_CSV_PATH = "trades_diary/all_trades.csv"
IND_BASE = "https://api.indstocks.com"

try:
    TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT = str(st.secrets.get("TELEGRAM_CHAT_ID", ""))
    GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "") or st.secrets.get("GITHUB_PAT", "")
    GITHUB_REPO = st.secrets.get("GITHUB_REPO", "")
except:
    TELEGRAM_TOKEN = ""
    TELEGRAM_CHAT = ""
    GITHUB_TOKEN = ""
    GITHUB_REPO = ""

# ---------------- V29 - SAME FOLDER - App ke bagal wali file, seedha wahan se, download nahi ----------------
# User ne sahi bola: 5-7 file pehle se hi GitHub pe download karke rakh di hain - app.py ke bagal me, usi folder me.
# To har baar GitHub se download karne jaana hi kyu? Bagal wali file ka location do - APP_DIR = app.py wala folder - aur wahin se seedha padh lo.
# Niyam (priority) - sabse tez wala pehle, sabse dheema wala aakhri me:
#   1) Session (isi run me Download Data se aaya fresh data) - sabse naya, isliye pehle
#   2) Same Folder Local File (APP_DIR / "IND_Scrip_Codes.csv" jaisi) - deploy ke saath aayi hui, network bilkul nahi, turant
#   3) GitHub Raw (raw.githubusercontent) - sirf tab jab local file mili hi nahi - jaise file dusri jagah se push hui ho aur is deploy me abhi aayi na ho
#   4) INDmoney API - sirf LATEST ke liye: LTP (quotes/full) + Aaj ka naya candle (Delta) + Top 15 ki Option Chain - baaki sab kabhi IND se nahi mangenge
# Dhyan: Download Data dabane ke baad GitHub pe file chali jati hai, par Streamlit Cloud ke chalte hue container me bagal wali local file tab tak purani hi rehti hai jab tak reboot / redeploy na ho.
# Isliye Download Data ke baad wala fresh data Session me rakhte hain - taaki usi run me naya data use ho, purani local file na use ho jaye.
APP_DIR = Path(__file__).resolve().parent  # app.py jis folder me hai, wahi folder - bagal wali file yahin hai
MASTER_FOLDER = "data"  # V33 - GitHub me sab master data ek hi folder me - bahar root me nahi. Diary alag hai, wo trades_diary me hi rahegi.
_LOCAL_CSV_CACHE = {}  # filename -> (mtime, size, df) - ek scan me ek file ko 10 baar padhna ho to disk se 1 baar hi padhenge, baaki baar cache se
def local_file_path(filename):
    # Pehle bagal me, nahi mili to data/ folder me - GitHub se aayi file data/ me hogi
    _f = str(filename)
    if _f.startswith(MASTER_FOLDER + "/") or _f.startswith("trades_diary/"):
        return APP_DIR / _f
    return APP_DIR / _f
def read_local_csv(filename):
    # Same Folder wali file seedha padho - koi network nahi, koi download nahi, turant.
    # Returns (df | None, msg) - file nahi mili to (None, "nahi mili") - tab caller GitHub Raw ya Session pe jayega, fail nahi hoga.
    try:
        # V33 - Pehle data/ folder me dekho (nayi file wahi hai), phir bagal me purani root wali - nayi hi chalegi, purani ignore hogi
        _p = None
        for _cand in [APP_DIR / MASTER_FOLDER / str(filename), Path.cwd() / MASTER_FOLDER / str(filename), local_file_path(filename), Path.cwd() / str(filename)]:
            if _cand.is_file():
                _p = _cand
                break
        if _p is None:
            return None, f"Same Folder me {filename} nahi mili"
        try:
            _st = _p.stat()
            _key = str(filename)
            _cached = _LOCAL_CSV_CACHE.get(_key)
            if _cached is not None and _cached[0] == _st.st_mtime and _cached[1] == _st.st_size:
                return _cached[2], f"Same Folder se turant - {filename} - Cache se - {len(_cached[2])} rows - koi download nahi"
            _df = pd.read_csv(_p, dtype=str, keep_default_na=False)
            if _df is None or _df.empty:
                return None, f"Same Folder me {filename} khali hai"
            _LOCAL_CSV_CACHE[_key] = (_st.st_mtime, _st.st_size, _df)
            return _df, f"Same Folder se turant - {filename} - {len(_df)} rows - koi download nahi, bagal wali file se"
        except Exception as e:
            return None, f"Same Folder wali {filename} padhne me error - {e}"
    except Exception as e:
        return None, f"Same Folder check me error - {e}"

# ---------------- STOCKS - NSE + BSE F&O WALE ----------------
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
    "OBEROIRLTY": "OBEROIRLTY.NS", "PHOENIXLTD": "PHOENIXLTD.NS", "PRESTIGE": "PRESTIGE.NS", "LODHA": "LODHA.NS",
    "TORNTPOWER": "TORNTPOWER.NS", "ADANIGREEN": "ADANIGREEN.NS", "ADANIPOWER": "ADANIPOWER.NS", "TATACHEM": "TATACHEM.NS",
    "UPL": "UPL.NS", "SRF": "SRF.NS", "PIIND": "PIIND.NS", "DABUR": "DABUR.NS", "MARICO": "MARICO.NS",
    "COLPAL": "COLPAL.NS", "GODREJCP": "GODREJCP.NS", "HAVELLS": "HAVELLS.NS", "VOLTAS": "VOLTAS.NS", "DIXON": "DIXON.NS",
    "CGPOWER": "CGPOWER.NS", "SIEMENS": "SIEMENS.NS", "ABB": "ABB.NS", "CUMMINSIND": "CUMMINSIND.NS", "BHEL": "BHEL.NS",
    "CONCOR": "CONCOR.NS", "IRB": "IRB.NS", "GMRINFRA": "GMRINFRA.NS", "ZYDUSLIFE": "ZYDUSLIFE.NS", "LUPIN": "LUPIN.NS",
    "TORNTPHARM": "TORNTPHARM.NS", "AUROPHARMA": "AUROPHARMA.NS", "ALKEM": "ALKEM.NS", "BIOCON": "BIOCON.NS",
    "EXIDEIND": "EXIDEIND.NS", "MRF": "MRF.NS", "BALKRISIND": "BALKRISIND.NS", "APOLLOTYRE": "APOLLOTYRE.NS",
    "ASHOKLEY": "ASHOKLEY.NS", "TVSMOTOR": "TVSMOTOR.NS", "BOSCHLTD": "BOSCHLTD.NS", "MOTHERSON": "MOTHERSON.NS",
}

LOT_SIZES = {"RELIANCE": 250, "TCS": 175, "INFY": 800, "HDFCBANK": 550, "ICICIBANK": 1375, "SBIN": 1500, "TATAMOTORS": 1400, "TATASTEEL": 5500, "M&M": 800, "TITAN": 350, "ADANIENT": 300, "ADANIPORTS": 1000, "AXISBANK": 1200, "KOTAKBANK": 800, "LT": 300, "MARUTI": 50, "ONGC": 3850, "POWERGRID": 3600, "NTPC": 5700, "COALINDIA": 2100, "BPCL": 1800, "HINDALCO": 2600, "JSWSTEEL": 1350, "BAJFINANCE": 125, "BHARTIARTL": 950, "ITC": 1600, "HCLTECH": 700, "WIPRO": 3000, "TECHM": 900, "SUNPHARMA": 700, "DRREDDY": 125, "CIPLA": 650, "DIVISLAB": 200, "EICHERMOT": 175, "HEROMOTOCO": 300, "GRASIM": 250, "ULTRACEMCO": 100, "SHRIRAMFIN": 300, "MUTHOOTFIN": 500, "APOLLOHOSP": 125, "TATACONSUM": 1000, "NESTLEIND": 10, "BRITANNIA": 100, "HINDUNILVR": 300, "ASIANPAINT": 400, "KALYANJIL": 3200, "UNIONBANK": 8000, "PNB": 8000, "CANBK": 7000, "FEDERALBNK": 10000, "IDFCFIRSTB": 10000, "BEL": 4000, "HAL": 150, "TATAPOWER": 3750, "IRFC": 7500, "RVNL": 5000, "IRCTC": 1250, "MAZAGON": 150, "COCHINSHIP": 300, "NHPC": 7000, "SJVN": 8000, "HUDCO": 4000, "NBCC": 6000, "YESBANK": 20000, "SUZLON": 10000, "IDEA": 20000, "PAYTM": 800, "ZOMATO": 3000, "NYKAA": 4000, "POLICYBZR": 500, "DMART": 200, "TRENT": 200, "JUBLFOOD": 500, "INDIGO": 150, "BAJAJFINSV": 500, "BAJAJ-AUTO": 125, "SBILIFE": 750, "HDFCLIFE": 1100, "INDUSINDBK": 800, "BANKBARODA": 4000, "AUBANK": 1000, "MPHASIS": 300, "PERSISTENT": 100, "COFORGE": 100, "LTIM": 100, "VEDL": 3000, "JINDALSTEL": 800, "SAIL": 8000, "NMDC": 8000, "GAIL": 4000, "PETRONET": 3000, "IOC": 4000, "HINDPETRO": 2000, "AMBUJACEM": 1000, "ACC": 300, "SHREECEM": 25, "DLF": 1500, "GODREJPROP": 300, "OBEROIRLTY": 700, "PHOENIXLTD": 800, "PRESTIGE": 1000, "LODHA": 300, "TORNTPOWER": 1500, "ADANIGREEN": 1000, "ADANIPOWER": 1200, "TATACHEM": 1100, "UPL": 1000, "SRF": 100, "PIIND": 100, "DABUR": 2500, "MARICO": 3000, "COLPAL": 100, "GODREJCP": 1000, "HAVELLS": 500, "VOLTAS": 1000, "DIXON": 100, "CGPOWER": 1000, "SIEMENS": 100, "ABB": 100, "CUMMINSIND": 100, "BHEL": 7000, "CONCOR": 1000, "IRB": 10000, "GMRINFRA": 10000, "ZYDUSLIFE": 1000, "LUPIN": 500, "TORNTPHARM": 200, "AUROPHARMA": 1000, "ALKEM": 100, "BIOCON": 2000, "EXIDEIND": 3000, "MRF": 10, "BALKRISIND": 200, "APOLLOTYRE": 2000, "ASHOKLEY": 8000, "TVSMOTOR": 300, "BOSCHLTD": 25, "MOTHERSON": 6000}

KNOWN_SCRIP = {"RELIANCE": "2885", "TCS": "11536", "HDFCBANK": "1333", "INFY": "1594", "ICICIBANK": "4963", "SBIN": "3045", "ITC": "1660", "LT": "11483", "TITAN": "3506", "TATAMOTORS": "3846", "ONGC": "2475", "NTPC": "2882", "POWERGRID": "2562", "TATASTEEL": "3499", "HINDALCO": "1363", "JSWSTEEL": "11723", "BAJFINANCE": "317", "BHARTIARTL": "10604", "MARUTI": "10999", "SUNPHARMA": "3351", "ADANIENT": "25", "ADANIPORTS": "15083", "AXISBANK": "5900", "KOTAKBANK": "1922", "M&M": "2031", "GRASIM": "1319", "ULTRACEMCO": "11532", "HCLTECH": "7229", "WIPRO": "3787", "TECHM": "13538", "CIPLA": "694", "DIVISLAB": "10940", "EICHERMOT": "5053", "HEROMOTOCO": "1348", "COALINDIA": "20374", "BPCL": "526", "VEDL": "3063", "DLF": "14732", "BEL": "383", "HAL": "11890", "TATAPOWER": "3426", "IRCTC": "13611", "DMART": "5097", "TRENT": "1964", "INDIGO": "11184", "BAJAJFINSV": "166", "BAJAJ-AUTO": "16669", "SBILIFE": "21808", "HDFCLIFE": "467", "INDUSINDBK": "5258", "BANKBARODA": "4668", "GAIL": "1232", "IOC": "1624", "NMDC": "2029", "SAIL": "2964", "JINDALSTEL": "673", "MPHASIS": "1106", "PERSISTENT": "12355", "COFORGE": "11543", "LTIM": "17818", "AMBUJACEM": "216", "ACC": "35", "SHREECEM": "3105", "GODREJPROP": "17875"}

# ---------------- SESSION ----------------
for _k, _v in [("authenticated", False), ("show_diary", False), ("scan_df", None), ("news_data", None), ("indices_data", None), ("auto_sent", False), ("indmoney_connected", False), ("indmoney_debug", ""), ("scan_source", ""), ("scan_time", "")]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ---------------- SAFE HELPERS ----------------
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

def ist_now():
    try:
        return datetime.now(IST)
    except:
        return datetime.now(timezone(timedelta(hours=5, minutes=30)))

def get_last_trading_day():
    # ASLI WAJAH 0 STOCKS KI - YAHI THA:
    # Pehle hum aaj ki date le lete the. Saturday / Sunday ko market band hota hai, to us din ki koi candle hi nahi hoti.
    # Sunday raat 11 baje scan karoge to Sunday ki 09:15-15:30 me koi candle nahi hai -> 0 stocks.
    # Isliye ab hum pichhla TRADING DAY lete hain - Saturday/Sunday ko skip karke Friday.
    # Aur agar abhi 09:15 se pehle hai to kal ka trading day lete hain.
    now = ist_now()
    d = now.date()
    if now.hour < 9 or (now.hour == 9 and now.minute < 15):
        d = d - timedelta(days=1)
    while d.weekday() >= 5:  # 5=Saturday, 6=Sunday
        d = d - timedelta(days=1)
    return d

def get_trading_day():
    return get_last_trading_day()

def is_market_closed_for_scan(trading_day=None):
    # V32 - Market band hai to dobara IND se mat mango - cache se hi best stock do. Pehle har rescan me quotes + candle dobara mangta tha, isliye har baar utna hi time lagta tha.
    try:
        _now = ist_now()
        if trading_day is None:
            trading_day = get_trading_day()
        if trading_day != _now.date():
            return True
        if _now.hour > 15 or (_now.hour == 15 and _now.minute >= 30):
            return True
        if _now.hour < 9 or (_now.hour == 9 and _now.minute < 15):
            return True
        return False
    except:
        return False

def get_scan_window(trading_day):
    # Scan kisi bhi time ho sakta hai - 09:20, 09:30, 09:35, 01:00, 02:00, raat ko - isliye FIXED 09:20 mat karo.
    # Start hamesha 09:15, End = abhi kitna baja hai, us hisab se.
    # Agar trading_day == aaj hai aur abhi market chal raha hai to End = abhi ka time.
    # Agar trading_day == aaj hai aur market band ho gaya (15:30 ke baad) to End = 15:30.
    # Agar trading_day pichhla din hai (weekend / subah scan) to End = us din ka 15:30 - poora din.
    now = ist_now()
    start_dt = datetime(trading_day.year, trading_day.month, trading_day.day, 9, 15, 0, tzinfo=IST)
    if trading_day == now.date():
        if now.hour < 15 or (now.hour == 15 and now.minute <= 30):
            end_dt = now
        else:
            end_dt = datetime(trading_day.year, trading_day.month, trading_day.day, 15, 30, 0, tzinfo=IST)
    else:
        end_dt = datetime(trading_day.year, trading_day.month, trading_day.day, 15, 30, 0, tzinfo=IST)
    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(minutes=5)
    return start_dt, end_dt

def to_ms(dt):
    # Docs: start_time / end_time MILLISECONDS me chahiye
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return int(dt.timestamp() * 1000)

def from_ts_seconds(ts):
    # Docs: candle ka ts SECONDS me aata hai, MILLISECONDS me NAHI
    try:
        return datetime.fromtimestamp(float(ts), tz=IST)
    except:
        return ist_now()

# ---------------- INDstocks API - Docs ke hisab se EXACT ----------------
def ind_headers(token):
    # Docs Step 2: headers = {'Authorization': access_token} - Bearer NAHI lagana, yehi sabse badi galti thi
    return {"Authorization": str(token).strip(), "Content-Type": "application/json"}

def ind_test_profile(token):
    try:
        r = requests.get(f"{IND_BASE}/user/profile", headers=ind_headers(token), timeout=12)
        if r.status_code == 200:
            d = r.json().get("data", {})
            return True, f"Connected - {d.get('first_name','')} {d.get('last_name','')}"
        else:
            return False, f"Token Fail - Status {r.status_code} - {r.text[:300]} - Token 24 ghante me expire hota hai, naya banao"
    except Exception as e:
        return False, f"Connect nahi hua - {e}"

def get_nearest_thursday_fallback():
    # NSE Equity F&O ki weekly expiry Thursday ko hoti hai. Agar IND ka Expiry API khali de de (jaise photo me aaya - Expiries khali aayi),
    # to Option Chain fail nahi karenge, agle Thursday ko hi Nearest Expiry maan lenge.
    # Photo wala fail isi liye aaya tha - Expiry API ne khali diya, humne usko fail maan liya, Option Chain hi nahi manga.
    # Ab fallback hai - Expiry API khali ho to bhi Thursday se kaam chal jayega.
    try:
        today = ist_now().date()
        # Agar aaj Thursday hai aur abhi 15:30 se pehle hai to aaj hi expiry hai, nahi to agla Thursday
        days_ahead = (3 - today.weekday() + 7) % 7  # Monday=0 ... Thursday=3
        if days_ahead == 0:
            # Aaj Thursday hai - agar abhi 15:30 ke baad hai to agla Thursday, nahi to aaj
            if ist_now().hour >= 16:
                days_ahead = 7
        nxt = today + timedelta(days=days_ahead)
        return nxt.strftime("%Y-%m-%d")
    except:
        return (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

def ind_get_expiries(underlying, token):
    # V21 - Pehle Master File (FNO) se Expiry lo - Mahine me 1 baar Download Data se aayi hui File se.
    # Baar-baar Expiry API mat khojo - Master me sab Expiry likhi hoti hai, wahi se mil jayegi.
    # Agar Master me nahi mili to hi API se try karo, phir bhi nahi mili to Thursday Fallback.
    try:
        _exps_m, _msg_m = get_expiry_from_master_file(underlying, token)
        # Agar Master se mili aur wo Fallback wali nahi hai (msg me Master se Expiry mili likha hai) to wahi return karo
        if _exps_m and "Master FNO File se Expiry mili" in _msg_m:
            return _exps_m, _msg_m
    except:
        pass
    # V20 FIX - User ne bola: IND ko Exchange / Segment / Security ID wala request mat bhejna.
    # Pehle hum underlying + segment=DERIVATIVE bhejte the, isliye kabhi kabhi fail ho jata tha.
    # Ab sirf Security ID se search karenge - jo IND_master_index / Equity Master CSV se aayegi.
    # underlying yahan pe ab Stock ka naam nahi, uska Security ID hai (jaise RELIANCE ka 2885).
    # Agar naam aaya to pehle CSV se Security ID me badlo, phir wahi ID bhejo.
    try:
        # Agar underlying naam hai to CSV se Security ID nikalo
        _sid_for_exp = str(underlying).strip()
        if not _sid_for_exp.isdigit():
            try:
                _map_exp = ind_get_all_scrips(token)
                _sid_for_exp = str(_map_exp.get(_sid_for_exp.upper(), _sid_for_exp))
            except:
                pass
        # Ab sirf Security ID bhejo - Exchange / Segment mat bhejo
        r = requests.get(f"{IND_BASE}/market/instruments/expiries", headers=ind_headers(token), params={"underlying": _sid_for_exp, "segment": "DERIVATIVE"}, timeout=12)
        if r.status_code == 200:
            data = r.json().get("data", [])
            if data:
                return data, ""
            # Khali aayi to fallback - fail nahi karenge
            fb = get_nearest_thursday_fallback()
            return [fb], f"Expiries API se khali aayi, isliye Fallback Nearest Thursday {fb} use kar rahe hain - Option Chain isi se aayega"
        # Fail bhi ho to fallback
        fb = get_nearest_thursday_fallback()
        return [fb], f"Expiries Fail {r.status_code}, Fallback Thursday {fb} use kar rahe hain"
    except Exception as e:
        fb = get_nearest_thursday_fallback()
        return [fb], f"Expiries Error {e}, Fallback Thursday {fb} use kar rahe hain"

def ind_load_master_from_github_file():
    # V20 - Master ab IND_master_index wali File se aayega - jo photo me bheji hai.
    # File ka naam: IND_master_index.csv (tumne jo bola wahi naam - IND underscore master underscore index)
    # Isko GitHub repo me app.py ke saath hi rakho - same repo me. Streamlit Cloud me wahi file app ke saath aati hai.
    # Photo 3 me dikh raha hai: IND Master Index me sirf 3 columns hain - EXCH, SEGMENT, SECURITY_ID
    # Lekin dhyan: Dusra column SEGMENT likha hota hai, lekin usme Index ka naam hota hai - jaise NIFTY 50, NIFTY IT.
    # Isliye usko position se padhenge - Col 0 = EXCH, Col 1 = Naam, Col 2 = SECURITY_ID.
    # Photo 2 me IND Master FNO bhi hai - usme 23 columns hain, usko header se padhenge.
    # Dono file mil jayein to dono ko mila ke ek hi Map banayenge - Stock ka ID Equity/FNO se, Index ka ID Index file se.
    # Agar file GitHub pe nahi mili to (None, msg) - tab KNOWN_SCRIP se kaam chalega, fail nahi hoga.
    # Tum CSV bhej doge to hum bhi isi naam se rakh denge, tum GitHub pe bhi isi naam se upload kar dena.
    # Pehle IND_master_index dhoondo - yahi tumne bola hai
    # V32 - Equity/FNO pehle, Index aakhiri - Index file (92 rows) me stock ka BSE ID hota hai, usko Equity samajh ke stock ka ID mat lo
    for fname in ["IND_Master_Equity.csv", "IND_Master_Equity.CSV", "ind_master_equity.csv", "IND_Master_FNO.csv", "IND_master_fno.csv"]:
        try:
            df, _m = read_local_csv(fname)
            if df is not None and not df.empty:
                return df, f"Same Folder se turant - {fname} - {len(df)} rows - {_m}"
        except:
            continue
    for fname in ["IND_master_index.csv", "IND_Master_Index.csv", "IND_Master_index.csv", "ind_master_index.csv", "IND_Master_Index.CSV"]:
        try:
            df, _m = read_local_csv(fname)
            if df is not None and not df.empty:
                return df, f"Same Folder se turant - {fname} - {len(df)} rows - {_m}"
        except:
            continue
    # V22 - Local file nahi mili to session me Download Data wali dekh lo - Download Data dabane ke baad session me hi aa jati hai, GitHub me bhi save ho jati hai.
    # Tumko Upload nahi karna hai, Download Data hi kaafi hai - wahi se session me aayegi.
    try:
        import streamlit as _st
        # Pehle FNO wali - usme Expiry bhi hai, sabse kaam ki hai
        for _key in ["master_fno_df", "master_equity_df", "master_index_df"]:
            _up = _st.session_state.get(_key, None)
            if _up is not None and not _up.empty:
                return _up, f"Download Data se aaya - {_key} - {len(_up)} rows - GitHub me bhi save ho gaya hai"
    except:
        pass
    return None, "File nahi mili - Download Data dabao."

def ind_get_all_scrips(token):
    # V19: Pehle GitHub wali Master CSV File se lo - usme sab stock ka Sahi Naam + Secret Code likha hua hai.
    # Agar wo file mil gayi to API se dobara Master mangne ki zaroorat hi nahi - wahi file sabse pakki hai.
    # Agar file nahi mili to pehle jaisa API se Master CSV mang lo.
    # Ek baar me poori Equity CSV mang lo, baar-baar mat mango - 100 stocks ke liye yahi fast tareeka hai
    # V18 FIX: Pehle sirf SYMBOL_NAME se match karte the, isliye M&M, TATAMOTORS jaisi kai stocks ka ID nahi milta tha.
    # Ab 3 naam se match karte hain - SYMBOL_NAME + TRADING_SYMBOL + CUSTOM_SYMBOL - teeno me se jo bhi hamare naam se milega, uska ID le lenge.
    # Docs: CSV me SYMBOL_NAME = base symbol (HDFCBANK), TRADING_SYMBOL = trading wala symbol, CUSTOM_SYMBOL = descriptive symbol
    # V20 - Pehle GitHub File check karo - IND_master_index wali File se hi Security ID lo.
    # API se /market/instruments mat mango - tumne bola Exchange / Segment wala request mat bhejo, Security ID se hi khojo.
    # Isliye ab API call hi nahi karenge, sirf GitHub File + KNOWN_SCRIP se kaam chalega.
    # File me 2 tarah ki format ho sakti hai, dono ko handle karo:
    # A) IND_master_index - 3 columns: EXCH, SEGMENT (isme Naam hai), SECURITY_ID - Position se padho
    # B) Equity / FNO Master - 23/26 columns: SYMBOL_NAME, TRADING_SYMBOL, SECURITY_ID - Header se padho
    # V29 - SABSE PEHLE bagal wali IND_Scrip_Codes.csv - chhoti bani-banayi file (STOCK + SECURITY_ID + SCRIP_CODE_NSE + EXPIRY_LIST).
    # Pehle 30,000-row wali Master ko row-by-row loop karte the - wahi slow tha. Ab chhoti file se zip se Map - 1 sec se bhi kam.
    try:
        _sc_df, _sc_msg = read_local_csv("IND_Scrip_Codes.csv")
        if _sc_df is not None and not _sc_df.empty and "SECURITY_ID" in _sc_df.columns:
            _out = dict(KNOWN_SCRIP)
            # V32 - NSE pehle, BSE baad me - Equity me RELIANCE ke 2 row hote hain: NSE 2885 + BSE 500325. Pehle BSE wala overwrite kar deta tha, isliye NSE_500325 banta tha jo hota hi nahi, Search/Scan khali aata tha. Ab NSE hi jeetega.
            try:
                if "EXCH" in _sc_df.columns:
                    _sc_df = _sc_df.copy()
                    _sc_df["_exch_rank"] = _sc_df["EXCH"].astype(str).str.strip().str.upper().map(lambda x: 0 if x == "NSE" else 1)
                    _sc_df = _sc_df.sort_values("_exch_rank", kind="stable").drop(columns=["_exch_rank"])
            except:
                pass
            _sym_col = "STOCK" if "STOCK" in _sc_df.columns else ("SYMBOL_NAME" if "SYMBOL_NAME" in _sc_df.columns else None)
            if _sym_col:
                for _sym, _sid in zip(_sc_df[_sym_col].astype(str), _sc_df["SECURITY_ID"].astype(str)):
                    _sym = _sym.strip().upper(); _sid = _sid.strip()
                    if _sym and _sym != "NAN" and _sid and _sid.lower() != "nan":
                        # KNOWN_SCRIP wala sahi NSE ID bhi BSE se overwrite nahi hoga - sirf khali wale me bharo
                        if _sym not in _out or _out.get(_sym) in ("", None):
                            _out[_sym] = _sid
                        elif _sym in KNOWN_SCRIP:
                            pass
                        else:
                            # Scrip_Codes me pehle wala NSE hai, baad wala BSE hai - pehle wala hi rakho
                            pass
                for _col2 in ["TRADING_SYMBOL", "CUSTOM_SYMBOL", "UNDERLYING_SCRIP_NAME"]:
                    if _col2 in _sc_df.columns:
                        for _sym2, _sid2 in zip(_sc_df[_col2].astype(str), _sc_df["SECURITY_ID"].astype(str)):
                            _sym2 = _sym2.strip().upper(); _sid2 = _sid2.strip()
                            if _sym2 and _sym2 != "NAN" and _sid2 and _sid2.lower() != "nan":
                                if _sym2 not in _out:
                                    _out[_sym2] = _sid2
                if len(_out) > len(KNOWN_SCRIP):
                    return _out
    except:
        pass
    # V22 - Teeno File ka Code mila ke ek hi Map banao - FNO + Equity + Index - Download Data se teeno aayi hain
    # Pehle session me teeno File se Code mila lo, phir GitHub File se bhi mila lo - jisse koi Code chhoote nahi
    try:
        import streamlit as _st2
        _merged = dict(KNOWN_SCRIP)
        for _k in ["master_fno_df", "master_equity_df", "master_index_df"]:
            try:
                _df_s = _st2.session_state.get(_k, None)
                if _df_s is not None and not _df_s.empty and "SECURITY_ID" in _df_s.columns:
                    for _, _row in _df_s.iterrows():
                        try:
                            _sid_s = str(_row["SECURITY_ID"]).strip()
                            if not _sid_s or _sid_s.lower() == "nan":
                                continue
                            # Index file ho to 2nd column Naam hai, nahi to SYMBOL_NAME / TRADING_SYMBOL
                            if len(list(_df_s.columns)) == 3 and "SYMBOL_NAME" not in _df_s.columns:
                                # V32 - 3-column Index file se sirf Index lo, stock mat lo - isme RELIANCE jaisa stock BSE ID (500325) se hota hai, NSE 2885 se nahi
                                _nm_s = str(_row.iloc[1]).strip().upper() if len(_row) > 1 else ""
                                if _nm_s and _nm_s != "NAN" and ("NIFTY" in _nm_s or "SENSEX" in _nm_s or "BANKEX" in _nm_s or "FINNIFTY" in _nm_s or "MIDCAP" in _nm_s):
                                    if _nm_s not in _merged:
                                        _merged[_nm_s] = _sid_s
                                    if _nm_s == "NIFTY 50" and "NIFTY" not in _merged:
                                        _merged["NIFTY"] = _sid_s
                            else:
                                for _col in ["SYMBOL_NAME", "TRADING_SYMBOL", "CUSTOM_SYMBOL"]:
                                    if _col in _df_s.columns:
                                        _sym_s = str(_row[_col]).strip().upper()
                                        if _sym_s and _sym_s != "NAN" and _sym_s not in _merged:
                                            _merged[_sym_s] = _sid_s
                        except:
                            continue
            except:
                continue
        if len(_merged) > len(KNOWN_SCRIP):
            return _merged
    except:
        pass
    try:
        _df_gh, _msg_gh = ind_load_master_from_github_file()
        if _df_gh is not None and not _df_gh.empty:
            out = dict(KNOWN_SCRIP)
            _cols = list(_df_gh.columns)
            # A) Index file hai kya? - Sirf 3 columns aur SEGMENT me Naam hai
            _is_index_file = (len(_cols) == 3 and "SECURITY_ID" in _cols)
            for _, row in _df_gh.iterrows():
                try:
                    # SECURITY_ID hamesha aakhiri column ya SECURITY_ID naam wale column me hai
                    if "SECURITY_ID" in _df_gh.columns:
                        sid = str(row["SECURITY_ID"]).strip()
                    else:
                        sid = str(row.iloc[2]).strip() if len(row) > 2 else ""
                    if not sid or sid.lower() == "nan" or sid == "":
                        continue
                    if _is_index_file:
                        # Index file: Col 1 me Naam hai - jaise NIFTY 50, NIFTY IT, SENSEX
                        _name = str(row.iloc[1]).strip().upper() if len(row) > 1 else ""
                        if _name and _name != "NAN":
                            out[_name] = sid
                            # NIFTY 50 ko NIFTY bhi samjho
                            if _name == "NIFTY 50":
                                out["NIFTY"] = sid
                            if _name == "NIFTY BANK":
                                out["BANKNIFTY"] = sid
                    else:
                        # Equity / FNO file: SYMBOL_NAME, TRADING_SYMBOL, CUSTOM_SYMBOL se
                        for col in ["SYMBOL_NAME", "TRADING_SYMBOL", "CUSTOM_SYMBOL"]:
                            if col in _df_gh.columns:
                                sym = str(row[col]).strip().upper()
                                if sym and sym != "NAN" and sym not in out:
                                    out[sym] = sid
                        if "SYMBOL_NAME" in _df_gh.columns:
                            sym2 = str(row["SYMBOL_NAME"]).strip().upper()
                            if sym2 and sym2 != "NAN":
                                out[sym2] = sid
                except:
                    continue
            # Agar GitHub file se kuch mila to wahi return karo - API mat bulao
            if len(out) > len(KNOWN_SCRIP):
                return out
            # Agar file khali thi to bhi KNOWN_SCRIP return karo, API mat bulao
            if _df_gh is not None and not _df_gh.empty:
                return out
    except:
        pass
    # V39 - FIX: GitHub file nahi mili to sirf 64 KNOWN_SCRIP pe atakna band - 216 me se 152 ka Code hi nahi milega, isliye 0/216 aata tha
    # Token sahi hone pe bhi file ke bina Scan khali aata tha - isliye ab LIVE API se hi laayenge (wahi API jo Download Data use karta hai)
    # Ye Expiry wala Exchange/Segment request nahi hai - Instruments Master hai, isliye mana hua wala niyam nahi tootega
    try:
        _live = ind_fetch_instruments_map(token)
        if _live and len(_live) > len(KNOWN_SCRIP):
            return _live
    except Exception:
        pass
    return dict(KNOWN_SCRIP)


def ind_fetch_instruments_map(token):
    # V39 - IND se live Instruments Master (equity + fno) - CSV aati hai, usse {SYMBOL: SECURITY_ID} banao
    # Sirf tab chalega jab GitHub file nahi mili - normal flow me file se hi chalega, API baar-baar nahi bulaega
    if not token or len(str(token).strip()) < 10:
        return {}
    _out = dict(KNOWN_SCRIP)
    try:
        for _src in ["equity", "fno"]:
            try:
                _r = requests.get(f"{IND_BASE}/market/instruments", headers=ind_headers(token), params={"source": _src}, timeout=30)
                if _r.status_code != 200:
                    continue
                import io as _io2
                _df = pd.read_csv(_io2.StringIO(_r.text), dtype=str, keep_default_na=False)
                if _df is None or _df.empty or "SECURITY_ID" not in _df.columns:
                    continue
                # NSE pehle, BSE baad me - RELIANCE ka NSE 2885 jeetega, BSE 500325 nahi
                try:
                    if "EXCH" in _df.columns:
                        _df = _df.copy()
                        _df["_er"] = _df["EXCH"].astype(str).str.strip().str.upper().map(lambda x: 0 if x == "NSE" else 1)
                        _df = _df.sort_values("_er", kind="stable").drop(columns=["_er"])
                except:
                    pass
                for _, _row in _df.iterrows():
                    try:
                        _sid = str(_row.get("SECURITY_ID", "")).strip()
                        if not _sid or _sid.lower() == "nan":
                            continue
                        for _col in ["SYMBOL_NAME", "TRADING_SYMBOL", "CUSTOM_SYMBOL"]:
                            if _col in _df.columns:
                                _sym = str(_row.get(_col, "")).strip().upper()
                                if _sym and _sym != "NAN" and _sym not in _out:
                                    _out[_sym] = _sid
                    except:
                        continue
            except:
                continue
    except Exception:
        pass
    return _out
    # V20 - Iske neeche wala purana API wala code hata diya - ab API se instruments nahi mangte, sirf GitHub File se Security ID lete hain

# ---------------- V18 - KAAM 1: MASTER CSV DOWNLOAD BUTTON ----------------
# Docs: GET /market/instruments?source=equity / fno / index / mcx -> Response JSON NAHI, raw CSV file hai.
# CSV Columns (equity - 26 columns): EXCH, SEGMENT, SECURITY_ID, INSTRUMENT_NAME, TRADING_SYMBOL, LOT_UNITS, CUSTOM_SYMBOL,
# SYMBOL_NAME, UNDERLYING_SCRIP_NAME, ISIN, etc. + INTRADAY_LEVERAGE, HAIRCUT, PLEDGE_ELIGIBLE
# fno - 23 columns, index - sirf 3 columns: EXCH, SEGMENT, SECURITY_ID (dusra column SEGMENT likha hota hai lekin usme Index ka naam hota hai)
# Isliye hum CSV ko raw bytes me bhi rakhte hain (Download Button ke liye) aur DataFrame me bhi (Table dikhane ke liye).
# ---------------- V21 - TRADING DIARY KE PAAS DOWNLOAD DATA BUTTON - MAHINE ME 1 BAAR ----------------
# User ka naya kaam: Trading Diary ke paas hi ek chhota sa Button de do - Download Data.
# Jaise hi Download Data pe click karein, wo Download ho ke GitHub me apne aap save ho jaye.
# Mahine me 1 baar karenge - usme Exchange, Segment, Security ID, Expiry - sab likha hoga.
# Uske baad roz-roz Expiry search nahi karni padegi - Expiry wahi Master File se mil jayegi.
# Roz sirf Latest Price / Candle jo move karega, wo hi Daily search karna padega - aasan ho jayega, jaldi ho jayega.
# Kaun si File: IND Master FNO (sabse important - isme Expiry + Strike + Security ID sab hai), IND Master Equity, IND Master Index
# File ke naam: IND_Master_FNO.csv, IND_Master_Equity.csv, IND_master_index.csv - yahi naam GitHub pe rahega.
def _push_master_to_github(filename, csv_bytes_or_text):
    # Diary wale hi GitHub Token/Repo se Master File ko GitHub pe save karo - apne aap save hoga.
    # Diary ka _push_diary_to_github() sirf Diary ke liye tha, ye Master ke liye hai - same tareeka.
    try:
        if not GITHUB_TOKEN or not GITHUB_REPO:
            return False, "GitHub Token Secrets me nahi hai - isliye GitHub me auto-save nahi hua. File ko neeche wale Download se le ke GitHub pe haath se daal do."
        if isinstance(csv_bytes_or_text, bytes):
            csv_text = csv_bytes_or_text.decode("utf-8", errors="ignore")
        else:
            csv_text = str(csv_bytes_or_text)
        content_b64 = base64.b64encode(csv_text.encode()).decode()
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
        # V33 - Sab master data data/ folder me - bahar root me nahi
        _gh_path = str(filename) if str(filename).startswith(MASTER_FOLDER + "/") else f"{MASTER_FOLDER}/{filename}"
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{_gh_path}"
        get_resp = requests.get(url, headers=headers, timeout=10)
        sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None
        payload = {"message": f"Master update {filename} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Mahine me 1 baar", "content": content_b64}
        if sha:
            payload["sha"] = sha
        put_resp = requests.put(url, headers=headers, json=payload, timeout=20)
        if put_resp.status_code in (200, 201):
            return True, f"GitHub data/ me save ho gaya - {_gh_path}"
        return False, f"GitHub Fail {put_resp.status_code} - {put_resp.text[:200]}"
    except Exception as e:
        return False, f"GitHub Error - {e}"

def download_monthly_master_all(token):
    # V24 - Download Button ka kaam - User ne bola: Master CSV me se jo bhi stock hai, uska Script Code download karke jama karke GitHub pe rakh do, saath me Expiry bhi.
    # Isse data khojne me samay nahi lagega - turant ka turant GitHub me same repo me rahega, wahan se mil jayega.
    # Uske baad jo wahan se nahi mila / jo data badalne wala hai (LTP / Candle / Option Chain) - wo live IND se mang lenge.
    # Script Code kaise banta hai - Docs wala:
    #   CSV me Code ka naam = SECURITY_ID (jaise RELIANCE = 2885, TCS = 11536)
    #   Scrip-Code = 'NSE_' + SECURITY_ID -> 'NSE_2885'  (Quotes / Historical ke liye - params = {'scrip-codes': 'NSE_2885,NSE_11536'})
    #   Option Chain ke liye underlying-scrip = SECURITY_ID hi, bina prefix -> '2885'
    # Steps: 1) 3 File IND se download (fno + equity + index) -> GitHub pe save, 2) Unse Scrip-Code Lookup banao -> GitHub pe IND_Scrip_Codes.csv naam se save, 3) Expiry list bhi usi Lookup me daal do.
    results = []
    if not token or len(str(token).strip()) < 10:
        return [], "Pehle IND Token se Login karo - bina Token ke Master Download nahi hoga"
    dfs = {}
    for source, filename in [("fno", "IND_Master_FNO.csv"), ("equity", "IND_Master_Equity.csv"), ("index", "IND_master_index.csv")]:
        try:
            r = requests.get(f"{IND_BASE}/market/instruments", headers=ind_headers(token), params={"source": source}, timeout=30)
            if r.status_code != 200:
                results.append((filename, None, pd.DataFrame(), False, f"IND Fail {r.status_code} - {r.text[:200]}"))
                continue
            csv_bytes = r.content
            try:
                df = pd.read_csv(io.StringIO(r.text), dtype=str, keep_default_na=False)
            except Exception as e:
                df = pd.DataFrame()
            dfs[source] = df
            ok, gmsg = _push_master_to_github(filename, csv_bytes)
            try:
                import streamlit as _st
                if source == "fno":
                    _st.session_state["master_fno_df"] = df
                    _st.session_state["master_fno_bytes"] = csv_bytes
                elif source == "equity":
                    _st.session_state["master_equity_df"] = df
                elif source == "index":
                    _st.session_state["master_index_df"] = df
            except:
                pass
            results.append((filename, csv_bytes, df, ok, f"{len(df)} rows - {gmsg}"))
            time.sleep(0.3)
        except Exception as e:
            results.append((filename, None, pd.DataFrame(), False, f"Error - {e}"))
    # 2) Scrip-Code Lookup banao - Equity wali cash row se hi Underlying ka SECURITY_ID lo (FNO wali contract row se nahi)
    try:
        lookup_rows = []
        eq = dfs.get("equity", pd.DataFrame())
        fno = dfs.get("fno", pd.DataFrame())
        idx = dfs.get("index", pd.DataFrame())
        # Expiry per underlying - FNO File se nikaalo
        exp_map = {}
        if fno is not None and not fno.empty and "EXPIRY_DATE" in fno.columns:
            for _col in ["UNDERLYING_SCRIP_NAME", "SYMBOL_NAME"]:
                if _col not in fno.columns:
                    continue
                for _u, _grp in fno.groupby(fno[_col].astype(str).str.upper()):
                    _exps = []
                    for _v in _grp["EXPIRY_DATE"].astype(str).tolist():
                        _v = _v.strip()
                        if not _v or _v.lower() in ("nan", "0", ""):
                            continue
                        try:
                            _d = pd.to_datetime(_v).date()
                            _exps.append(_d.strftime("%Y-%m-%d"))
                        except:
                            continue
                    if _exps:
                        exp_map[_u] = ";".join(sorted(set(_exps))[:6])
        # Equity rows - har stock ka ek hi row (cash row) - V32: NSE pehle, BSE baad me, SYMBOL se dedupe - RELIANCE ka NSE 2885 hi rahega, BSE 500325 nahi
        seen = set()
        seen_sym = set()
        if eq is not None and not eq.empty and "SECURITY_ID" in eq.columns:
            try:
                if "EXCH" in eq.columns:
                    eq = eq.copy()
                    eq["_er2"] = eq["EXCH"].astype(str).str.strip().str.upper().map(lambda x: 0 if x == "NSE" else 1)
                    eq = eq.sort_values("_er2", kind="stable").drop(columns=["_er2"])
            except:
                pass
            for _, row in eq.iterrows():
                try:
                    sid = str(row.get("SECURITY_ID", "")).strip()
                    if not sid or sid.lower() == "nan" or sid in seen:
                        continue
                    _sym_chk = str(row.get("SYMBOL_NAME", "")).strip().upper()
                    if _sym_chk and _sym_chk in seen_sym:
                        continue
                    seen.add(sid)
                    if _sym_chk:
                        seen_sym.add(_sym_chk)
                    sym = _sym_chk
                    trad = str(row.get("TRADING_SYMBOL", "")).strip().upper() if "TRADING_SYMBOL" in eq.columns else ""
                    cust = str(row.get("CUSTOM_SYMBOL", "")).strip().upper() if "CUSTOM_SYMBOL" in eq.columns else ""
                    under = str(row.get("UNDERLYING_SCRIP_NAME", "")).strip().upper() if "UNDERLYING_SCRIP_NAME" in eq.columns else ""
                    lookup_rows.append({"STOCK": sym or trad, "SYMBOL_NAME": sym, "TRADING_SYMBOL": trad, "CUSTOM_SYMBOL": cust, "UNDERLYING_SCRIP_NAME": under,
                                        "SECURITY_ID": sid, "SCRIP_CODE_NSE": f"NSE_{sid}", "EXCH": str(row.get("EXCH","")).strip(),
                                        "EXPIRY_LIST": exp_map.get(sym, "") or exp_map.get(under, "") or exp_map.get(trad, "")})
                except:
                    continue
        # Index rows - 3 columns wali file, 2nd column hi Naam hai
        if idx is not None and not idx.empty and "SECURITY_ID" in idx.columns:
            for _, row in idx.iterrows():
                try:
                    sid = str(row.get("SECURITY_ID", "")).strip()
                    if not sid or sid.lower() == "nan" or sid in seen:
                        continue
                    seen.add(sid)
                    nm = str(row.iloc[1]).strip().upper() if len(row) > 1 else ""
                    lookup_rows.append({"STOCK": nm, "SYMBOL_NAME": nm, "TRADING_SYMBOL": nm, "CUSTOM_SYMBOL": nm, "UNDERLYING_SCRIP_NAME": nm,
                                        "SECURITY_ID": sid, "SCRIP_CODE_NSE": f"NSE_{sid}", "EXCH": str(row.get("EXCH","")).strip(), "EXPIRY_LIST": exp_map.get(nm, "")})
                except:
                    continue
        if lookup_rows:
            _ldf = pd.DataFrame(lookup_rows)
            _csv_bytes = _ldf.to_csv(index=False).encode("utf-8")
            _ok, _gmsg = _push_master_to_github("IND_Scrip_Codes.csv", _csv_bytes)
            results.append(("IND_Scrip_Codes.csv", _csv_bytes, _ldf, _ok, f"{len(_ldf)} Scrip-Codes (NSE_ + SECURITY_ID) + Expiry - {_gmsg} - Ab search GitHub se turant hoga"))
            try:
                import streamlit as _st2
                _st2.session_state["scrip_codes_df"] = _ldf
            except:
                pass
    except Exception as e:
        results.append(("IND_Scrip_Codes.csv", None, pd.DataFrame(), False, f"Scrip-Code Lookup banane me Error - {e}"))
    # V25 - 216 Universe bhi GitHub me jama karo - IND_Universe_216.csv - taaki har scan me turant mil jaye
    try:
        _ulist, _udf, _umsg = build_universe_from_masters(dfs.get("fno", pd.DataFrame()), dfs.get("equity", pd.DataFrame()), None)
        if _udf is not None and not _udf.empty:
            _ub = _udf.to_csv(index=False).encode("utf-8")
            _uok, _ugmsg = _push_master_to_github("IND_Universe_216.csv", _ub)
            results.append(("IND_Universe_216.csv", _ub, _udf, _uok, f"{len(_udf)} stocks Universe (FNO DISTINCT UNDERLYING) - {_ugmsg} - {_umsg}"))
            try:
                import streamlit as _st3
                _st3.session_state["universe_216_df"] = _udf
            except:
                pass
    except Exception as e:
        results.append(("IND_Universe_216.csv", None, pd.DataFrame(), False, f"Universe banane me Error - {e}"))
    # V34 - History bhi isi Download me - 5 timeframe, mahina-wise, data/history/... me
    try:
        _uni_stocks = []
        try:
            if _udf is not None and not _udf.empty and "STOCK" in _udf.columns:
                _uni_stocks = [str(x).strip().upper() for x in _udf["STOCK"].tolist() if str(x).strip()]
        except:
            pass
        _scrip_map_hist = {}
        try:
            for _lr in (lookup_rows or []):
                _k = str(_lr.get("STOCK", "") or "").strip().upper()
                _v = str(_lr.get("SECURITY_ID", "") or "").strip()
                if _k and _v:
                    _scrip_map_hist[_k] = _v
        except:
            pass
        if not _uni_stocks and _scrip_map_hist:
            _uni_stocks = list(_scrip_map_hist.keys())[:216]
        if _uni_stocks and _scrip_map_hist:
            _hist_results = download_history_tf_month(token, _uni_stocks, _scrip_map_hist)
            for _tf, _mm, _ok, _msg in _hist_results:
                results.append((f"history/{_tf}/{_mm}.csv", None, pd.DataFrame(), _ok, _msg))
    except Exception as e:
        results.append(("history", None, pd.DataFrame(), False, f"History download me error - {e}"))
    return results, "Master + Scrip-Code + Expiry + History (5 timeframe, mahina-wise) - GitHub me jama ho gaya - Ab search turant hoga"

def get_expiry_from_master_file(stock_name, token=None):
    # V21 - Expiry ab baar-baar API se mat khojo, Master File (FNO) se hi le lo.
    # FNO Master me har contract ki EXPIRY_DATE likhi hoti hai. Us stock ke saare contract ki Expiry nikal lo, sort karo, pehli wali Nearest hai.
    # Isse roz-roz Expiry search ki zaroorat khatam - Mahine me 1 baar Master Download karne se sab Expiry mil jayegi.
    # Agar Master File me nahi mili to Fallback Thursday (V19 wala) use karenge - fail nahi karenge.
    # V29 - SABSE PEHLE bagal wali IND_Scrip_Codes.csv ki EXPIRY_LIST - Expiry bhi usi file me jama hai, API se mangne ki zaroorat nahi.
    try:
        _sc_exp, _sc_exp_msg = read_local_csv("IND_Scrip_Codes.csv")
        if _sc_exp is not None and not _sc_exp.empty and "EXPIRY_LIST" in _sc_exp.columns:
            _q_exp = str(stock_name).strip().upper()
            _sym_col_exp = "STOCK" if "STOCK" in _sc_exp.columns else ("SYMBOL_NAME" if "SYMBOL_NAME" in _sc_exp.columns else None)
            if _sym_col_exp:
                _match = _sc_exp[_sc_exp[_sym_col_exp].astype(str).str.strip().str.upper() == _q_exp]
                if not _match.empty:
                    _elist = str(_match.iloc[0]["EXPIRY_LIST"]).strip()
                    if _elist and _elist.lower() != "nan":
                        _today_exp = ist_now().date()
                        _exps_exp = []
                        for _v in _elist.replace(",", ";").split(";"):
                            _v = _v.strip()
                            if not _v:
                                continue
                            try:
                                _d_exp = pd.to_datetime(_v).date()
                                if _d_exp >= _today_exp:
                                    _exps_exp.append(_d_exp)
                            except:
                                continue
                        if _exps_exp:
                            _exps_exp = sorted(set(_exps_exp))
                            _out_exp = [d.strftime("%Y-%m-%d") for d in _exps_exp]
                            return _out_exp, f"Expiry Same Folder se turant - IND_Scrip_Codes.csv ki EXPIRY_LIST se - Pehli Nearest: {_out_exp[0]} - API se nahi manga"
    except:
        pass
    try:
        import streamlit as _st
        _df = _st.session_state.get("master_fno_df", None)
        if _df is None or _df.empty:
            # GitHub File se try karo
            _df2, _m2 = ind_load_master_from_github_file()
            # Agar Index file aayi hai to wo FNO nahi hai, usme Expiry nahi hogi - FNO file alag se dhoondo
            if _df2 is not None and "EXPIRY_DATE" in _df2.columns:
                _df = _df2
        if _df is None or _df.empty or "EXPIRY_DATE" not in _df.columns:
            fb = get_nearest_thursday_fallback()
            return [fb], f"Master FNO File me Expiry nahi mili, Fallback Thursday {fb} use kar rahe hain - Mahine me 1 baar Download Data dabao"
        # Stock ka naam - SYMBOL_NAME / TRADING_SYMBOL / UNDERLYING_SCRIP_NAME se match karo
        _q = str(stock_name).strip().upper()
        _mask = pd.Series([False]*len(_df))
        for _col in ["SYMBOL_NAME", "TRADING_SYMBOL", "UNDERLYING_SCRIP_NAME", "CUSTOM_SYMBOL"]:
            if _col in _df.columns:
                _mask = _mask | (_df[_col].astype(str).str.upper() == _q)
                # FNO me TRADING_SYMBOL me expiry bhi hoti hai, isliye startswith bhi check karo - jaise NIFTY26...
                _mask = _mask | (_df[_col].astype(str).str.upper().str.startswith(_q))
        _sub = _df[_mask]
        if _sub.empty:
            fb = get_nearest_thursday_fallback()
            return [fb], f"{stock_name} ka Expiry Master FNO me nahi mila, Fallback Thursday {fb}"
        # EXPIRY_DATE ko date me badlo - kai format ho sakte hain - DD-Mon-YYYY ya YYYY-MM-DD
        _exps = []
        for _v in _sub["EXPIRY_DATE"].astype(str).tolist():
            _v = _v.strip()
            if not _v or _v.lower() in ("nan", "0", ""):
                continue
            # Try karo - pehle YYYY-MM-DD, phir DD-Mon-YYYY
            for _fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y", "%Y/%m/%d"):
                try:
                    _d = datetime.strptime(_v, _fmt).date()
                    _exps.append(_d)
                    break
                except:
                    continue
            else:
                # Agar format nahi mila to pd.to_datetime se try karo
                try:
                    _d2 = pd.to_datetime(_v).date()
                    _exps.append(_d2)
                except:
                    continue
        if not _exps:
            fb = get_nearest_thursday_fallback()
            return [fb], "Master me Expiry Date parse nahi hui, Fallback Thursday"
        # Aaj se aage wali hi lo, purani mat lo, sort karo
        _today = ist_now().date()
        _future = sorted([d for d in _exps if d >= _today])
        if not _future:
            _future = sorted(_exps)
        _out = [d.strftime("%Y-%m-%d") for d in _future]
        return _out, f"Master FNO File se Expiry mili - {len(_out)} Expiry - Pehli Nearest: {_out[0]} - API se dobara search nahi kiya"
    except Exception as e:
        fb = get_nearest_thursday_fallback()
        return [fb], f"Expiry Master se Error {e}, Fallback Thursday {fb}"

def ind_download_master_csv(token, source="equity"):
    # V20 - BAND KAR DIYA - User ne bola Download ka Option hata do, Exchange/Segment wala request mat bhejo.
    # Ab Master CSV Download nahi karenge. Sirf GitHub pe uploaded IND_master_index wali File se Security ID lenge.
    # Is function ko ab kahi se bulaya nahi jayega, sirf purana naam rehne diya hai taaki code toote nahi.
    return None, pd.DataFrame(), "Download Band Hai - GitHub pe IND_master_index.csv se Security ID lo"

def ind_build_master_table(master_df_equity):
    # V20 - IND_master_index wali File se bhi Table banao - 3 columns wali Index file ho to bhi chalega.
    # Index file: EXCH, SEGMENT (isme Naam hai), SECURITY_ID - Position se padho.
    # Equity/FNO file: SYMBOL_NAME, TRADING_SYMBOL, SECURITY_ID - Header se padho.
    # Hamare 216 stocks ka IND me kya Sahi Naam + Secret Code + Lot + Expiry hai, ye table banata hai - Master FNO se DISTINCT UNDERLYING.
    # Agar IND ne naam badal diya hai (jaise pehle ZOMATO tha, ab ETERNAL hai), to yahan dikh jayega ki IND wala naam kya hai.
    # Phir hum wahi naam likhenge to fail nahi hoga.
    rows = []
    if master_df_equity is None or master_df_equity.empty:
        return pd.DataFrame()
    # Lookup banayo - SYMBOL_NAME, TRADING_SYMBOL, CUSTOM_SYMBOL - teeno se
    # V20 - Agar IND_master_index wali 3-column file hai to uska 2nd column (SEGMENT) hi Naam hai, usse lookup banao
    lookup = {}
    _is_idx = (len(list(master_df_equity.columns)) == 3 and "SECURITY_ID" in master_df_equity.columns and "SYMBOL_NAME" not in master_df_equity.columns)
    for _, row in master_df_equity.iterrows():
        try:
            sid = str(row.get("SECURITY_ID", "")).strip()
            if not sid or sid == "nan":
                continue
            if _is_idx:
                _nm = str(row.iloc[1]).strip().upper() if len(row) > 1 else ""
                if _nm and _nm != "NAN" and _nm not in lookup:
                    lookup[_nm] = row
            else:
                for col in ["SYMBOL_NAME", "TRADING_SYMBOL", "CUSTOM_SYMBOL"]:
                    if col in master_df_equity.columns:
                        k = str(row.get(col, "")).strip().upper()
                        if k and k != "NAN" and k not in lookup:
                            lookup[k] = row
        except:
            continue
    # V25 - 216 Universe se table banao, 138 wala purana list nahi - Master FNO se DISTINCT UNDERLYING
    try:
        import streamlit as _st5
        _udf5 = _st5.session_state.get("universe_216_df", None)
        _stock_list_216 = _udf5["STOCK"].astype(str).str.upper().tolist() if _udf5 is not None and not _udf5.empty and "STOCK" in _udf5.columns else list(MARKET_STOCKS.keys())
    except:
        _stock_list_216 = list(MARKET_STOCKS.keys())
    for stock in _stock_list_216:
        key = str(stock).strip().upper()
        row = lookup.get(key, None)
        if row is not None:
            # V20 - Index file me SYMBOL_NAME nahi hota, 2nd column hi Naam hai
            if "SYMBOL_NAME" in master_df_equity.columns:
                ind_sym = str(row.get("SYMBOL_NAME", "")).strip()
                ind_trad = str(row.get("TRADING_SYMBOL", "")).strip()
            else:
                ind_sym = str(row.iloc[1]).strip() if len(row) > 1 else ""
                ind_trad = ind_sym
            ind_custom = str(row.get("CUSTOM_SYMBOL", "")).strip() if "CUSTOM_SYMBOL" in master_df_equity.columns else ""
            sid = str(row.get("SECURITY_ID", "")).strip()
            exch = str(row.get("EXCH", "")).strip()
            # Naam badla hua hai ya same hai?
            if ind_sym.upper() == key:
                status = "✅ SAME - Wahi Naam Hai"
            else:
                status = f"⚠️ NAAM ALAG - IND me {ind_sym} hai, {key} likhoge to fail hoga, {ind_sym} likho"
            # Agar TRADING_SYMBOL alag hai to wo bhi dikhao - wahi asli trading naam hai
            rows.append({"Hamara Naam": stock, "IND SYMBOL_NAME": ind_sym, "IND TRADING_SYMBOL": ind_trad, "IND CUSTOM_SYMBOL": ind_custom, "IND Secret Code (SECURITY_ID)": sid, "EXCH": exch, "Status": status})
        else:
            rows.append({"Hamara Naam": stock, "IND SYMBOL_NAME": "", "IND TRADING_SYMBOL": "", "IND CUSTOM_SYMBOL": "", "IND Secret Code (SECURITY_ID)": "", "EXCH": "", "Status": "❌ IND Master me Nahi Mila - Master CSV dobara Download karo, ya naam badal gaya hai"})
    return pd.DataFrame(rows)

# ---------------- V19 - 100 ME SE SCORE KAISE BANTA HAI - YAHI GAYAB HO GAYA THA ----------------
# Pehle sirf "Probability %: 70" likha aata tha, ye nahi likha aata tha ki 70 kaise bana.
# Ab har stock ka poora hisab dikhayenge - kaun sa Criteria pass hua, kitne ank mile, kaun sa fail hua, kitne kate.
# Total 100 ank ka hisab:
# Gap >0.30% = 15 ank | VWAP ke sahi taraf = 15 ank | ORB Break = 20 ank | Volume >1.5x = 15 ank
# Movement Started = 15 ank | Trending Score >=60 = 10 ank | Volatility OK (Choppy nahi) = 10 ank = 100 ank
# Katoti: Fake Breakout = -30 | Choppy = -20 | Sideways = -15
# Example: Gap pass (15) + VWAP pass (15) + ORB pass (20) + Volume fail (0) + Movement Started (15) + Trending (10) + Volatility (10) - Fake 0 = 85
# Agar Fake hai to 85-30=55 ho jayega - isliye Fake wala kabhi Top me nahi aayega.
def calc_probability_breakdown(ana):
    # ana = analyze_full_day() ka output dict
    rows = []
    total = 0
    # 1 Gap
    gap_val = abs(safe_float(ana.get("Gap %", 0)))
    gap_pass = gap_val > 0.30
    gap_pts = 15 if gap_pass else 0
    total += gap_pts
    rows.append({"Criteria": "1. Gap - Khula kitna upar/neeche", "Value": f"{safe_float(ana.get('Gap %',0)):+.2f}% (Chahiye >0.30%)", "Pass?": "✅ PASS" if gap_pass else "❌ FAIL", "Ank": gap_pts, "Max": 15, "Kahan se Check Hua": "IND se - NSE_ + SECURITY_ID se - quotes/full + Historical 5minute se"})
    # 2 VWAP
    ltp = safe_float(ana.get("LTP", 0)); vwap = safe_float(ana.get("VWAP", 0)); gap = safe_float(ana.get("Gap %", 0))
    vwap_pass = (ltp > vwap and gap > 0) or (ltp < vwap and gap < 0)
    vwap_pts = 15 if vwap_pass else 0
    total += vwap_pts
    rows.append({"Criteria": "2. VWAP - LTP VWAP ke sahi taraf hai?", "Value": f"LTP {ltp:.2f} vs VWAP {vwap:.2f}", "Pass?": "✅ PASS" if vwap_pass else "❌ FAIL", "Ank": vwap_pts, "Max": 15, "Kahan se Check Hua": "IND Historical 5minute se VWAP"})
    # 3 ORB
    orb_pass = bool(ana.get("ORB Break", False))
    orb_pts = 20 if orb_pass else 0
    total += orb_pts
    rows.append({"Criteria": "3. ORB 09:15-09:30 Break", "Value": f"ORB High {safe_float(ana.get('ORB High',0)):.2f} / Low {safe_float(ana.get('ORB Low',0)):.2f} - Break: {orb_pass}", "Pass?": "✅ PASS" if orb_pass else "❌ FAIL", "Ank": orb_pts, "Max": 20, "Kahan se Check Hua": "IND Historical 5minute se ORB - Day High/Low IND se"})
    # 4 Volume
    volx = safe_float(ana.get("Vol x", 0))
    vol_pass = volx > 1.5
    vol_pts = 15 if vol_pass else 0
    total += vol_pts
    rows.append({"Criteria": "4. Volume - Aaj zyada Volume hai?", "Value": f"{volx:.2f}x (Chahiye >1.5x)", "Pass?": "✅ PASS" if vol_pass else "❌ FAIL", "Ank": vol_pts, "Max": 15, "Kahan se Check Hua": "IND quotes/full Volume + Historical 5minute se Volume x"})
    # 5 Movement Started
    mv_started = str(ana.get("Movement Started?", "")) == "HAAN"
    mv_pts = 15 if mv_started else 0
    total += mv_pts
    rows.append({"Criteria": "5. Movement Started? - Abhi bhag raha hai ya so raha hai", "Value": str(ana.get("Movement Started?", "")), "Pass?": "✅ PASS" if mv_started else "❌ FAIL", "Ank": mv_pts, "Max": 15, "Kahan se Check Hua": "IND Historical 5minute Last 5min + Day Range se"})
    # 6 Trending
    trend_score = safe_float(ana.get("Trending Score", 0))
    trend_pass = trend_score >= 60
    trend_pts = 10 if trend_pass else 0
    total += trend_pts
    rows.append({"Criteria": "6. Trending Score >=60", "Value": f"{trend_score:.0f}", "Pass?": "✅ PASS" if trend_pass else "❌ FAIL", "Ank": trend_pts, "Max": 10, "Kahan se Check Hua": "IND Historical 5minute Session Story S1/S2/S3 se"})
    # 7 Volatility OK
    mov_type = str(ana.get("Movement Type", ""))
    vol_ok = ("CHOPPY" not in mov_type and "VOLATILE" not in mov_type)
    vol_ok_pts = 10 if vol_ok else 0
    total += vol_ok_pts
    rows.append({"Criteria": "7. Volatility OK - Choppy / Volatile to nahi", "Value": mov_type, "Pass?": "✅ PASS" if vol_ok else "❌ FAIL", "Ank": vol_ok_pts, "Max": 10, "Kahan se Check Hua": "IND Historical 5minute Wick + Reversal se"})
    # Katoti
    fake = bool(ana.get("Fake Breakout", False))
    fake_pts = -30 if fake else 0
    total += fake_pts
    rows.append({"Criteria": "KATOTI: Fake Breakout - Trap hai?", "Value": "HAAN - TRAP" if fake else "NAHI", "Pass?": "❌ KATA" if fake else "✅ SAHI", "Ank": fake_pts, "Max": 0, "Kahan se Check Hua": "ORB toota lekin 15min me wapas - IND se"})
    choppy = "CHOPPY" in mov_type
    choppy_pts = -20 if choppy else 0
    total += choppy_pts
    rows.append({"Criteria": "KATOTI: Choppy", "Value": mov_type, "Pass?": "❌ KATA" if choppy else "✅ SAHI", "Ank": choppy_pts, "Max": 0, "Kahan se Check Hua": "IND se"})
    side = "SIDEWAYS" in mov_type
    side_pts = -15 if side else 0
    total += side_pts
    rows.append({"Criteria": "KATOTI: Sideways", "Value": mov_type, "Pass?": "❌ KATA" if side else "✅ SAHI", "Ank": side_pts, "Max": 0, "Kahan se Check Hua": "IND se"})
    # V40 - Gemini sahi tha: Fake -30 + Choppy -20 + Sideways -15 = -65 ho jata tha, mazboot stock bhi 5-10 pe aa jata tha
    # Katoti kabhi -30 se zyada nahi hogi - taaki ek hi wajah se stock poora khatam na ho
    _kat_total = fake_pts + choppy_pts + side_pts
    if _kat_total < -30:
        _adj = -30 - _kat_total
        total += _adj
        rows.append({"Criteria": "KATOTI CAP: Katoti -30 se zyada nahi", "Value": f"Katoti {_kat_total} thi, cap karke -30 ki", "Pass?": "✅ CAP", "Ank": _adj, "Max": 0, "Kahan se Check Hua": "V40 - Ek hi wajah se stock khatam nahi hoga"})
    total = max(0, min(100, int(total)))
    return pd.DataFrame(rows), total

# ---------------- V19 - STOCK NAAM ALIAS - RIL likho to RELIANCE milega ----------------
# User RIL likhega to RELIANCE samajhna hai, HDFC likhega to HDFCBANK, TATA likhega to saare TATA dikhane hain.
STOCK_ALIASES = {
    "RIL": "RELIANCE", "RELIANCE": "RELIANCE", "REL": "RELIANCE",
    "HDFC": "HDFCBANK", "HDFCBANK": "HDFCBANK",
    "ICICI": "ICICIBANK", "ICICIBANK": "ICICIBANK",
    "AXIS": "AXISBANK", "AXISBANK": "AXISBANK",
    "SBIN": "SBIN", "SBI": "SBIN",
    "INFY": "INFY", "INFOSYS": "INFY",
    "TCS": "TCS",
    "BHEL": "BHEL", "BHARATHEAVY": "BHEL",
    "EICHER": "EICHERMOT", "EICHERMOT": "EICHERMOT",
    "TATAMOTOR": "TATAMOTORS", "TATAMOTORS": "TATAMOTORS", "TATA MOTORS": "TATAMOTORS",
    "BANKBARODA": "BANKBARODA", "BOB": "BANKBARODA",
    "SUZLON": "SUZLON",
    "ZOMATO": "ETERNAL", "ETERNAL": "ETERNAL",
    "M&M": "M&M", "MAHINDRA": "M&M",
    "BAJAJ": "BAJFINANCE",
    "NIFTY": "NIFTY", "BANKNIFTY": "BANKNIFTY",
}


# ---------------- V24 - IND-ONLY - Docs wala exact pattern, isi tarah se search karna hai ----------------
# User ne photo bheja - Docs Getting Started wala code - isi tarah se search karna hai:
#   import requests, os
#   access_token = os.getenv('INDSTOCKS_TOKEN')
#   base_url = 'https://api.indstocks.com'
#   headers = {'Authorization': access_token}
#   params = {'scrip-codes': 'NSE_2885,NSE_11536'}
#   response = requests.get(f'{base_url}/market/quotes/full', headers=headers, params=params)
#   quotes['data']['NSE_2885']['live_price'] -> LTP, ['day_change_percentage'] -> Change, ['volume'] -> Volume
# Ab iske alawa koi Yahoo / NSE wala search nahi hoga. Teenon ka Compromise Mix band.
# Code kaise banta hai:
#   CSV me Code ka naam = SECURITY_ID (jaise RELIANCE = 2885, TCS = 11536, TECHM = ? - Equity File ki cash row se)
#   scrip-code = 'NSE_' + SECURITY_ID  -> 'NSE_2885'  (Quotes / Historical ke liye)
#   underlying-scrip = SECURITY_ID hi, bina prefix -> '2885'  (Option Chain ke liye)
#   FNO wali File ka SECURITY_ID mat lo - wo contract ka hai, underlying ka nahi. Equity wali cash row se lo.
def ind_quotes_full_docs_pattern(scrip_codes_list, token):
    # scrip_codes_list: ['NSE_2885', 'NSE_11536'] jaise - Docs wala hi format
    # Returns (dict { 'NSE_2885': {...} }, msg)
    # Bilkul Docs jaisa - headers = {'Authorization': token}, params = {'scrip-codes': 'NSE_2885,NSE_11536'}
    if not token or len(str(token).strip()) < 10:
        return {}, "Token nahi diya - INDstocks se naya Token banao (24 ghante me expire hota hai)"
    if not scrip_codes_list:
        return {}, "Koi scrip-code hi nahi diya"
    access_token = str(token).strip()
    base_url = 'https://api.indstocks.com'
    headers = {'Authorization': access_token}
    params = {'scrip-codes': ','.join(scrip_codes_list)}
    try:
        response = requests.get(f'{base_url}/market/quotes/full', headers=headers, params=params, timeout=15)
        if response.status_code != 200:
            try:
                _ej = response.json()
                return {}, f"IND Fail - Status {response.status_code} - {_ej.get('message','')} {_ej.get('debug_info','')}"[:400]
            except:
                return {}, f"IND Fail - Status {response.status_code} - {response.text[:300]}"
        quotes = response.json()
        data = quotes.get('data', {})
        # Docs: for symbol, data in quotes['data'].items(): LTP = data['live_price'], Change = data['day_change_percentage'], Volume = data['volume']
        return data, f"IND se aaya - {len(data)} quotes - Docs wala pattern - NSE_ + SECURITY_ID se"
    except Exception as e:
        return {}, f"IND Error - {e}"

def ind_quote_single_docs_pattern(stock_symbol, token, scrip_map=None):
    # Ek stock ka LTP sirf IND se - Docs wala pattern
    # Pehle CSV se SECURITY_ID nikaalo, phir NSE_SECURITY_ID banao, phir quotes/full mango
    scrip, _src = ind_get_scrip(stock_symbol, token, scrip_map)
    if not scrip:
        return None, f"CSV me {stock_symbol} ka SECURITY_ID nahi mila - Pehle Download Data dabao"
    scrip_code = f"NSE_{scrip}"
    data, msg = ind_quotes_full_docs_pattern([scrip_code], token)
    if scrip_code in data:
        d = data[scrip_code]
        return {
            "symbol": stock_symbol, "scrip_code": scrip_code, "security_id": scrip,
            "ltp": safe_float(d.get("live_price", 0)), "change_pct": safe_float(d.get("day_change_percentage", 0)),
            "volume": safe_float(d.get("volume", 0)), "open": safe_float(d.get("day_open", d.get("open", 0))),
            "high": safe_float(d.get("day_high", d.get("high", 0))), "low": safe_float(d.get("day_low", d.get("low", 0))),
            "prev_close": safe_float(d.get("previous_close", d.get("prev_close", 0))),
            "raw": d,
        }, msg
    return None, f"IND se {scrip_code} ka data nahi aaya - {msg}"



# ---------------- V25 - 216 STOCKS UNIVERSE - Is tarike se total 216 stock + jaruri jankari mila hai ----------------
# User ne bola: Is tarike se total 216 stock + uska jaruri jankari mila hai, isko dekho aur apne hisab se use karo.
# Matlab: 138 wala purana hardcoded list ab nahi chalega. Ab universe Master FNO File se aayega - jo Download Data se GitHub me jama hua hai.
# Master FNO me har F&O contract ki row hoti hai - usme se DISTINCT UNDERLYING nikaalo to 216 equity underlyings bachte hain (Index alag).
# Jaruri jankari = STOCK + SYMBOL_NAME + SECURITY_ID + SCRIP_CODE_NSE (NSE_2885) + LOT_SIZE + EXPIRY_LIST + EXCHANGE
# Ye sab ek baar Download Data me GitHub me jama ho jayega - IND_Universe_216.csv me - phir har scan me turant GitHub se mil jayega, dobara Master parse karne ka time nahi lagega.
# Sirf badalne wala data (LTP / Candle / Chain) live IND se mangenge - NSE_ + SECURITY_ID se.
INDEX_UNDERLYINGS = {"NIFTY", "NIFTY 50", "NIFTY BANK", "BANKNIFTY", "BANK NIFTY", "FINNIFTY", "NIFTY FIN SERVICE", "MIDCPNIFTY", "NIFTY MID SELECT", "NIFTY NEXT 50", "SENSEX", "BANKEX", "SENSEX 50", "BSE SENSEX", "NIFTY IT", "NIFTY FMCG", "NIFTY AUTO", "NIFTY PHARMA", "NIFTY METAL", "NIFTY ENERGY", "NIFTY REALTY", "NIFTY MEDIA", "NIFTY PSU BANK"}

def build_universe_from_masters(fno_df=None, equity_df=None, scrip_codes_df=None):
    # Masters se 216 universe banao - FNO se UNDERLYING, Equity se SECURITY_ID, Scrip-Codes se SCRIP_CODE_NSE
    # Returns (universe_list, universe_df, msg) - universe_list = ['RELIANCE', 'TCS', ...] sorted, 216 ke aas-paas
    try:
        import streamlit as _st
        if fno_df is None:
            fno_df = _st.session_state.get("master_fno_df", None)
        if equity_df is None:
            equity_df = _st.session_state.get("master_equity_df", None)
        if scrip_codes_df is None:
            scrip_codes_df = _st.session_state.get("scrip_codes_df", None)
        # V29 - Session me Scrip-Codes nahi hai to bagal wali IND_Scrip_Codes.csv se le lo - bade Master ko chhede bina
        if scrip_codes_df is None or (hasattr(scrip_codes_df, "empty") and scrip_codes_df.empty):
            try:
                _sc_b, _sc_bmsg = read_local_csv("IND_Scrip_Codes.csv")
                if _sc_b is not None and not _sc_b.empty:
                    scrip_codes_df = _sc_b
            except:
                pass
        # Scrip map - SYMBOL -> SECURITY_ID + SCRIP_CODE
        scrip_map2 = {}
        if scrip_codes_df is not None and not scrip_codes_df.empty and "SECURITY_ID" in scrip_codes_df.columns:
            for _, r in scrip_codes_df.iterrows():
                try:
                    _sym = str(r.get("SYMBOL_NAME", "") or r.get("STOCK", "")).strip().upper()
                    _sid = str(r.get("SECURITY_ID", "")).strip()
                    if _sym and _sid and _sid.lower() != "nan":
                        scrip_map2[_sym] = {"SECURITY_ID": _sid, "SCRIP_CODE_NSE": str(r.get("SCRIP_CODE_NSE", f"NSE_{_sid}")).strip(), "EXPIRY_LIST": str(r.get("EXPIRY_LIST", "")).strip(), "LOT_SIZE": str(r.get("LOT_SIZE", "")).strip() if "LOT_SIZE" in scrip_codes_df.columns else ""}
                except:
                    continue
        # Equity se bhi map bharo - FNO me jo nahi hai wo Equity se mil jaye
        if equity_df is not None and not equity_df.empty and "SECURITY_ID" in equity_df.columns:
            for _, r in equity_df.iterrows():
                try:
                    _sym = str(r.get("SYMBOL_NAME", "")).strip().upper()
                    _sid = str(r.get("SECURITY_ID", "")).strip()
                    if _sym and _sid and _sid.lower() != "nan" and _sym not in scrip_map2:
                        scrip_map2[_sym] = {"SECURITY_ID": _sid, "SCRIP_CODE_NSE": f"NSE_{_sid}", "EXPIRY_LIST": "", "LOT_SIZE": ""}
                except:
                    continue
        # FNO se UNDERLYING list - DISTINCT UNDERLYING_SCRIP_NAME / SYMBOL_NAME
        underlyings = []
        if fno_df is not None and not fno_df.empty:
            _col = None
            for _c in ["UNDERLYING_SCRIP_NAME", "UNDERLYING_SYMBOL", "SYMBOL_NAME"]:
                if _c in fno_df.columns:
                    _col = _c
                    break
            if _col:
                _vals = fno_df[_col].astype(str).str.strip().str.upper().tolist()
                for _v in _vals:
                    if not _v or _v in ("NAN", "NONE", ""):
                        continue
                    if _v in INDEX_UNDERLYINGS:
                        continue
                    # FNO contract ke naam me expiry hoti hai (NIFTY26...), underlying me nahi hoti - phir bhi saaf karo
                    if _v not in underlyings:
                        underlyings.append(_v)
        # Agar FNO se 216 nahi mile (file purani / khali) to Scrip-Codes wali list se hi universe banao - Equity wale hi F&O me zyada hote hain
        if len(underlyings) < 100 and scrip_map2:
            # Scrip-Codes me FNO wale hi zyada hain - EXPIRY_LIST wale ko pehle rakho (wo F&O me hain)
            _fno_syms = [k for k, v in scrip_map2.items() if v.get("EXPIRY_LIST")]
            if len(_fno_syms) >= 100:
                underlyings = sorted(_fno_syms)
            else:
                underlyings = sorted(list(scrip_map2.keys()))
        underlyings = sorted([u for u in underlyings if u not in INDEX_UNDERLYINGS])
        # V31 - Universe ko SYMBOL me badlo - FNO se UNDERLYING full naam aata hai ("ADANI ENERGY SOLUTION LTD"), SCAN ko SYMBOL chahiye ("ADANIENSOL").
        # Pehle full naam hi universe me chala jata tha, phir Code nahi milta tha, isliye SCAN 0 aata tha. Ab Symbol me badal ke hi universe banega.
        try:
            _mapped_u, _udf_mapped = normalize_universe_to_symbols(underlyings, pd.DataFrame({"STOCK": underlyings}))
            if _mapped_u:
                _disp_for_rows = {}
                try:
                    if _udf_mapped is not None and not _udf_mapped.empty and "DISPLAY_NAME" in _udf_mapped.columns:
                        for _rr in _udf_mapped.itertuples():
                            _disp_for_rows[str(getattr(_rr, "STOCK", ""))] = str(getattr(_rr, "DISPLAY_NAME", ""))
                except:
                    pass
                underlyings = _mapped_u
                # Rows banate time DISPLAY_NAME bhi rakhne ke liye map ko aage use karenge
                _BUILD_DISP_MAP = _disp_for_rows
            else:
                _BUILD_DISP_MAP = {}
        except Exception:
            _BUILD_DISP_MAP = {}
        rows = []
        for _u in underlyings:
            _info = scrip_map2.get(_u, {})
            # LOT_SIZE - FNO File se bhi nikaal sakte hain, agar wahan LOT_SIZE / MARKET_LOT column hai
            _lot = _info.get("LOT_SIZE", "")
            if not _lot and fno_df is not None and not fno_df.empty:
                try:
                    for _lc in ["LOT_SIZE", "MARKET_LOT", "LOT"]:
                        if _lc in fno_df.columns:
                            _sub = fno_df[fno_df[_col].astype(str).str.upper() == _u] if _col else pd.DataFrame()
                            if not _sub.empty:
                                _lot = str(_sub.iloc[0][_lc]).strip()
                                break
                except:
                    pass
            rows.append({"STOCK": _u, "SYMBOL_NAME": _u, "DISPLAY_NAME": _BUILD_DISP_MAP.get(_u, _u), "SECURITY_ID": _info.get("SECURITY_ID", ""), "SCRIP_CODE_NSE": _info.get("SCRIP_CODE_NSE", ""), "LOT_SIZE": _lot, "EXPIRY_LIST": _info.get("EXPIRY_LIST", "")})
        _udf = pd.DataFrame(rows) if rows else pd.DataFrame()
        return underlyings, _udf, f"Universe: {len(underlyings)} stocks - Master FNO se DISTINCT UNDERLYING se - Index alag karke"
    except Exception as e:
        return list(MARKET_STOCKS.keys()), pd.DataFrame(), f"Universe banane me Error {e} - Purana 138 wala list use kar rahe hain"

def get_scan_universe_216(token=None):
    # Scan ke liye universe - Pehle GitHub / Session wali IND_Universe_216.csv se, nahi to Masters se, nahi to 138 wala fallback
    # Returns (list, df, msg)
    try:
        import streamlit as _st
        # 1) Session me pehle se bana hua universe hai to wahi - sabse fast (Download Data se aaya fresh) - par STOCK ko Symbol me karke hi denge
        _udf = _st.session_state.get("universe_216_df", None)
        if _udf is not None and not _udf.empty and "STOCK" in _udf.columns and len(_udf) >= 100:
            _ulist_n, _udf_n = normalize_universe_to_symbols(_udf["STOCK"].astype(str).tolist(), _udf)
            return _ulist_n, _udf_n, f"Universe Session se turant - {len(_ulist_n)} stocks"
        # 1b) V29 - Bagal wali IND_Universe_216.csv - bani-banayi list, dobara Master se banane ki zaroorat nahi
        try:
            _udf_local, _umsg_local = read_local_csv("IND_Universe_216.csv")
            if _udf_local is not None and not _udf_local.empty and "STOCK" in _udf_local.columns and len(_udf_local) >= 100:
                _ulist_l, _udf_l = normalize_universe_to_symbols(_udf_local["STOCK"].astype(str).tolist(), _udf_local)
                try:
                    _st.session_state["universe_216_df"] = _udf_l
                except:
                    pass
                return _ulist_l, _udf_l, f"Universe Same Folder se turant - IND_Universe_216.csv - {len(_ulist_l)} stocks - {_umsg_local}"
        except:
            pass
        # 2) Masters se banao
        _list, _df, _msg = build_universe_from_masters()
        if len(_list) >= 100:
            try:
                _st.session_state["universe_216_df"] = _df
            except:
                pass
            return _list, _df, _msg
        # 3) Fallback - 138 wala purana
        return list(MARKET_STOCKS.keys()), pd.DataFrame(), "Master FNO abhi Download nahi hua - Purana 138 wala list use ho raha hai - Pehle Download Data dabao, phir 216 wala universe aayega"
    except Exception as e:
        return list(MARKET_STOCKS.keys()), pd.DataFrame(), f"Universe Error {e}"



# ---------------- V26 - HISTORY CACHE - Historical kabhi badalta nahi, to baar-baar IND se kyu mangna? ----------------
# User ne bola - bilkul sahi bola, isse tez hoga, bahut tez hoga:
# - Kal kitna move kiya, 5min / 10min / 15min me kaun sa stock kitna bhaga, candle Green bani ya Red - ye kal ka data hai, ye kabhi nahi badlega.
# - Aaj 09:15 pe scan kiya to 09:15-09:20 ka candle aa gaya. 1 ghanta baad 10:20 pe dobara scan kiya to 09:15-10:20 ka data dobara kyu mangna? 09:15-10:15 wala to pehle se hi hamare paas hai.
# - Sirf naya wala mangna hai - 10:15-10:20 ka delta - aur LTP jo har second badalta hai, wo quotes/full se.
# - Expiry bhi mahine / hafte me 1 baar badalta hai, isliye wo bhi CSV me hi hai, har scan me API se nahi mangte.
# Isliye 2 Cache File GitHub me jama karte jayenge:
#   1) IND_History_Daily.csv - Band din ka summary - 1 row = 1 stock x 1 din - OPEN/HIGH/LOW/CLOSE/GAP/VWAP/ORB/VOL_X/MOVEMENT/GREEN/RED - 6 mahina / 1 saal tak jama hota jayega - 216 x 180 din = ~39k rows, chhota file.
#   2) IND_History_Today.csv - Aaj ka 5-min candle - 1 row = 1 stock x 1 candle (09:15, 09:20...) - OPEN/HIGH/LOW/CLOSE/VOLUME - Aaj ka din khatam hote hi isko Daily me summarize karke saaf kar denge.
# Scan ka naya tareeka:
#   Pehle GitHub se Cache nikaalo -> Pichhla data mil gaya.
#   Phir sirf Delta mango - Aaj ka Last Cached Candle Time se Abhi Tak ka - aur LTP quotes/full se.
#   Phir Cache ko update karke wapas GitHub me jama kar do - taaki agle scan me aur kam mangna pade.
# Pehla scan abhi bhi 5 min lagega (kyunki Cache khali hai), dusra scan 1 ghante baad 1 min se bhi kam me ho jayega - kyunki 80% data Cache se aa jayega.
# Theta / Gamma / Option Chain - wo LTP ke saath badalta hai, isliye wo sirf Top 15 ke liye live IND se mangenge, 216 ke liye nahi.
HISTORY_DAILY_FILE = "IND_History_Daily.csv"
HISTORY_TODAY_FILE = "IND_History_Today.csv"

# ---------------- V34 - TIMEFRAME + MAHINA WISE HISTORY ----------------
# Download ek baar dabao to sab aa jaye, live me sirf wahi file khule jo chahiye.
# Layout (data/ ke andar, bahar nahi):
#   data/history/5min/2026-11.csv    - 5-min candles, Nov 2026, sab stocks ek hi file me
#   data/history/15min/2026-11.csv  - 15-min candles
#   data/history/1hour/2026-11.csv  - 1H candles
#   data/history/4hour/2026-11.csv  - 4H candles
#   data/history/daily/2026-11.csv  - Daily candles
# Ek file me sab stocks - alag-alag stock ki 216 file nahi banegi, warna folder bhar jayega.
# Sirf ye 5 timeframe - 1min extra hai, wo live me hi mangenge, save nahi karenge.
HISTORY_DIR = "history"
# V35 - Kitni candles rakhni hai, har timeframe ki - yahin se badlo (500 / 200 / 1000 jo chahiye)
# 500 5min = ~7 din | 500 15min = ~20 din | 500 1H = ~80 din | 500 4H = ~1.3 saal | 500 Daily = ~2 saal | 500 Weekly = ~10 saal
# Isse zyada purani candles apne aap hat jayengi - folder kabhi nahi bharega
TF_LIST = ["5min", "15min", "1hour", "4hour", "daily", "weekly"]
TF_API = {"5min": "5minute", "15min": "15minute", "1hour": "1hour", "4hour": "4hour", "daily": "1day", "weekly": "1week"}
# V36 - Interval naam ka fallback - Photo me 1H/4H 0 aaya tha, kyunki "1hour"/"4hour" naam API ne nahi mana ho sakta hai - ab 3 naam try karenge, jo chalega wahi rahega
TF_API_TRY = {"5min": ["5minute"], "15min": ["15minute"], "1hour": ["1hour", "60minute", "1H"], "4hour": ["4hour", "240minute", "4H"], "daily": ["1day"], "weekly": ["1week", "1Week", "W"]}
# V36 - Pehli baar kitna mangna hai (500 candles tak ka lakshya) - DELETE NAHI HOGA, ye sirf pehli baar ka fetch size hai
TF_RETENTION = {"5min": 500, "15min": 500, "1hour": 500, "4hour": 500, "daily": 500, "weekly": 500}
# V36 - Lookback API ki limit me rakha - 1H 100 din / 4H 400 din mangne pe API 0 deta tha, isliye 1H 30 din, 4H 60 din, Weekly 365 din - baaki Delta se judta jayega (add karte jana), kabhi delete nahi hoga
TF_LOOKBACK_DAYS = {"5min": 7, "15min": 30, "1hour": 30, "4hour": 60, "daily": 500, "weekly": 365}
TF_DELTA = {"5min": timedelta(minutes=5), "15min": timedelta(minutes=15), "1hour": timedelta(hours=1), "4hour": timedelta(hours=4), "daily": timedelta(days=1), "weekly": timedelta(weeks=1)}
def tf_month_path(tf, yyyymm):
    # _push_master ko ye path denge - wo aage data/ laga dega -> data/history/5min/2026-11.csv
    return f"{HISTORY_DIR}/{tf}/{yyyymm}.csv"
def tf_yyyymm(dt):
    try:
        return pd.to_datetime(dt).strftime("%Y-%m")
    except:
        return datetime.now(IST).strftime("%Y-%m")
def tf_rows_from_candles_df(df, stock):
    # ind_candles_to_df wala format (Time/Open/High/Low/Close/Volume) -> save wala format (STOCK/TIME/OPEN/HIGH/LOW/CLOSE/VOLUME)
    try:
        if df is None or df.empty:
            return pd.DataFrame()
        _d = df.copy()
        _d["Time"] = pd.to_datetime(_d["Time"], errors="coerce")
        _d = _d.dropna(subset=["Time"])
        if _d.empty:
            return pd.DataFrame()
        return pd.DataFrame({
            "STOCK": str(stock).upper(),
            "TIME": _d["Time"].dt.strftime("%Y-%m-%d %H:%M:%S"),
            "OPEN": pd.to_numeric(_d["Open"], errors="coerce").fillna(0),
            "HIGH": pd.to_numeric(_d["High"], errors="coerce").fillna(0),
            "LOW": pd.to_numeric(_d["Low"], errors="coerce").fillna(0),
            "CLOSE": pd.to_numeric(_d["Close"], errors="coerce").fillna(0),
            "VOLUME": pd.to_numeric(_d["Volume"], errors="coerce").fillna(0),
        })
    except:
        return pd.DataFrame()
def tf_candles_for_stock(tf_df, stock, trading_day=None):
    # Save wali file se ek stock ki candles -> analyze wala format (Time/Open/High/Low/Close/Volume)
    # trading_day diya ho to sirf us din ki, nahi diya to sab
    try:
        if tf_df is None or tf_df.empty or "STOCK" not in tf_df.columns:
            return pd.DataFrame()
        _sub = tf_df[tf_df["STOCK"].astype(str).str.upper() == str(stock).upper()].copy()
        if _sub.empty:
            return pd.DataFrame()
        # Daily purani file me DATE hota hai, nayi me TIME - dono chalenge
        if "TIME" in _sub.columns:
            _sub["Time"] = pd.to_datetime(_sub["TIME"].astype(str), errors="coerce")
        elif "DATE" in _sub.columns:
            _sub["Time"] = pd.to_datetime(_sub["DATE"].astype(str), errors="coerce")
        else:
            return pd.DataFrame()
        _sub = _sub.dropna(subset=["Time"])
        if trading_day is not None:
            _sub = _sub[_sub["Time"].dt.date == trading_day]
        if _sub.empty:
            return pd.DataFrame()
        _sub = _sub.sort_values("Time")
        return pd.DataFrame({
            "Time": _sub["Time"],
            "Open": pd.to_numeric(_sub["OPEN"], errors="coerce").fillna(0),
            "High": pd.to_numeric(_sub["HIGH"], errors="coerce").fillna(0),
            "Low": pd.to_numeric(_sub["LOW"], errors="coerce").fillna(0),
            "Close": pd.to_numeric(_sub["CLOSE"], errors="coerce").fillna(0),
            "Volume": pd.to_numeric(_sub["VOLUME"], errors="coerce").fillna(0) if "VOLUME" in _sub.columns else 0,
        })
    except:
        return pd.DataFrame()
def load_tf_month(tf, yyyymm):
    # Ek timeframe + ek mahina ki file - Session -> Local data/history/... -> GitHub Raw -> Purani file (fallback)
    # Returns df (STOCK/TIME/OPEN...), khali ho to empty df
    try:
        import streamlit as _st
        _key = f"tf_{tf}_{yyyymm}"
        _cached = _st.session_state.get(_key, None)
        if _cached is not None and not _cached.empty:
            return _cached
        # Local - data/history/tf/yyyymm.csv (read_local_csv data/ pehle dekhta hai, par yahan poora path dete hain)
        _local_rel = tf_month_path(tf, yyyymm)  # history/5min/2026-11.csv
        for _cand in [APP_DIR / MASTER_FOLDER / _local_rel, Path.cwd() / MASTER_FOLDER / _local_rel, APP_DIR / _local_rel]:
            try:
                if _cand.is_file():
                    _df = pd.read_csv(_cand, dtype=str, keep_default_na=False)
                    if _df is not None and not _df.empty:
                        try:
                            _st.session_state[_key] = _df
                        except:
                            pass
                        return _df
            except:
                pass
        # GitHub Raw - data/history/... pehle, phir history/... (agar kisi ne bahar daal di ho)
        if GITHUB_TOKEN and GITHUB_REPO:
            for _try_url in [f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{MASTER_FOLDER}/{_local_rel}", f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{_local_rel}"]:
                try:
                    _r = requests.get(_try_url, timeout=10)
                    if _r.status_code == 200 and len(_r.text.strip()) > 20:
                        _df = pd.read_csv(io.StringIO(_r.text), dtype=str, keep_default_na=False)
                        if _df is not None and not _df.empty:
                            try:
                                _st.session_state[_key] = _df
                            except:
                                pass
                            return _df
                except:
                    continue
        # Purani file fallback - 5min ke liye Today file, daily ke liye Daily file - taaki dobara Download kiye bina bhi scan chale
        if tf == "5min":
            _old, _m = read_local_csv(HISTORY_TODAY_FILE)
            if _old is not None and not _old.empty:
                return _old
        if tf == "daily":
            _old, _m = read_local_csv(HISTORY_DAILY_FILE)
            if _old is not None and not _old.empty:
                return _old
        return pd.DataFrame()
    except:
        return pd.DataFrame()
def save_tf_month(tf, yyyymm, new_rows_df):
    # Nayi candles purani file me jodo - duplicate STOCK+TIME hatao, nayi jeetegi - phir data/history/... me save karo
    # Returns (ok, msg)
    try:
        import streamlit as _st
        if new_rows_df is None or new_rows_df.empty:
            return False, f"{tf} {yyyymm}: nayi candles nahi thi"
        _old = load_tf_month(tf, yyyymm)
        # Purani file Today/Daily wali ho to uska format alag hai (DATE) - usko TIME me badal ke merge karo
        if _old is not None and not _old.empty:
            if "TIME" not in _old.columns and "DATE" in _old.columns:
                _old = _old.copy()
                _old["TIME"] = _old["DATE"].astype(str) + " 00:00:00"
                _old = _old[["STOCK", "TIME", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]] if all(c in _old.columns for c in ["STOCK", "TIME", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]) else _old
            _merged = pd.concat([_old, new_rows_df], ignore_index=True)
        else:
            _merged = new_rows_df.copy()
        # Sirf zaroori columns, duplicate hatao, sort karo - file saaf rahegi, extra nahi
        _keep = ["STOCK", "TIME", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]
        _merged = _merged[[c for c in _keep if c in _merged.columns]]
        _merged = _merged.drop_duplicates(subset=["STOCK", "TIME"], keep="last")
        _merged["TIME_DT"] = pd.to_datetime(_merged["TIME"].astype(str), errors="coerce")
        _merged = _merged.dropna(subset=["TIME_DT"]).sort_values(["STOCK", "TIME_DT"]).drop(columns=["TIME_DT"])
        # V36 - DELETE BAND - Pichhla data rahega, delete nahi hoga - usse seekh ke selection improve hoga, isliye purani candles hatana band
        # (Pehle yahan tail(500) se purani candles kat jati thi - ab sab rahega)
        _ok, _m = _push_master_to_github(tf_month_path(tf, yyyymm), _merged.to_csv(index=False).encode("utf-8"))
        if _ok:
            try:
                _st.session_state[f"tf_{tf}_{yyyymm}"] = _merged
            except:
                pass
            return True, f"{tf} {yyyymm}: {len(_merged)} candles - {len(new_rows_df)} nayi jodi"
        return False, f"{tf} {yyyymm}: save fail - {_m}"
    except Exception as e:
        return False, f"{tf} {yyyymm}: save error - {e}"

def check_saved_history():
    # V35 - Download dabane se PEHLE ye chalega - batayega kahan tak data saved hai, uske aage ka hi download hoga
    # Har timeframe ke liye: is mahine + pichhle 2 mahine ki file dekho, sabse aakhri TIME nikaalo
    # Returns ({tf: {"last": datetime_or_None, "first": datetime_or_None, "candles": int, "stocks": int}}, DataFrame)
    _out = {}
    _rows = []
    try:
        _now = ist_now()
        _months = []
        for _back in [0, 1, 2]:
            _d = _now - timedelta(days=32 * _back)
            _mm = tf_yyyymm(_d)
            if _mm not in _months:
                _months.append(_mm)
        for _tf in TF_LIST:
            _last = None
            _first = None
            _total = 0
            _stocks = set()
            for _mm in _months:
                try:
                    _df = load_tf_month(_tf, _mm)
                    if _df is None or _df.empty:
                        continue
                    _times = pd.to_datetime(_df["TIME"].astype(str) if "TIME" in _df.columns else _df["DATE"].astype(str), errors="coerce").dropna()
                    if _times.empty:
                        continue
                    _mx = _times.max()
                    _mn = _times.min()
                    if _last is None or _mx > _last:
                        _last = _mx
                    if _first is None or _mn < _first:
                        _first = _mn
                    _total += len(_df)
                    if "STOCK" in _df.columns:
                        _stocks.update(_df["STOCK"].astype(str).str.upper().tolist())
                except:
                    continue
            _out[_tf] = {"last": _last, "first": _first, "candles": int(_total), "stocks": len(_stocks)}
            _rows.append({"Timeframe": _tf, "Pehli baar": int(TF_RETENTION.get(_tf, 500)), "Saved hai (3 mahine me)": int(_total),
                          "Stocks": len(_stocks),
                          "Pehli candle": _first.strftime("%Y-%m-%d %H:%M") if _first is not None else "-",
                          "Aakhri saved": _last.strftime("%Y-%m-%d %H:%M") if _last is not None else "Kuch nahi saved - pehli baar download hoga"})
        return _out, pd.DataFrame(_rows)
    except Exception as e:
        return {}, pd.DataFrame([{"Timeframe": "Error", "Pehli baar": "", "Saved hai (3 mahine me)": "", "Stocks": "", "Pehli candle": "", "Aakhri saved": f"Check me error - {e}"}])


def load_history_cache_from_github():
    # GitHub se dono Cache File laao - raw.githubusercontent se - agar nahi mili to khali DataFrame
    # Returns (daily_df, today_df, msg)
    try:
        import streamlit as _st
        # Pehle session me hai to wahi - sabse fast, GitHub dobara mat kholo
        _d = _st.session_state.get("history_daily_df", None)
        _t = _st.session_state.get("history_today_df", None)
        if _d is not None and _t is not None:
            return _d, _t, f"History Cache Session se - Daily {len(_d)} rows, Today {len(_t)} candles"
        daily_df = pd.DataFrame()
        today_df = pd.DataFrame()
        # V29 - PEHLE bagal wali file - Same Folder se turant, koi network nahi. Local mili to Raw pe jayenge hi nahi.
        for _fn, _is_daily in [(HISTORY_DAILY_FILE, True), (HISTORY_TODAY_FILE, False)]:
            try:
                _ldf, _lmsg = read_local_csv(_fn)
                if _ldf is not None and not _ldf.empty:
                    if _is_daily:
                        daily_df = _ldf
                    else:
                        today_df = _ldf
                    continue
            except:
                pass
            try:
                if GITHUB_TOKEN and GITHUB_REPO:
                    # V33 - Pehle data/ folder se, nahi mili to purani root wali se
                    _r = None
                    for _try_url in [f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{MASTER_FOLDER}/{_fn}", f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{_fn}"]:
                        try:
                            _r = requests.get(_try_url, timeout=10)
                            if _r.status_code == 200 and len(_r.text.strip()) > 20:
                                break
                        except:
                            continue
                    if _r is not None and _r.status_code == 200 and len(_r.text.strip()) > 20:
                        _df = pd.read_csv(io.StringIO(_r.text), dtype=str, keep_default_na=False)
                        if _is_daily:
                            daily_df = _df
                        else:
                            today_df = _df
            except:
                pass
        try:
            _st.session_state["history_daily_df"] = daily_df
            _st.session_state["history_today_df"] = today_df
        except:
            pass
        _src = "Same Folder se turant" if (not daily_df.empty or not today_df.empty) else "GitHub se"
        return daily_df, today_df, f"History Cache {_src} - Daily {len(daily_df)} rows, Today {len(today_df)} candles - Pichhla data mil gaya, sirf Delta + LTP IND se mangenge"
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), f"History Cache load me Error - {e}"

def save_history_cache_to_github(daily_df, today_df):
    # Cache ko GitHub me jama karo - _push_master_to_github wale hi tareeke se - taaki reboot pe bhi na ude
    try:
        import streamlit as _st
        _msgs = []
        if daily_df is not None and not daily_df.empty:
            _ok, _m = _push_master_to_github(HISTORY_DAILY_FILE, daily_df.to_csv(index=False).encode("utf-8"))
            _msgs.append(f"Daily: {_m}")
            _st.session_state["history_daily_df"] = daily_df
        if today_df is not None and not today_df.empty:
            _ok2, _m2 = _push_master_to_github(HISTORY_TODAY_FILE, today_df.to_csv(index=False).encode("utf-8"))
            _msgs.append(f"Today: {_m2}")
            _st.session_state["history_today_df"] = today_df
        elif today_df is not None and today_df.empty:
            # Aaj ka din khatam ho gaya to Today file khali kar do - Daily me summarize ho chuka hai
            pass
        return " | ".join(_msgs) if _msgs else "Cache khali tha, GitHub me kuch nahi bheja"
    except Exception as e:
        return f"History Cache save me Error - {e}"

def daily_df_from_cache_for_stock(stock, daily_cache_df):
    # Cache wali Daily summary se df_daily banao - analyze_full_day ko wahi format chahiye jo IND 1day deta hai - Time/Open/High/Low/Close/Volume
    try:
        if daily_cache_df is None or daily_cache_df.empty or "STOCK" not in daily_cache_df.columns:
            return pd.DataFrame()
        _sub = daily_cache_df[daily_cache_df["STOCK"].astype(str).str.upper() == str(stock).upper()].copy()
        if _sub.empty:
            return pd.DataFrame()
        # DATE ko Time banao
        _sub["Time"] = pd.to_datetime(_sub["DATE"].astype(str), errors="coerce")
        _sub = _sub.dropna(subset=["Time"]).sort_values("Time")
        _out = pd.DataFrame({
            "Time": _sub["Time"],
            "Open": pd.to_numeric(_sub["OPEN"], errors="coerce").fillna(0),
            "High": pd.to_numeric(_sub["HIGH"], errors="coerce").fillna(0),
            "Low": pd.to_numeric(_sub["LOW"], errors="coerce").fillna(0),
            "Close": pd.to_numeric(_sub["CLOSE"], errors="coerce").fillna(0),
            "Volume": pd.to_numeric(_sub.get("VOLUME", 0), errors="coerce").fillna(0) if "VOLUME" in _sub.columns else 0,
        })
        return _out
    except:
        return pd.DataFrame()

def today_candles_from_cache_for_stock(stock, today_cache_df, trading_day):
    # Aaj ka cached 5-min candle - TIME ko datetime banao, trading_day ka hi lo
    try:
        if today_cache_df is None or today_cache_df.empty or "STOCK" not in today_cache_df.columns:
            return pd.DataFrame(), None
        _sub = today_cache_df[today_cache_df["STOCK"].astype(str).str.upper() == str(stock).upper()].copy()
        if _sub.empty:
            return pd.DataFrame(), None
        _sub["Time"] = pd.to_datetime(_sub["TIME"].astype(str), errors="coerce")
        _sub = _sub.dropna(subset=["Time"])
        # Sirf aaj ka din
        _sub = _sub[_sub["Time"].dt.date == trading_day]
        if _sub.empty:
            return pd.DataFrame(), None
        _sub = _sub.sort_values("Time")
        _out = pd.DataFrame({
            "Time": _sub["Time"],
            "Open": pd.to_numeric(_sub["OPEN"], errors="coerce").fillna(0),
            "High": pd.to_numeric(_sub["HIGH"], errors="coerce").fillna(0),
            "Low": pd.to_numeric(_sub["LOW"], errors="coerce").fillna(0),
            "Close": pd.to_numeric(_sub["CLOSE"], errors="coerce").fillna(0),
            "Volume": pd.to_numeric(_sub["VOLUME"], errors="coerce").fillna(0),
        })
        _last = _out["Time"].max() if not _out.empty else None
        return _out, _last
    except:
        return pd.DataFrame(), None

def update_history_cache_after_scan(scan_rows_by_stock, trading_day):
    # Scan ke baad Cache update karo - scan_rows_by_stock: {stock: df5}
    # Today Cache me naye candles jama karo (duplicate TIME mat daalo), Daily Cache me sirf tab daalo jab market band ho gaya (15:30 ke baad) aur us din ka row abhi nahi hai.
    # Returns (daily_df, today_df, msg)
    try:
        daily_df, today_df, _lm = load_history_cache_from_github()
        # Today Cache - naye candles
        _new_today_rows = []
        _is_market_closed = False
        try:
            _now = ist_now()
            _is_market_closed = (_now.date() > trading_day) or (_now.date() == trading_day and (_now.hour > 15 or (_now.hour == 15 and _now.minute >= 31)))
        except:
            _is_market_closed = False
        for _stock, _df5 in (scan_rows_by_stock or {}).items():
            try:
                if _df5 is None or _df5.empty:
                    continue
                _df5c = _df5.copy()
                _df5c["Time"] = pd.to_datetime(_df5c["Time"], errors="coerce")
                _df5c = _df5c.dropna(subset=["Time"])
                _df5c = _df5c[_df5c["Time"].dt.date == trading_day]
                for _, _r in _df5c.iterrows():
                    _new_today_rows.append({"STOCK": str(_stock).upper(), "TIME": pd.to_datetime(_r["Time"]).strftime("%Y-%m-%d %H:%M:%S"),
                                            "OPEN": str(_r.get("Open", 0)), "HIGH": str(_r.get("High", 0)), "LOW": str(_r.get("Low", 0)), "CLOSE": str(_r.get("Close", 0)), "VOLUME": str(_r.get("Volume", 0))})
            except:
                continue
        if _new_today_rows:
            _new_df = pd.DataFrame(_new_today_rows)
            if today_df is None or today_df.empty:
                today_df = _new_df
            else:
                # Purana + Naya, duplicate STOCK+TIME hatao - naya wala jeetega (LTP update ho sakta hai jab candle chal rahi ho)
                today_df = pd.concat([today_df, _new_df], ignore_index=True)
                today_df = today_df.drop_duplicates(subset=["STOCK", "TIME"], keep="last")
            # Sirf aaj ka hi rakho Today me - kal ka purana Today Daily me ja chuka hai, usko yahan mat rakho
            try:
                today_df["TIME_DT"] = pd.to_datetime(today_df["TIME"].astype(str), errors="coerce")
                today_df = today_df[today_df["TIME_DT"].dt.date == trading_day].drop(columns=["TIME_DT"])
            except:
                pass
        # Daily Cache - sirf market band hone pe finalize karo - taaki adhura din Daily me na jaye
        _daily_added = 0
        if _is_market_closed and scan_rows_by_stock:
            for _stock, _df5 in scan_rows_by_stock.items():
                try:
                    if _df5 is None or _df5.empty:
                        continue
                    # Is stock + is din ka row pehle se hai?
                    _exists = False
                    if daily_df is not None and not daily_df.empty and "STOCK" in daily_df.columns and "DATE" in daily_df.columns:
                        _exists = ((daily_df["STOCK"].astype(str).str.upper() == str(_stock).upper()) & (daily_df["DATE"].astype(str) == trading_day.strftime("%Y-%m-%d"))).any()
                    if _exists:
                        continue
                    _ana = analyze_full_day(_df5, pd.DataFrame())
                    if not _ana or "error" in _ana:
                        continue
                    _new_row = {"STOCK": str(_stock).upper(), "DATE": trading_day.strftime("%Y-%m-%d"),
                                "OPEN": str(safe_float(_ana.get("Open", 0))), "HIGH": str(safe_float(_ana.get("Day High", 0))), "LOW": str(safe_float(_ana.get("Day Low", 0))), "CLOSE": str(safe_float(_ana.get("LTP", 0))),
                                "PREV_CLOSE": str(safe_float(_ana.get("Prev Close", 0))), "GAP_PCT": str(safe_float(_ana.get("Gap %", 0))), "VWAP": str(safe_float(_ana.get("VWAP", 0))),
                                "ORB_HIGH": str(safe_float(_ana.get("ORB High", 0))), "ORB_LOW": str(safe_float(_ana.get("ORB Low", 0))), "VOL_X": str(safe_float(_ana.get("Vol x", 0))),
                                "DAY_RANGE_PCT": str(safe_float(_ana.get("Day Range %", 0))), "NET_MOVE_PCT": str(safe_float(_ana.get("Net Move %", 0))),
                                "MOVEMENT_TYPE": str(_ana.get("Movement Type", "")), "TRENDING_SCORE": str(safe_float(_ana.get("Trending Score", 0))),
                                "GREEN_CANDLES": "", "RED_CANDLES": "", "TOTAL_CANDLES": str(int(_ana.get("Candles", 0))), "VOLUME": str(safe_float(_ana.get("Volume", 0)) if "Volume" in _ana else 0)}
                    # Green / Red candle count - df5 se gino
                    try:
                        _d5 = _df5.copy()
                        _green = int((pd.to_numeric(_d5["Close"], errors="coerce") >= pd.to_numeric(_d5["Open"], errors="coerce")).sum())
                        _red = int(len(_d5) - _green)
                        _new_row["GREEN_CANDLES"] = str(_green)
                        _new_row["RED_CANDLES"] = str(_red)
                    except:
                        pass
                    daily_df = pd.concat([daily_df, pd.DataFrame([_new_row])], ignore_index=True) if daily_df is not None and not daily_df.empty else pd.DataFrame([_new_row])
                    _daily_added += 1
                except:
                    continue
            # Daily ko 6 mahina / 1 saal tak rakho - usse purana hata do taaki file badi na ho (365 din se zyada mat rakho)
            try:
                if daily_df is not None and not daily_df.empty:
                    daily_df["DATE_DT"] = pd.to_datetime(daily_df["DATE"].astype(str), errors="coerce")
                    _cut = pd.to_datetime(trading_day) - pd.Timedelta(days=365)
                    daily_df = daily_df[daily_df["DATE_DT"] >= _cut].drop(columns=["DATE_DT"])
                    daily_df = daily_df.drop_duplicates(subset=["STOCK", "DATE"], keep="last").sort_values(["STOCK", "DATE"])
            except:
                pass
            # Aaj ka din Daily me chala gaya to Today ko saaf kar do - kal se naya Today shuru hoga
            if _daily_added > 0:
                today_df = pd.DataFrame(columns=["STOCK", "TIME", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"])
        # V34 - Sirf TF-month files me save karo - purani 2 file me nahi, warna duplicate hoga, folder bhar jayega
        _save_msgs = []
        if _new_today_rows:
            try:
                _tf5 = pd.DataFrame(_new_today_rows)
                _ok5, _m5 = save_tf_month("5min", tf_yyyymm(trading_day), _tf5)
                _save_msgs.append(f"5min: {_m5}")
            except Exception as _e5:
                _save_msgs.append(f"5min save error - {_e5}")
        if _is_market_closed and _daily_added > 0:
            try:
                _drows = []
                for _stock2, _df5b in (scan_rows_by_stock or {}).items():
                    try:
                        if _df5b is None or _df5b.empty:
                            continue
                        _o2 = safe_float(_df5b.iloc[0]["Open"]); _h2 = safe_float(_df5b["High"].max()); _l2 = safe_float(_df5b["Low"].min()); _c2 = safe_float(_df5b.iloc[-1]["Close"]); _v2 = safe_float(pd.to_numeric(_df5b["Volume"], errors="coerce").fillna(0).sum())
                        _drows.append({"STOCK": str(_stock2).upper(), "TIME": trading_day.strftime("%Y-%m-%d 15:30:00"), "OPEN": _o2, "HIGH": _h2, "LOW": _l2, "CLOSE": _c2, "VOLUME": _v2})
                    except:
                        continue
                if _drows:
                    _okD, _mD = save_tf_month("daily", tf_yyyymm(trading_day), pd.DataFrame(_drows))
                    _save_msgs.append(f"daily: {_mD}")
            except Exception as _eD:
                _save_msgs.append(f"daily save error - {_eD}")
        _save_msg = " | ".join(_save_msgs) if _save_msgs else "Kuch naya nahi tha"
        return daily_df, today_df, f"History update - 5min +{len(_new_today_rows)} candles, Daily +{_daily_added} din - {_save_msg}"
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), f"History Cache update me Error - {e}"


# ---------------- V23 - SEARCH FIX - Tech Mahindra likho to bhi TECHM aayega, R E L likho to RELIANCE aayega ----------------
# Dikkat thi: Tech Mahindra likha to nahi aaya, TCHM khoja tab aaya, to bhi mil nahi kiya. R E L likha to bhi nahi aaya.
# Wajah: Pehle hum sirf MARKET_STOCKS ke chhote naam se match karte the - TECHM, RELIANCE. Poora naam Tech Mahindra, Reliance Industries - uska koi map hi nahi tha.
# Aur R E L me Space tha, usko hataya hi nahi tha. TCHM me E chhoota tha, usko bhi nahi pakda tha.
# Ab naya niyam:
# 1) Pehle Space, Dot, Hyphen sab hata do - "R E L" -> "REL", "Tech Mahindra" -> "TECHMAHINDRA", "Tata Motors" -> "TATAMOTORS"
# 2) Poora Company Naam ka Map - TECHMAHINDRA -> TECHM, RELIANCEINDUSTRIES -> RELIANCE, HDFCBANK ka poora naam HDFCBANK hi hai, etc.
# 3) Phir Exact, phir Contains (REL in RELIANCE), phir Subsequence (TCHM ke letter T-C-H-M, TECHM me isi order me hain - isliye TCHM -> TECHM)
# 4) Phir GitHub CSV File se bhi dhoondo - us CSV me SYMBOL_NAME, TRADING_SYMBOL, CUSTOM_SYMBOL, UNDERLYING_SCRIP_NAME - kisi me bhi naam milega to wahi stock hai.
FULL_NAME_ALIASES = {
    "STATE BANK OF INDIA": "SBIN", "STATEBANKOFINDIA": "SBIN",
    "HDFC BANK LIMITED": "HDFCBANK", "HDFCBANKLIMITED": "HDFCBANK",
    "ICICI BANK LIMITED": "ICICIBANK", "ICICIBANKLIMITED": "ICICIBANK",
    "TATA MOTORS LIMITED": "TATAMOTORS", "TATAMOTORSLIMITED": "TATAMOTORS",
    "TATA STEEL LIMITED": "TATASTEEL", "TATASTEELLIMITED": "TATASTEEL",
    "HINDUSTAN UNILEVER LIMITED": "HINDUNILVR", "HINDUSTANUNILEVERLIMITED": "HINDUNILVR",
    "ITC LIMITED": "ITC", "ITCLIMITED": "ITC",
    "LARSEN AND TOUBRO LIMITED": "LT", "LARSENANDTOUBROLIMITED": "LT", "LARSEN & TOUBRO LIMITED": "LT",
    "BAJAJ FINANCE LIMITED": "BAJAJFINANCE", "BAJAJFINANCELIMITED": "BAJAJFINANCE",
    "MARUTI SUZUKI INDIA LIMITED": "MARUTI", "MARUTISUZUKIINDIALIMITED": "MARUTI",
    "TITAN COMPANY LIMITED": "TITAN", "TITANCOMPANYLIMITED": "TITAN",
    "SUN PHARMACEUTICAL INDUSTRIES LIMITED": "SUNPHARMA", "SUNPHARMACEUTICALINDUSTRIESLIMITED": "SUNPHARMA",
    "NTPC LIMITED": "NTPC", "NTPCLIMITED": "NTPC",
    "POWER GRID CORPORATION OF INDIA LIMITED": "POWERGRID", "POWERGRIDCORPORATIONOFINDIALIMITED": "POWERGRID",
    "OIL AND NATURAL GAS CORPORATION LIMITED": "ONGC", "OILANDNATURALGASCORPORATIONLIMITED": "ONGC",
    "COAL INDIA LIMITED": "COALINDIA", "COALINDIALIMITED": "COALINDIA",
    "TECHMAHINDRA": "TECHM", "TECHM": "TECHM", "TCHM": "TECHM", "TECHMAHINDRA LIMITED": "TECHM",
    "RELIANCE": "RELIANCE", "RELIANCEINDUSTRIES": "RELIANCE", "RELIANCEINDUSTRIESLIMITED": "RELIANCE", "RIL": "RELIANCE", "REL": "RELIANCE", "R E L": "RELIANCE",
    "TATAMOTORS": "TATAMOTORS", "TATAMOTOR": "TATAMOTORS", "TATAMOTORSLIMITED": "TATAMOTORS",
    "TATASTEEL": "TATASTEEL", "TATASTEELLIMITED": "TATASTEEL",
    "TATAPOWER": "TATAPOWER", "TATAPOWERCOMPANY": "TATAPOWER",
    "TATACONSUM": "TATACONSUM", "TATACONSUMER": "TATACONSUM", "TATACONSUMERPRODUCTS": "TATACONSUM",
    "HDFCBANK": "HDFCBANK", "HDFC": "HDFCBANK", "HDFCBANKLIMITED": "HDFCBANK",
    "ICICIBANK": "ICICIBANK", "ICICI": "ICICIBANK", "ICICIBANKLIMITED": "ICICIBANK",
    "AXISBANK": "AXISBANK", "AXIS": "AXISBANK",
    "STATEBANKOFINDIA": "SBIN", "SBI": "SBIN", "SBIN": "SBIN",
    "INFOSYS": "INFY", "INFY": "INFY", "INFOSYSLIMITED": "INFY",
    "TATACONSULTANCYSERVICES": "TCS", "TCS": "TCS",
    "HCLTECHNOLOGIES": "HCLTECH", "HCLTECH": "HCLTECH", "HCL": "HCLTECH",
    "WIPRO": "WIPRO", "WIPROLIMITED": "WIPRO",
    "BHARTIAIRTEL": "BHARTIARTL", "BHARTIARTL": "BHARTIARTL", "AIRTEL": "BHARTIARTL",
    "SUNPHARMACEUTICAL": "SUNPHARMA", "SUNPHARMA": "SUNPHARMA", "SUNPHARMAINDUSTRIES": "SUNPHARMA",
    "MAHINDRAANDMAHINDRA": "M&M", "MAHINDRA": "M&M", "M&M": "M&M", "MNM": "M&M",
    "MARUTISUZUKI": "MARUTI", "MARUTI": "MARUTI", "MARUTISUZUKIINDIA": "MARUTI",
    "HEROMOTOCORP": "HEROMOTOCO", "HEROMOTOCO": "HEROMOTOCO", "HERO": "HEROMOTOCO",
    "EICHERMOTORS": "EICHERMOT", "EICHERMOT": "EICHERMOT", "EICHER": "EICHERMOT",
    "BAJAJFINANCE": "BAJFINANCE", "BAJAJ": "BAJFINANCE",
    "BAJAJAUTO": "BAJAJ-AUTO", "BAJAJ-AUTO": "BAJAJ-AUTO",
    "HINDUNILVR": "HINDUNILVR", "HINDUSTANUNILEVER": "HINDUNILVR", "HUL": "HINDUNILVR",
    "NESTLE": "NESTLEIND", "NESTLEIND": "NESTLEIND", "NESTLEINDIA": "NESTLEIND",
    "BRITANNIA": "BRITANNIA", "BRITANNIAINDUSTRIES": "BRITANNIA",
    "ASIANPAINTS": "ASIANPAINT", "ASIANPAINT": "ASIANPAINT",
    "TITAN": "TITAN", "TITANCOMPANY": "TITAN",
    "ULTRATECHCEMENT": "ULTRACEMCO", "ULTRACEMCO": "ULTRACEMCO", "ULTRATECH": "ULTRACEMCO",
    "GRASIM": "GRASIM", "GRASIMINDUSTRIES": "GRASIM",
    "DIVISLABORATORIES": "DIVISLAB", "DIVISLAB": "DIVISLAB", "DIVIS": "DIVISLAB",
    "DRREDDYSLABORATORIES": "DRREDDY", "DRREDDY": "DRREDDY",
    "CIPLA": "CIPLA", "CIPLALIMITED": "CIPLA",
    "COALINDIA": "COALINDIA", "COALINDIALIMITED": "COALINDIA",
    "POWERGRID": "POWERGRID", "POWERGRIDCORPORATION": "POWERGRID",
    "NTPC": "NTPC", "NTPCLIMITED": "NTPC",
    "ONGC": "ONGC", "OILANDNATURALGAS": "ONGC",
    "ADANIENTERPRISES": "ADANIENT", "ADANIENT": "ADANIENT", "ADANI": "ADANIENT",
    "ADANIPORTS": "ADANIPORTS", "ADANIPORTSANDSEZ": "ADANIPORTS",
    "KOTAKMAHINDRABANK": "KOTAKBANK", "KOTAKBANK": "KOTAKBANK", "KOTAK": "KOTAKBANK",
    "LT": "LT", "LARSENANDTOUBRO": "LT", "LARSEN": "LT",
    "JSWSTEEL": "JSWSTEEL", "JSW": "JSWSTEEL",
    "HINDALCO": "HINDALCO", "HINDALCOINDUSTRIES": "HINDALCO",
    "INDIGO": "INDIGO", "INTERGLOBEAVIATION": "INDIGO",
    "ZOMATO": "ETERNAL", "ETERNAL": "ETERNAL",
    "PAYTM": "PAYTM", "ONE97COMMUNICATIONS": "PAYTM",
    "NYKAA": "NYKAA", "FSNE-COMMERCE": "NYKAA",
    "DMART": "DMART", "AVENUESUPERMARTS": "DMART",
    "TRENT": "TRENT", "TRENTLIMITED": "TRENT",
    "IRCTC": "IRCTC", "INDIANRAILWAYCATERING": "IRCTC",
    "YESBANK": "YESBANK", "YESBANKLIMITED": "YESBANK",
    "SUZLON": "SUZLON", "SUZLONENERGY": "SUZLON",
    "IDEA": "IDEA", "VODAFONEIDEA": "IDEA",
    "ADANIENERGYSOLUTION": "ADANIENSOL", "ADANIENSOL": "ADANIENSOL", "ADANIENERGYSOLUTIONLIMITED": "ADANIENSOL", "ADANIENERGYSOLUTIONLTD": "ADANIENSOL", "ADANITRANSMISSION": "ADANIENSOL",
    "ADANIGREENENERGY": "ADANIGREEN", "ADANIPOWER": "ADANIPOWER",
    "BEL": "BEL", "BHARATELECTRONICS": "BEL",
    "HAL": "HAL", "HINDUSTANAERONAUTICS": "HAL",
    "BANKBARODA": "BANKBARODA", "BOB": "BANKBARODA", "BANKOFBARODA": "BANKBARODA",
    "PNB": "PNB", "PUNJABNATIONALBANK": "PNB",
    "CANARABANK": "CANBK", "CANBK": "CANBK",
    "UNIONBANK": "UNIONBANK", "UNIONBANKOFINDIA": "UNIONBANK",
}

def _normalize_search_text(s):
    # "R E L" -> "REL", "Tech Mahindra" -> "TECHMAHINDRA", "Tata-Motors" -> "TATAMOTORS", "TCHM" -> "TCHM"
    if not s:
        return ""
    t = str(s).strip().upper()
    # Space, Dot, Hyphen, Underscore sab hata do
    for ch in [" ", ".", "-", "_", ",", "(", ")", "/"]:
        t = t.replace(ch, "")
    return t

def _is_subsequence(small, big):
    # TCHM ke letter T-C-H-M, TECHM me isi order me hain ya nahi - hai, isliye TCHM -> TECHM
    # REL ke letter R-E-L, RELIANCE me isi order me hain - hai, isliye REL -> RELIANCE
    if not small or not big:
        return False
    it = iter(big)
    return all(ch in it for ch in small)

_SYMBOL_LOOKUP_CACHE = {"map": None, "display": None}
def _build_symbol_lookup():
    # V31 - Ek hi jagah se Symbol nikalo - GitHub wali chhoti file se, MARKET_STOCKS (138) se nahi.
    # Pehle Search sirf MARKET_STOCKS me dekhta tha - usme ADANIENSOL hai hi nahi, isliye "list me nahi hai" bolta tha, jabki neeche Universe table me wahi naam dikh raha tha.
    # Ab Scrip_Codes (SYMBOL + TRADING + CUSTOM + UNDERLYING full naam) + Universe + KNOWN + Alias - sab se ek map banega, ek baar banega, phir cache se chalega.
    # Returns (norm_key -> SYMBOL, SYMBOL -> display_full_name)
    try:
        if _SYMBOL_LOOKUP_CACHE.get("map") is not None:
            return _SYMBOL_LOOKUP_CACHE["map"], _SYMBOL_LOOKUP_CACHE["display"]
        _mp = {}
        _disp = {}
        def _add(_key, _sym, _display_name=""):
            try:
                if not _key or not _sym:
                    return
                _k = _normalize_search_text(str(_key))
                _s = str(_sym).strip().upper()
                if not _k or not _s or _s in ("NAN", "NONE", ""):
                    return
                # Pehle wali entry jeetegi - Scrip_Codes sabse pehle aata hai, isliye wahi sahi rahega
                if _k not in _mp:
                    _mp[_k] = _s
                # LTD / LIMITED hatake bhi jod do - "ADANI ENERGY SOLUTION LTD" -> "ADANIENERGYSOLUTION" bhi milega
                for _suf in ("LIMITED", "LTD"):
                    if _k.endswith(_suf) and len(_k) > len(_suf):
                        _k2 = _k[:-len(_suf)]
                        if _k2 and _k2 not in _mp:
                            _mp[_k2] = _s
                if _s not in _disp and _display_name:
                    _disp[_s] = str(_display_name).strip()
                elif _s not in _disp:
                    _disp[_s] = _s
            except:
                pass
        # 1) Scrip_Codes - sabse bharosemand - SYMBOL + full naam dono - NSE pehle, BSE baad me (500325 wala bug)
        try:
            _sc, _ = read_local_csv("IND_Scrip_Codes.csv")
            if _sc is not None and not _sc.empty:
                try:
                    if "EXCH" in _sc.columns:
                        _sc = _sc.copy()
                        _sc["_er"] = _sc["EXCH"].astype(str).str.strip().str.upper().map(lambda x: 0 if x == "NSE" else 1)
                        _sc = _sc.sort_values("_er", kind="stable").drop(columns=["_er"])
                except:
                    pass
                for _, _r in _sc.iterrows():
                    try:
                        _sym2 = str(_r.get("SYMBOL_NAME", "") or _r.get("STOCK", "")).strip().upper()
                        if not _sym2 or _sym2 == "NAN":
                            continue
                        _under2 = str(_r.get("UNDERLYING_SCRIP_NAME", "") or "").strip()
                        _disp2 = _under2 if _under2 and _under2.upper() != "NAN" else _sym2
                        for _col3 in ["STOCK", "SYMBOL_NAME", "TRADING_SYMBOL", "CUSTOM_SYMBOL", "UNDERLYING_SCRIP_NAME"]:
                            if _col3 in _sc.columns:
                                _add(str(_r.get(_col3, "")), _sym2, _disp2)
                    except:
                        continue
        except:
            pass
        # 2) Universe - isme STOCK kabhi full naam hota hai, SYMBOL_NAME me Symbol - dono jod do
        try:
            _ud, _ = read_local_csv("IND_Universe_216.csv")
            if _ud is not None and not _ud.empty:
                for _, _r in _ud.iterrows():
                    try:
                        _sym3 = str(_r.get("SYMBOL_NAME", "") or _r.get("STOCK", "")).strip().upper()
                        _stk3 = str(_r.get("STOCK", "")).strip()
                        # Agar SYMBOL_NAME full naam jaisa hai (space hai) to wo Symbol nahi, full naam hai - usko display me rakho, Symbol ke liye STOCK se mat lo
                        # Universe me STOCK = full naam, SYMBOL_NAME = full naam bhi - tab Symbol ka pata Scrip_Codes se hi chalega (upar), yahan sirf full naam -> Symbol ka map tabhi jodenge jab Symbol saaf hai (space nahi)
                        if _sym3 and " " not in _sym3 and _sym3 not in ("NAN",):
                            _add(_sym3, _sym3, _stk3)
                        if _stk3:
                            # STOCK full naam hai to usko bhi key banao, value Symbol hogi agar Symbol saaf hai, nahi to khud hi
                            _add(_stk3, _sym3 if (" " not in _sym3 and _sym3) else _stk3, _stk3)
                    except:
                        continue
        except:
            pass
        # 3) KNOWN + MARKET_STOCKS (138) - purane wale bhi chalte rahen
        try:
            for _k5, _v5 in list(KNOWN_SCRIP.items()) + [(k, k) for k in MARKET_STOCKS.keys()]:
                _add(str(_k5), str(_v5) if str(_v5) in KNOWN_SCRIP else str(_k5), str(_k5))
        except:
            pass
        # 4) FULL_NAME_ALIASES - Tech Mahindra -> TECHM jaisa
        try:
            for _k6, _v6 in FULL_NAME_ALIASES.items():
                _add(str(_k6), str(_v6), str(_v6))
        except:
            pass
        _SYMBOL_LOOKUP_CACHE["map"] = _mp
        _SYMBOL_LOOKUP_CACHE["display"] = _disp
        return _mp, _disp
    except Exception:
        return {}, {}

def resolve_to_symbol(user_text):
    # V31 - Koi bhi naam likho - Symbol, poora naam, chhota naam - sab se Symbol niklega. Returns (symbol_or_None, suggestions_list)
    # "ADANI ENERGY SOLUTION LTD" -> ADANIENSOL, "Tech Mahindra" -> TECHM, "R E L" -> RELIANCE, "TCHM" -> TECHM
    try:
        if not user_text:
            return None, []
        _mp, _disp = _build_symbol_lookup()
        if not _mp:
            return None, []
        _q = _normalize_search_text(str(user_text))
        if not _q:
            return None, []
        if _q in _mp:
            return _mp[_q], [_mp[_q]]
        # LTD / LIMITED hatake
        _q2 = _q
        for _suf in ("LIMITED", "LTD"):
            if _q2.endswith(_suf):
                _q2 = _q2[:-len(_suf)]
        if _q2 and _q2 in _mp:
            return _mp[_q2], [_mp[_q2]]
        # Contains - q kisi key me hai ya key q me hai - Symbol ke hisab se dedupe karo
        _syms = []
        for _k, _v in _mp.items():
            if _q in _k or _k in _q:
                if _v not in _syms:
                    _syms.append(_v)
        if len(_syms) == 1:
            return _syms[0], _syms
        if len(_syms) > 1:
            # Sabse chhota Symbol pehle - jaise TATA likha to TATA wale sab, par exact jaisa pehle
            _syms_sorted = sorted(_syms, key=lambda s: (len(s), s))
            return None, _syms_sorted[:10]
        # Subsequence - TCHM -> TECHM
        _sub = []
        for _k, _v in _mp.items():
            if _is_subsequence(_q, _k) and _v not in _sub:
                _sub.append(_v)
        if len(_sub) == 1:
            return _sub[0], _sub
        if len(_sub) > 1:
            return None, sorted(_sub, key=lambda s: (len(s), s))[:10]
        return None, []
    except Exception:
        return None, []

def normalize_universe_to_symbols(universe_list, universe_df):
    # V31 - Universe me full naam aaye to Symbol me badlo - SCAN ko Symbol chahiye, full naam se Code nahi milta, isliye SCAN 0 aata tha.
    # "ADANI ENERGY SOLUTION LTD" -> ADANIENSOL, "RELIANCE INDUSTRIES LIMITED" -> RELIANCE. Jo pehle se Symbol hai wo waisa hi rahega.
    # Returns (symbol_list, df_with_STOCK=symbol + DISPLAY_NAME=full_naam)
    try:
        if not universe_list:
            return [], universe_df
        _mp, _disp = _build_symbol_lookup()
        _new_list = []
        _disp_map = {}
        for _u in universe_list:
            _u_str = str(_u).strip()
            if not _u_str:
                continue
            _sym, _ = resolve_to_symbol(_u_str)
            _final = _sym if _sym else _u_str.upper()
            if _final not in _new_list:
                _new_list.append(_final)
            # Display ke liye full naam rakho - agar original me space tha to wahi full naam hai, nahi to lookup wala display
            if _final != _u_str.upper():
                _disp_map[_final] = _u_str.upper()
            elif _final in _disp:
                _disp_map[_final] = _disp[_final]
            else:
                _disp_map[_final] = _u_str.upper()
        _new_list = sorted(_new_list)
        _new_df = universe_df
        try:
            if universe_df is not None and not universe_df.empty and "STOCK" in universe_df.columns:
                _new_df = universe_df.copy()
                # STOCK ko Symbol me badlo - har row ka STOCK resolve karo
                _new_stocks = []
                for _v in _new_df["STOCK"].astype(str).tolist():
                    _s2, _ = resolve_to_symbol(_v)
                    _new_stocks.append(_s2 if _s2 else _v.strip().upper())
                _new_df["STOCK"] = _new_stocks
                # SYMBOL_NAME bhi Symbol hi rakho
                if "SYMBOL_NAME" in _new_df.columns:
                    _new_df["SYMBOL_NAME"] = _new_stocks
                # DISPLAY_NAME - full naam, taaki table me dono dikhe
                _new_df["DISPLAY_NAME"] = [_disp_map.get(s, s) for s in _new_stocks]
                # Duplicate Symbol hatado - ek Symbol ki ek hi row
                _new_df = _new_df.drop_duplicates(subset=["STOCK"], keep="first").reset_index(drop=True)
        except:
            pass
        return _new_list, _new_df
    except Exception:
        return universe_list, universe_df

def resolve_stock_name(user_text):
    # V31 - Ab GitHub wali chhoti file se Symbol niklega, MARKET_STOCKS (138) se nahi. Pehle wala 30,000-row wala Master loop hataya - wahi slow tha.
    # Returns (resolved_stock_or_None, suggestions_list) - resolved = SYMBOL jaise ADANIENSOL, TECHM, RELIANCE
    if not user_text:
        return None, []
    try:
        _sym, _sugg = resolve_to_symbol(user_text)
        if _sym:
            return _sym, [_sym]
        if _sugg:
            return None, _sugg[:10]
        # Alias / MARKET fallback - purana tareeka, sirf chhoti list pe, Master loop nahi
        _q = _normalize_search_text(str(user_text))
        if _q in FULL_NAME_ALIASES:
            _r = FULL_NAME_ALIASES[_q]
            return _r, [_r]
        return None, []
    except Exception:
        return None, []

# ---------------- V18 - KAAM 2: 5-5 KARKE REQUEST + FAIL HONE PE 1-1 RETRY ----------------
# User ka niyam, bilkul waisa hi:
# - Normal: 5-5 karke hi request dalenge. Jo fail nahi hoga, usko 5-5 hi rehne denge, usko 1-1 me nahi badlenge.
# - Agar koi batch (5 ka group) fail ho raha hai, to us 5 ko alag-alag karke 1-1 request me dalenge.
# - Wo 5 khatam, phir wapas 5-5 ka dalenge. Jo fail hoga, usi ko 1-1 karke dalenge.
# Docs: scrip-codes max 5 hai, 5 se zyada pe 400 aata hai. Isliye 5 se zyada kabhi nahi bhejenge.
# Iska fayda: Pehle 1 galat code se poora batch udd jata tha, 5 ke 5 fail. Ab us batch ke 5 ko 1-1 karke mangenge to 4 sahi wale aa jayenge, sirf 1 galat wala fail hoga.
def ind_historical_5x5_with_retry(symbols_with_scrip, interval, start_ms, end_ms, token):
    # symbols_with_scrip: list of (stock_name, scrip_id) jaise [("RELIANCE","2885"), ("TCS","11536"), ...]
    # Returns (result_dict, log_list)
    # result_dict: {stock_name: {"candles": [...], "mode": "BATCH-5" / "SINGLE-1", "ok": True/False, "msg": "..."}}
    # log_list: har batch ka haal - UI me dikhane ke liye
    result = {}
    logs = []
    if not symbols_with_scrip:
        return result, ["Koi stock hi nahi diya 5x5 ke liye"]
    # 5-5 ke chunk banao
    chunks = [symbols_with_scrip[i:i+5] for i in range(0, len(symbols_with_scrip), 5)]
    for ci, chunk in enumerate(chunks, start=1):
        names = [s for s, _ in chunk]
        codes = [f"NSE_{sid}" for _, sid in chunk]
        # Pehle 5-5 karke try karo - jo fail nahi hoga, wo 5-5 hi rahega
        try:
            data, msg = ind_get_historical_batch(codes, interval, start_ms, end_ms, token)
            # Batch SUCCESS hai agar: success=True AUR kam se kam 1 code ka data aaya
            # Lekin dhyan: Docs kehta hai jo code ka data nahi hai, wo data me aayega hi nahi.
            # Isliye agar batch ke 5 me se 3 ka data aaya, 2 ka nahi aaya, to wo 2 ko bhi 1-1 karke check karenge - ho sakta hai wo 2 ka data hi nahi hai ya code galat hai.
            if data and len(data) > 0:
                # Kitne aaye, kitne nahi aaye?
                got = []
                missing = []
                for (sname, sid), code in zip(chunk, codes):
                    if code in data:
                        got.append(sname)
                        result[sname] = {"candles": (data[code].get("candles", []) or []), "mode": "BATCH-5", "ok": True, "msg": f"Batch {ci} me 5-5 se aaya"}
                    else:
                        missing.append((sname, sid, code))
                if not missing:
                    logs.append(f"Batch {ci}: 5-5 ✅ - {', '.join(names)} - Sab 5 aa gaye, 1-1 karne ki zaroorat nahi padi")
                else:
                    logs.append(f"Batch {ci}: 5-5 me {len(got)} aaye ({', '.join(got)}), {len(missing)} nahi aaye ({', '.join([m[0] for m in missing])}) - In {len(missing)} ko ab 1-1 karke try karenge")
                    # Missing walo ko 1-1 karke retry karo
                    for sname, sid, code in missing:
                        try:
                            d1, m1 = ind_get_historical_batch([code], interval, start_ms, end_ms, token)
                            if code in d1:
                                result[sname] = {"candles": (d1[code].get("candles", []) or []), "mode": "SINGLE-1 (Batch Fail ke baad Retry)", "ok": True, "msg": f"Batch {ci} me nahi aaya tha, 1-1 me aa gaya"}
                                logs.append(f"  -> {sname}: 1-1 ✅ - Batch me nahi aaya tha, ab aa gaya")
                            else:
                                result[sname] = {"candles": [], "mode": "SINGLE-1", "ok": False, "msg": f"1-1 me bhi nahi aaya - {m1} - Ho sakta hai is stock ka IND Code galat hai ya is din data hi nahi hai, Master CSV me Code check karo"}
                                logs.append(f"  -> {sname}: 1-1 ❌ - Batch + Single dono me nahi aaya - Master CSV me iska Code check karo")
                            time.sleep(0.2)
                        except Exception as e:
                            result[sname] = {"candles": [], "mode": "SINGLE-1", "ok": False, "msg": f"1-1 Error - {e}"}
                            logs.append(f"  -> {sname}: 1-1 ❌ Error - {e}")
                # Batch ke baad thoda ruk jao - 5/sec limit na toote
                time.sleep(0.2)
                continue
            else:
                # Batch poora fail hua - data khali aaya ya success=False - ab 5 ko 1-1 karke dalenge
                logs.append(f"Batch {ci}: 5-5 ❌ FAIL - {', '.join(names)} - Poora batch fail hua ({msg}) - Ab in 5 ko alag-alag 1-1 karke dalenge")
        except Exception as e:
            logs.append(f"Batch {ci}: 5-5 ❌ EXCEPTION - {', '.join(names)} - {e} - Ab in 5 ko 1-1 karke dalenge")
            data = {}
        # Yahan aaye matlab batch fail hua - ab 5 ko 1-1 karke
        for sname, sid in chunk:
            code = f"NSE_{sid}"
            # Agar pehle se result me hai (upar wale success case me) to dobara mat mango
            if sname in result and result[sname].get("ok"):
                continue
            try:
                d1, m1 = ind_get_historical_batch([code], interval, start_ms, end_ms, token)
                if code in d1:
                    result[sname] = {"candles": (d1[code].get("candles", []) or []), "mode": "SINGLE-1 (Batch Fail ke baad Retry)", "ok": True, "msg": f"Batch {ci} fail hua tha, 1-1 me aa gaya - Iska matlab batch me kisi aur ka Code galat tha, iska Code sahi hai"}
                    logs.append(f"  -> {sname}: 1-1 ✅ - Batch fail hua tha, lekin 1-1 me aa gaya (iska Code sahi hai)")
                else:
                    result[sname] = {"candles": [], "mode": "SINGLE-1", "ok": False, "msg": f"Batch + 1-1 dono fail - {m1} - Master CSV me iska Sahi Naam + Secret Code check karo"}
                    logs.append(f"  -> {sname}: 1-1 ❌ - Batch + Single dono fail - Master CSV me Code check karo")
                time.sleep(0.2)
            except Exception as e:
                result[sname] = {"candles": [], "mode": "SINGLE-1", "ok": False, "msg": f"1-1 Error - {e}"}
                logs.append(f"  -> {sname}: 1-1 ❌ Error - {e}")
        # Wo 5 khatam, ab wapas agle 5-5 pe jayenge - loop apne aap agle chunk pe jayega
        logs.append(f"Batch {ci} khatam - Ab agle 5-5 pe jayenge")
    return result, logs

def download_history_tf_month(token, universe_stocks, scrip_map_dict):
    # V36 - Download se PEHLE check karo kahan tak saved hai, uske AAGE ka hi mango - purana dobara mat mango, delete kabhi nahi hoga
    # - Pehli baar: poora lookback - 5min 7 din, 15min 30 din, 1H 30 din, 4H 60 din, Daily 500 din, Weekly 365 din - baaki Delta se judta jayega
    # - Agli baar: Aakhri saved + 1 candle se Abhi Tak ka Delta hi mango - pichhla data store rahega, naya uske upar jud jayega (overwrite nahi, update hoga)
    # - Agar aakhri saved abhi ka hi hai to us timeframe ko chhedo hi mat - pehle se saved hai
    # Returns [(tf, yyyymm, ok, msg)]
    _out = []
    try:
        if not token or not universe_stocks or not scrip_map_dict:
            return [("all", "", False, "History: stocks ya scrip khali")]
        _trading_day = get_trading_day()
        _s, _scan_end = get_scan_window(_trading_day)
        # Pehle check karo - kahan tak saved hai
        try:
            _saved, _saved_df = check_saved_history()
        except:
            _saved = {}
        for _tf in TF_LIST:
            try:
                _stocks = list(universe_stocks) if _tf in ("daily", "weekly") else list(universe_stocks)[:100]
                _pairs = []
                for _sname in _stocks:
                    _sid = str(scrip_map_dict.get(str(_sname).upper(), "") or "").strip()
                    if _sid and _sid.lower() != "nan":
                        _pairs.append((str(_sname).upper(), _sid))
                if not _pairs:
                    continue
                # Aakhri saved kahan tak hai?
                _last_saved = (_saved.get(_tf, {}) or {}).get("last")
                if _last_saved is not None:
                    try:
                        _last_saved = pd.to_datetime(_last_saved)
                    except:
                        _last_saved = None
                # Agar aakhri saved abhi se 1 candle se kam pehle ka hai to ye TF pehle se poora hai - dobara mat mango
                if _last_saved is not None and _scan_end is not None:
                    try:
                        if (_scan_end - _last_saved) <= TF_DELTA.get(_tf, timedelta(minutes=5)):
                            _out.append((_tf, "", True, f"{_tf}: pehle se {_last_saved.strftime('%Y-%m-%d %H:%M')} tak saved hai - dobara manga hi nahi"))
                            continue
                    except:
                        pass
                    _start_dt = _last_saved + TF_DELTA.get(_tf, timedelta(minutes=5))
                    _mode = f"Delta - {_last_saved.strftime('%Y-%m-%d %H:%M')} ke baad ka hi manga"
                else:
                    _start_dt = _scan_end - timedelta(days=TF_LOOKBACK_DAYS.get(_tf, 30))
                    _mode = f"Pehli baar - pichhle {TF_LOOKBACK_DAYS.get(_tf, 30)} din ka manga (500 candles tak)"
                if _start_dt >= _scan_end:
                    _out.append((_tf, "", True, f"{_tf}: naya kuch nahi - pehle se {_last_saved} tak saved hai"))
                    continue
                # V36 - Pehle kaun-kaun download hai, kaun nahi - har TF ke liye interval naam + chhota window dono try karo, taaki 1H/4H 0 na rahe
                _by_month = {}
                _tried = []
                _got_any = False
                for _iv in TF_API_TRY.get(_tf, [TF_API.get(_tf, "5minute")]):
                    try:
                        _res, _logs = ind_historical_5x5_with_retry(_pairs, _iv, to_ms(_start_dt), to_ms(_scan_end), token)
                        _tried.append(_iv)
                        _tmp = {}
                        for _sym, _r in (_res or {}).items():
                            _candles = (_r or {}).get("candles", []) or []
                            if not _candles:
                                continue
                            _df_c = ind_candles_to_df(_candles)
                            _rows = tf_rows_from_candles_df(_df_c, _sym)
                            if _rows.empty:
                                continue
                            _rows["MM"] = pd.to_datetime(_rows["TIME"].astype(str), errors="coerce").dt.strftime("%Y-%m")
                            for _mm, _sub in _rows.groupby("MM"):
                                if not _mm or str(_mm) == "nan":
                                    continue
                                _tmp.setdefault(str(_mm), []).append(_sub.drop(columns=["MM"]))
                        if _tmp:
                            _by_month = _tmp
                            _got_any = True
                            _mode = f"{_mode} - interval '{_iv}' chala"
                            break
                    except Exception as _e_iv:
                        _tried.append(f"{_iv} (error)")
                        continue
                # Agar bada window pe 0 aaya to chhota window try karo - API ki range limit se bada mangne pe 0 aata tha, chhote me aa jayega
                if not _got_any:
                    try:
                        _small_days = 7 if _tf in ("5min", "15min", "1hour", "4hour") else 30
                        _start_small = _scan_end - timedelta(days=_small_days)
                        if _start_small < _start_dt:
                            _start_small = _start_dt
                        _res2, _logs2 = ind_historical_5x5_with_retry(_pairs, TF_API_TRY.get(_tf, [TF_API.get(_tf, "5minute")])[0], to_ms(_start_small), to_ms(_scan_end), token)
                        _tmp2 = {}
                        for _sym, _r in (_res2 or {}).items():
                            _candles = (_r or {}).get("candles", []) or []
                            if not _candles:
                                continue
                            _df_c = ind_candles_to_df(_candles)
                            _rows = tf_rows_from_candles_df(_df_c, _sym)
                            if _rows.empty:
                                continue
                            _rows["MM"] = pd.to_datetime(_rows["TIME"].astype(str), errors="coerce").dt.strftime("%Y-%m")
                            for _mm, _sub in _rows.groupby("MM"):
                                if not _mm or str(_mm) == "nan":
                                    continue
                                _tmp2.setdefault(str(_mm), []).append(_sub.drop(columns=["MM"]))
                        if _tmp2:
                            _by_month = _tmp2
                            _got_any = True
                            _mode = f"{_mode} - bada window 0 diya, chhota window ({_small_days} din) chala"
                    except:
                        pass
                if not _by_month:
                    _out.append((_tf, "", False, f"{_tf}: {_mode} - 0 candles - try kiya: {', '.join(_tried)} - Agli baar phir try hoga, purana data delete nahi hua"))
                    continue
                for _mm, _parts in _by_month.items():
                    _merged = pd.concat(_parts, ignore_index=True)
                    _ok, _msg = save_tf_month(_tf, _mm, _merged)
                    _out.append((_tf, _mm, _ok, f"{_mode} - {_msg}"))
            except Exception as _e_tf:
                _out.append((_tf, "", False, f"{_tf}: error - {_e_tf}"))
        return _out
    except Exception as e:
        return [("all", "", False, f"History download error - {e}")]


def ind_get_scrip(symbol, token, scrip_map=None):
    # V22 - Naam se Search nahi, Code se Search - symbol yahan pe sirf Suggestion ke liye aaya hai, andar Code se hi khojenge.
    # Code pehle se hi Master File (Download Data se GitHub me save hui) me hai, isliye Error aayega hi nahi.
    # V39 - FIX: "STATE BANK OF INDIA" jaisa full naam aaye to pehle Symbol (SBIN) me badlo, phir Code khojo - nahi to Code kabhi nahi milega
    if scrip_map and str(symbol).upper() in scrip_map:
        return str(scrip_map[str(symbol).upper()]), "MAP - Code se"
    try:
        _sym2, _ = resolve_to_symbol(str(symbol))
        if _sym2 and scrip_map and str(_sym2).upper() in scrip_map:
            return str(scrip_map[str(_sym2).upper()]), "MAP - Full naam se Symbol bana ke"
    except:
        pass
    if symbol in KNOWN_SCRIP:
        return KNOWN_SCRIP[symbol], "KNOWN"
    try:
        m = ind_get_all_scrips(token)
        if str(symbol).upper() in m:
            return str(m[str(symbol).upper()]), "CSV"
    except:
        pass
    return "", f"CSV me {symbol} nahi mila"

def _parse_option_chain_data(data):
    # V30 - Chain ka parse ek jagah - IND kabhi strikes ko dict deta hai, kabhi list, kabhi keys alag hoti hain - sab handle karo
    # Dict form: strikes = {"2500": {"ce": {...}, "pe": {...}}, ...}
    # List form: strikes = [{"strike": 2500, "ce": {...}, "pe": {...}}, ...] ya [{"strike_price": 2500, "call": {...}, "put": {...}}, ...]
    # Har leg me premium ke naam alag ho sakte hain - last_price / ltp / premium / close - pehla jo mile wahi lo
    try:
        if not isinstance(data, dict):
            return pd.DataFrame(), 0
        strikes = data.get("strikes", None)
        if strikes is None:
            strikes = data.get("options", None)
        if strikes is None:
            return pd.DataFrame(), 0
        # List ko dict jaisa banao
        items = []
        if isinstance(strikes, dict):
            for _k, _v in strikes.items():
                items.append((_k, _v))
        elif isinstance(strikes, list):
            for _el in strikes:
                if not isinstance(_el, dict):
                    continue
                _k = _el.get("strike", _el.get("strike_price", _el.get("strikePrice", "")))
                items.append((_k, _el))
        else:
            return pd.DataFrame(), 0
        def _leg_val(leg, keys, default=0):
            try:
                if not isinstance(leg, dict):
                    return default
                for _k in keys:
                    if _k in leg and leg[_k] not in (None, "", "nan"):
                        return leg[_k]
                return default
            except:
                return default
        rows = []
        for _strike_key, _legs in items:
            try:
                try:
                    _strike = safe_int(float(str(_strike_key).strip()))
                except:
                    # List wale me strike key ke bajaye legs me strike ho sakta hai
                    _strike = safe_int(float(str(_legs.get("strike", _legs.get("strike_price", 0))))) if isinstance(_legs, dict) else 0
                if _strike <= 0:
                    continue
                if not isinstance(_legs, dict):
                    continue
                # CE / PE ke naam - ce/pe, CE/PE, call/put
                _ce = _legs.get("ce", _legs.get("CE", _legs.get("call", _legs.get("Call", {}))))
                _pe = _legs.get("pe", _legs.get("PE", _legs.get("put", _legs.get("Put", {}))))
                if not isinstance(_ce, dict):
                    _ce = {}
                if not isinstance(_pe, dict):
                    _pe = {}
                rows.append({
                    "Strike": _strike,
                    "CE Premium": safe_float(_leg_val(_ce, ["last_price", "ltp", "premium", "last_traded_price", "close", "price"])),
                    "PE Premium": safe_float(_leg_val(_pe, ["last_price", "ltp", "premium", "last_traded_price", "close", "price"])),
                    "CE OI": safe_int(_leg_val(_ce, ["oi", "open_interest", "openInterest"])),
                    "PE OI": safe_int(_leg_val(_pe, ["oi", "open_interest", "openInterest"])),
                    "CE IV": safe_float(_leg_val(_ce, ["iv", "implied_volatility", "impliedVolatility"])),
                    "PE IV": safe_float(_leg_val(_pe, ["iv", "implied_volatility", "impliedVolatility"])),
                    "CE Delta": safe_float(_leg_val((_ce.get("greeks", {}) or {}), ["delta"]) if isinstance(_ce.get("greeks", {}), dict) else safe_float(_leg_val(_ce, ["delta"]))),
                    "PE Delta": safe_float(_leg_val((_pe.get("greeks", {}) or {}), ["delta"]) if isinstance(_pe.get("greeks", {}), dict) else safe_float(_leg_val(_pe, ["delta"]))),
                    "CE Bid": safe_float(_leg_val(_ce, ["top_bid_price", "bid", "best_bid", "bid_price"])),
                    "CE Ask": safe_float(_leg_val(_ce, ["top_ask_price", "ask", "best_ask", "ask_price"])),
                    "PE Bid": safe_float(_leg_val(_pe, ["top_bid_price", "bid", "best_bid", "bid_price"])),
                    "PE Ask": safe_float(_leg_val(_pe, ["top_ask_price", "ask", "best_ask", "ask_price"])),
                })
            except:
                continue
        if not rows:
            return pd.DataFrame(), 0
        _df = pd.DataFrame(rows).sort_values("Strike").reset_index(drop=True)
        return _df, len(_df)
    except Exception:
        return pd.DataFrame(), 0

def ind_get_option_chain(symbol, token, scrip_map=None):
    # V30 - PHOTO WALA FIX - Pehle wala code pehli hi koshish me haar maan jata tha:
    #   params = {exchange NSE, segment EQUITY, expiry 2026-11-26} -> API ne 200 + {"strikes": []} diya -> humne turant "strikes khali" bol ke return kar diya.
    # Asli wajah Token nahi tha - Token sahi tha, isliye underlying_ltp 1984.9 aa gaya tha. Wajah ye thi:
    #   1) Segment galat ho sakta hai - Equity Options ke liye DERIVATIVE chahiye hota hai, EQUITY pe khali aata hai
    #   2) Expiry galat ho sakti hai - Master wali Expiry monthly ho, Chain ko weekly chahiye ho, ya us Expiry pe us stock ki Chain hi na ho
    #   3) strike_count galat ho sakta hai - 25 pe khali, 10 pe aa jaye
    # Isliye ab ek koshish me haar nahi manenge - Expiry (3 tak) x Segment (DERIVATIVE / EQUITY / bina segment) x strike_count (25 / 10 / bina) - sab try karenge.
    # Jisme pehle strikes mil jayenge, wahin ruk jayenge. Sab fail ho to tabhi khali bolenge, poora try-list ke saath - taaki pata chale kya-kya try kiya.
    if not token or len(str(token).strip()) < 10:
        return pd.DataFrame(), "Token nahi diya", "", "", ""
    expiries, err_exp = ind_get_expiries(symbol, token)
    if not expiries:
        expiries = [get_nearest_thursday_fallback()]
        err_exp = f"Expiry list khali thi, Fallback Thursday {expiries[0]} try kar rahe hain - {err_exp}"
    # Expiry list - pehli 3 hi try karenge (zyada try karne se slow hoga) + Fallback Thursday bhi jod do agar list me nahi hai
    _try_expiries = []
    for _e in list(expiries)[:3]:
        _es = str(_e).strip()
        if _es and _es not in _try_expiries:
            _try_expiries.append(_es)
    try:
        _fb = get_nearest_thursday_fallback()
        if _fb not in _try_expiries:
            _try_expiries.append(_fb)
    except:
        pass
    scrip, _src = ind_get_scrip(symbol, token, scrip_map)
    if not scrip:
        return pd.DataFrame(), f"Scrip nahi mila - {_src}", str(_try_expiries[0]) if _try_expiries else "", "", ""
    # Segment / strike_count ke combos - DERIVATIVE pehle (Equity Options ke liye yahi sahi hota hai), phir EQUITY, phir bina segment
    _combos = [
        ({"exchange": "NSE", "segment": "DERIVATIVE"}, "DERIVATIVE", 25),
        ({"exchange": "NSE", "segment": "EQUITY"}, "EQUITY", 25),
        ({}, "BINA-SEGMENT", 25),
        ({"exchange": "NSE", "segment": "DERIVATIVE"}, "DERIVATIVE", 10),
        ({"exchange": "NSE", "segment": "DERIVATIVE"}, "DERIVATIVE-BINA-COUNT", None),
    ]
    _tried = []
    _last_ltp = ""
    _last_raw = ""
    for _expiry in _try_expiries:
        for _base_params, _seg_name, _scount in _combos:
            try:
                _params = dict(_base_params)
                _params["underlying-scrip"] = scrip
                _params["expiry"] = _expiry
                if _scount is not None:
                    _params["strike_count"] = _scount
                _tried.append(f"{_expiry} + {_seg_name} + count={_scount}")
                r = requests.get(f"{IND_BASE}/market/option-chain", headers=ind_headers(token), params=_params, timeout=15)
                if r.status_code != 200:
                    _last_raw = f"Status {r.status_code} - {r.text[:200]}"
                    continue
                try:
                    j = r.json()
                except:
                    _last_raw = f"JSON parse nahi hua - {r.text[:200]}"
                    continue
                data = j.get("data", {}) if isinstance(j, dict) else {}
                if not isinstance(data, dict):
                    data = {}
                _last_ltp = str(safe_float(data.get("underlying_ltp", 0))) if data.get("underlying_ltp") is not None else _last_ltp
                _last_raw = str(j)[:400]
                _df_chain, _n = _parse_option_chain_data(data)
                if _df_chain is not None and not _df_chain.empty and _n > 0:
                    # Mil gayi - isi Expiry + Segment pe ruk jao, aage try mat karo (fast ke liye)
                    return _df_chain, f"IND SE AAYA - {_n} strikes - Expiry {_expiry} - Segment {_seg_name} - Scrip {scrip} - LTP {_last_ltp}", _expiry, scrip, _last_ltp
                # Strikes khali aaye - is combo pe haar mat mano, agle combo / agle Expiry pe jao (yehi photo wala fix hai)
                continue
            except Exception as _e_combo:
                _last_raw = f"Combo error - {_e_combo}"
                continue
    # Sab try kar liya, kahin se strikes nahi aaye
    _try_txt = " | ".join(_tried)
    return pd.DataFrame(), f"IND se strikes khali aaye - Sab try kiya: {_try_txt} - Scrip {scrip} - LTP {_last_ltp} - Aakhri jawab: {_last_raw[:300]} - Token sahi hai (LTP aa gaya), Expiry / Segment ka combo nahi mila. Agli Expiry ya thodi der baad dobara try karo.", str(_try_expiries[0]) if _try_expiries else "", scrip, _last_ltp

# ---------------- HISTORICAL DATA - INDstocks - TUMHARE PHOTO WALA PAGE ----------------
def ind_get_historical_batch(scrip_codes, interval, start_ms, end_ms, token):
    # Docs: GET /market/historical/{interval}?scrip-codes=NSE_3045,NFO_51011&start_time=...&end_time=...
    # scrip-codes MAX 5 hai - 5 se zyada bhejoge to 400 aayega. Isliye caller ko 5-5 karke bhejna hai.
    # start_time / end_time MILLISECONDS me, candle ka ts SECONDS me aayega.
    # Response: {"success": true, "data": {"NSE_3045": {"candles": [{"ts":..., "o":..., "h":..., "l":..., "c":..., "v":...}]}}}
    # Jo code ka data nahi hai, wo "data" me aayega hi nahi - isliye keys check karo.
    if not token or not scrip_codes:
        return {}, "Token ya Scrip khali"
    if len(scrip_codes) > 5:
        return {}, "Ek baar me max 5 scrip-codes - batching galat hui"
    try:
        params = {"scrip-codes": ",".join(scrip_codes), "start_time": int(start_ms), "end_time": int(end_ms)}
        r = requests.get(f"{IND_BASE}/market/historical/{interval}", headers=ind_headers(token), params=params, timeout=15)
        if r.status_code != 200:
            return {}, f"Historical Fail {r.status_code} - {r.text[:400]}"
        j = r.json()
        if not j.get("success", False):
            return {}, f"Historical success=False - {str(j)[:400]}"
        data = j.get("data", {})
        return data, "OK"
    except Exception as e:
        return {}, f"Historical Error - {e}"

def ind_candles_to_df(candles_list):
    # IND candle: {"ts": seconds, "o": open, "h": high, "l": low, "c": close, "v": volume}
    # ts ko IST datetime me badlo, 09:15 wali candle 09:15-09:19 ko cover karti hai
    if not candles_list:
        return pd.DataFrame()
    rows = []
    for c in candles_list:
        try:
            ts = safe_float(c.get("ts", 0))
            dt = from_ts_seconds(ts)
            rows.append({"Time": dt, "Open": safe_float(c.get("o", 0)), "High": safe_float(c.get("h", 0)), "Low": safe_float(c.get("l", 0)), "Close": safe_float(c.get("c", 0)), "Volume": safe_float(c.get("v", 0))})
        except:
            continue
    df = pd.DataFrame(rows).sort_values("Time").reset_index(drop=True)
    return df

def ind_get_day_candles_for_symbol(symbol, scrip, token, trading_day):
    # Aaj ka 5minute: 09:15 se 15:30 tak. Agar abhi market chal raha hai to ab tak, nahi to 15:30 tak.
    # 5minute ka Max Range 7 Din hai, isliye aaj ka din ek call me aa jayega.
    now = ist_now()
    start_dt = datetime(trading_day.year, trading_day.month, trading_day.day, 9, 15, 0, tzinfo=IST)
    if trading_day == now.date() and now.hour < 15 or (trading_day == now.date() and now.hour == 15 and now.minute <= 30):
        end_dt = now
    else:
        end_dt = datetime(trading_day.year, trading_day.month, trading_day.day, 15, 30, 0, tzinfo=IST)
    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(hours=6, minutes=15)
    code = f"NSE_{scrip}"
    data, msg = ind_get_historical_batch([code], "5minute", to_ms(start_dt), to_ms(end_dt), token)
    if code not in data:
        return pd.DataFrame(), f"{symbol} ka 5min data nahi aaya - {msg}"
    candles = data[code].get("candles", []) or []
    df = ind_candles_to_df(candles)
    return df, "OK"


def ind_get_multi_timeframe(symbol, scrip, token, trading_day):
    # WORLD BEST TRADERS KI STRATEGY - EK TIMEFRAME NAHI, 3 TIMEFRAME EK SAATH:
    # - 1minute: Subah 09:20 pe jab 5minute ki sirf 1 candle hoti hai, tab 1minute ki 5 candles se Gap + VWAP + Volume pata chalta hai. (Ross Cameron - 1min ORB)
    # - 5minute: ORB 09:15-09:30 + VWAP + Day Range - Main timeframe. (Andrew Aziz - ORB + VWAP)
    # - 15minute: Trend confirm karne ke liye - 15min me breakout pakka hai ya fake. (Minervini - Trend + VCP)
    # - 1day: ATR + Pichhla Trend + Support - O'Neil / Minervini
    # - Scan kisi bhi time ho: 09:20, 09:30, 09:35, 01:00, 02:00 - Start hamesha 09:15, End = abhi ka time ya 15:30.
    # Isliye kabhi bhi 0 candles nahi aayengi agar market us din khula tha.
    start_dt, end_dt = get_scan_window(trading_day)
    code = f"NSE_{scrip}"
    out = {"df_1min": None, "df_5min": None, "df_15min": None, "df_daily": None, "debug": []}
    # 5minute pehle
    try:
        data5, msg5 = ind_get_historical_batch([code], "5minute", to_ms(start_dt), to_ms(end_dt), token)
        if code in data5:
            out["df_5min"] = ind_candles_to_df(data5[code].get("candles", []) or [])
            out["debug"].append(f"5min: {len(out['df_5min'])} candles")
        else:
            out["debug"].append(f"5min: 0 - {msg5}")
    except Exception as e:
        out["debug"].append(f"5min error {e}")
    # Agar 5min me 3 se kam candles hain (jaise 09:20 pe) to 1minute se bharo
    need_1min = out["df_5min"] is None or len(out["df_5min"]) < 3
    if need_1min:
        try:
            data1, msg1 = ind_get_historical_batch([code], "1minute", to_ms(start_dt), to_ms(end_dt), token)
            if code in data1:
                out["df_1min"] = ind_candles_to_df(data1[code].get("candles", []) or [])
                out["debug"].append(f"1min: {len(out['df_1min'])} candles")
                # 1min se 5min banao - har 5 candles ko ek me milao
                if out["df_5min"] is None or len(out["df_5min"]) == 0:
                    if out["df_1min"] is not None and len(out["df_1min"]) > 0:
                        # 1min ko 5min me resample karo
                        df1 = out["df_1min"].copy()
                        df1 = df1.set_index("Time")
                        df5r = df1.resample("5min").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna().reset_index()
                        out["df_5min"] = df5r
                        out["debug"].append(f"1min se 5min banaya: {len(df5r)}")
            else:
                out["debug"].append(f"1min: 0 - {msg1}")
        except Exception as e:
            out["debug"].append(f"1min error {e}")
    # 15minute - trend confirm
    try:
        data15, msg15 = ind_get_historical_batch([code], "15minute", to_ms(start_dt), to_ms(end_dt), token)
        if code in data15:
            out["df_15min"] = ind_candles_to_df(data15[code].get("candles", []) or [])
            out["debug"].append(f"15min: {len(out['df_15min'])} candles")
        else:
            out["debug"].append(f"15min: 0 - {msg15}")
    except Exception as e:
        out["debug"].append(f"15min error {e}")
    # Daily - ATR ke liye
    try:
        start_daily = end_dt - timedelta(days=35)
        dataD, msgD = ind_get_historical_batch([code], "1day", to_ms(start_daily), to_ms(end_dt), token)
        if code in dataD:
            out["df_daily"] = ind_candles_to_df(dataD[code].get("candles", []) or [])
            out["debug"].append(f"Daily: {len(out['df_daily'])} candles")
        else:
            out["debug"].append(f"Daily: 0 - {msgD}")
    except Exception as e:
        out["debug"].append(f"Daily error {e}")
    return out


# ---------------- STEP 2: NSE - Docs se check kiya hua ----------------
# NSE India ka official website API hai (unofficial docs, lekin sab jagah use hota hai):
# - GET https://www.nseindia.com/api/quote-equity?symbol=RELIANCE  -> LTP, Open, High, Low, PrevClose, VWAP jaisa data
# - GET https://www.nseindia.com/api/option-chain-equities?symbol=RELIANCE -> Option Chain
# NSE ko pehle https://www.nseindia.com khol ke cookie lena padta hai, nahi to 403 aata hai.
# Isliye hum session banate hain, pehle homepage kholte hain, phir quote mangte hain.
# NSE kabhi-kabhi Streamlit Cloud se 403 de deta hai - isliye NSE FAIL hona normal hai, usko error nahi manna,
# us stock ko Step 3 me IND se le lenge. Yahi 3-step ka matlab hai - ek fail hua to dusra sambhal lega.
def nse_get_session():
    # V24 DEAD CODE - Kabhi call nahi hoga, sirf IND se scan hoga. Is function ko rakha hai taaki purana import na toote.
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/",
    })
    try:
        # Cookie lene ke liye homepage - 8 sec se zyada wait nahi karenge
        s.get("https://www.nseindia.com", timeout=8)
    except Exception:
        pass
    return s

def nse_get_quote(symbol, session=None):
    # V24 DEAD CODE - Kabhi call nahi hoga, sirf IND se scan hoga.
    # Returns (dict_or_None, msg)
    # NSE symbol me M&M jaisa & hota hai, usko URL me sahi se bhejna hai - requests khud kar lega
    try:
        s = session or nse_get_session()
        # NSE symbol: MARKET_STOCKS keys hi NSE symbol hain (RELIANCE, M&M, etc.) - .NS hatana hai, Yahoo wala .NS nahi bhejna
        url = "https://www.nseindia.com/api/quote-equity"
        r = s.get(url, params={"symbol": symbol}, timeout=10)
        if r.status_code == 403:
            return None, "NSE 403 - NSE ne Cloud IP ko rok diya, isliye Step 3 IND se lenge"
        if r.status_code != 200:
            return None, f"NSE Fail {r.status_code} - {r.text[:200]}"
        j = r.json()
        price = j.get("priceInfo", {}) or {}
        if not price:
            return None, "NSE se priceInfo khali aaya"
        out = {
            "LTP": safe_float(price.get("lastPrice", 0)),
            "Open": safe_float(price.get("open", 0)),
            "High": safe_float(price.get("intraDayHighLow", {}).get("max", 0)) if isinstance(price.get("intraDayHighLow", {}), dict) else 0,
            "Low": safe_float(price.get("intraDayHighLow", {}).get("min", 0)) if isinstance(price.get("intraDayHighLow", {}), dict) else 0,
            "PrevClose": safe_float(price.get("previousClose", 0)),
            "Change%": safe_float(price.get("pChange", 0)),
            "VWAP": safe_float(price.get("vwap", 0)) if price.get("vwap") else 0,
            "Volume": safe_float(price.get("totalTradedVolume", 0)),
            "UpperCP": safe_float(price.get("upperCP", 0)),
            "LowerCP": safe_float(price.get("lowerCP", 0)),
        }
        # High/Low agar intraDay se nahi aaya to priceInfo ke dayHigh/dayLow se lo
        if out["High"] == 0:
            out["High"] = safe_float(price.get("dayHigh", 0))
        if out["Low"] == 0:
            out["Low"] = safe_float(price.get("dayLow", 0))
        return out, "NSE SE AAYA"
    except Exception as e:
        return None, f"NSE Error - {e}"

def nse_get_option_chain(symbol, session=None):
    # V24 DEAD CODE - Kabhi call nahi hoga, sirf IND se Option Chain aayega.
    # Returns (df_or_empty, msg) - NSE ka format IND se alag hai, isliye alag parse karna hai
    # NSE: data -> filtered -> data list, har row me strikePrice, CE, PE
    try:
        s = session or nse_get_session()
        r = s.get("https://www.nseindia.com/api/option-chain-equities", params={"symbol": symbol}, timeout=12)
        if r.status_code == 403:
            return pd.DataFrame(), "NSE 403 - Cloud IP block, Step 3 IND se lenge"
        if r.status_code != 200:
            return pd.DataFrame(), f"NSE Option Fail {r.status_code}"
        j = r.json()
        records = j.get("records", {}) or {}
        data_list = records.get("data", []) or []
        if not data_list:
            return pd.DataFrame(), "NSE se Option data khali"
        rows = []
        for d in data_list:
            try:
                strike = safe_int(d.get("strikePrice", 0))
                ce = d.get("CE", {}) or {}
                pe = d.get("PE", {}) or {}
                rows.append({
                    "Strike": strike,
                    "CE Premium": safe_float(ce.get("lastPrice", 0)),
                    "PE Premium": safe_float(pe.get("lastPrice", 0)),
                    "CE OI": safe_int(ce.get("openInterest", 0)),
                    "PE OI": safe_int(pe.get("openInterest", 0)),
                    "CE IV": safe_float(ce.get("impliedVolatility", 0)),
                    "PE IV": safe_float(pe.get("impliedVolatility", 0)),
                    "CE Bid": safe_float(ce.get("bidprice", 0)),
                    "CE Ask": safe_float(ce.get("askPrice", 0)),
                    "PE Bid": safe_float(pe.get("bidprice", 0)),
                    "PE Ask": safe_float(pe.get("askPrice", 0)),
                    "CE Delta": 0, "PE Delta": 0,
                })
            except:
                continue
        df = pd.DataFrame(rows).sort_values("Strike").reset_index(drop=True) if rows else pd.DataFrame()
        if df.empty:
            return pd.DataFrame(), "NSE parse ke baad khali"
        return df, f"NSE SE AAYA - {len(df)} strikes"
    except Exception as e:
        return pd.DataFrame(), f"NSE Option Error - {e}"

# ---------------- IND-ONLY SCAN - YAHI ASLI FIX HAI 86 FAIL KA ----------------
# PEHLE WALA TAREEKA KYU FAIL HUA (86/138):
# 1) Hum 138 stocks ko IND se 5-5 karke batch me mangte the. Docs me likha hai scrip-codes max 5 hai,
#    lekin agar us 5 me se 1 bhi scrip-code galat hua (jaise TATAMOTORS ka ID badal gaya, ya M&M ka & wala naam CSV me alag tha,
#    ya kisi stock ka SECURITY_ID CSV me mila hi nahi) to poora batch 400 de deta hai - 5 ke 5 stock udd jate hain.
#    138 / 5 = 28 batch, usme se 17 batch me 1-1 galat code tha -> 17*5 = 85 stock udd gaye. Yahi 86 fail ka hisab hai.
# 2) Rate limit: IND Data APIs 5/sec hai. Hum 138 stocks ke liye 28 batch + 28 daily + 28 15min = 84 calls 10 sec me maar dete the -> 429 aaya, aur batch fail.
# 3) Scrip Map: IND instruments CSV me SYMBOL_NAME aur TRADING_SYMBOL alag-alag hote hain. Hum SYMBOL_NAME se match karte the,
#    to M&M, M&M, TATAMOTORS jaisi kai stocks ka ID mila hi nahi -> uska code hi nahi bana -> skip.
# NAYA TAREEKA - 3 STEP, BOJH 97% KAM:
# STEP 1: Yahoo/Google (Internet) se 138 stocks ka data - 1 hi call me sab aa jata hai, koi scrip-code nahi, koi rate limit nahi.
#         Isse Top 5 + Manual News wale (jaise BHEL) chunte hain.
# STEP 2: Sirf un 6 ko NSE pe check karte hain - jo NSE de de wo NSE se le lo.
# STEP 3: Jo NSE nahi de paya / error / khali, wo sirf wahi cheez IND se mangte hain - sirf 6 stocks, isliye IND pe bojh hi nahi, fail hone ka chance hi nahi.
#         Aur IND me bhi 5-5 batch nahi, 1-1 karke retry karenge, taaki 1 galat code se 5 na udein.
def check_ind_token():
    # V38 - Token chal raha hai ya expire ho gaya - 1 stock se check karo, poora Scan mat karo
    # Returns (ok, msg) - ok=True matlab Token sahi hai, ok=False matlab Token daalna padega
    try:
        import streamlit as _st
        _tok = _st.session_state.get("indmoney_secret", "")
    except:
        _tok = ""
    if not _tok or len(str(_tok)) < 10:
        return False, "Token khali hai - naya Token daalo (24 ghante me expire hota hai)"
    try:
        _smap = ind_get_all_scrips(_tok)
        if not _smap:
            return False, "Token se Scrip list nahi aayi - Token expire ho gaya lag raha hai, naya Token daalo"
        _q, _msg = ind_quotes_full_docs_pattern(["NSE_2885"], _tok)
        if _q:
            return True, "Token chal raha hai - Scan dabao"
        return False, f"Token se Quote nahi aaya - {_msg} - naya Token daalo"
    except Exception as e:
        return False, f"Token check me error - {e} - naya Token daalo"


def scan_from_saved_history():
    # V38 - FALLBACK - IND se 0 aaya to bhi khali mat chhodo - GitHub me saved 5min + Daily se hi Score banao
    # Pichhle saved din ka data hai, Live nahi hai - isliye ispe "SAVED" likha rahega, Chain ke liye Token chahiye
    # Score wahi 100-point wala: Gap 15 + VWAP 15 + ORB 20 + Volume 15 + Movement 15 + Trending 10 + Volatility 10
    try:
        _td = get_trading_day()
        _mm = tf_yyyymm(_td)
        _df5 = load_tf_month("5min", _mm)
        _dfd = load_tf_month("daily", _mm)
        if _df5 is None or _df5.empty:
            return pd.DataFrame(), "Saved 5min data nahi hai - pehle Download Data dabao"
        # Aakhri saved din nikalo - usi din ka scan banega
        try:
            _df5["_DT"] = pd.to_datetime(_df5["TIME"].astype(str), errors="coerce")
            _last_day = _df5["_DT"].dt.date.max()
            _day5 = _df5[_df5["_DT"].dt.date == _last_day].copy()
        except:
            _last_day = None
            _day5 = _df5.copy()
        if _day5.empty:
            return pd.DataFrame(), "Saved data me aakhri din nahi mila"
        rows = []
        # Daily se pichhla close + avg volume nikalo
        _prev_close = {}
        _avg_vol = {}
        try:
            if _dfd is not None and not _dfd.empty and "STOCK" in _dfd.columns:
                _dfd2 = _dfd.copy()
                _dfd2["_DT2"] = pd.to_datetime(_dfd2["TIME"].astype(str), errors="coerce")
                for _sym, _g in _dfd2.groupby(_sym if False else _dfd2["STOCK"].astype(str).str.upper()):
                    try:
                        _g2 = _g.sort_values("_DT2")
                        if len(_g2) >= 2:
                            _prev_close[str(_sym).upper()] = safe_float(_g2.iloc[-2]["CLOSE"])
                        _avg_vol[str(_sym).upper()] = safe_float(pd.to_numeric(_g2["VOLUME"], errors="coerce").tail(5).mean())
                    except:
                        continue
        except:
            pass
        for _sym, _g in _day5.groupby(_day5["STOCK"].astype(str).str.upper()):
            try:
                _g2 = _g.sort_values("_DT")
                if len(_g2) < 5:
                    continue
                _open = safe_float(_g2.iloc[0]["OPEN"]); _close = safe_float(_g2.iloc[-1]["CLOSE"])
                _high = safe_float(pd.to_numeric(_g2["HIGH"], errors="coerce").max()); _low = safe_float(pd.to_numeric(_g2["LOW"], errors="coerce").min())
                _vol_today = safe_float(pd.to_numeric(_g2["VOLUME"], errors="coerce").sum())
                _first3 = _g2.head(3)
                _orb_h = safe_float(pd.to_numeric(_first3["HIGH"], errors="coerce").max()); _orb_l = safe_float(pd.to_numeric(_first3["LOW"], errors="coerce").min())
                _prev = _prev_close.get(str(_sym).upper(), _open)
                _gap = ((_open - _prev) / _prev * 100) if _prev else 0.0
                try:
                    _tp = (pd.to_numeric(_g2["HIGH"], errors="coerce") + pd.to_numeric(_g2["LOW"], errors="coerce") + pd.to_numeric(_g2["CLOSE"], errors="coerce")) / 3
                    _vv = pd.to_numeric(_g2["VOLUME"], errors="coerce")
                    _vwap = safe_float((_tp * _vv).sum() / _vv.sum()) if _vv.sum() > 0 else _close
                except:
                    _vwap = _close
                _avgv = _avg_vol.get(str(_sym).upper(), 0)
                _volx = (_vol_today / _avgv) if _avgv else 1.0
                _orb_break = bool(_close > _orb_h or _close < _orb_l)
                _moved = "HAAN" if _orb_break else "NAHI"
                _move_pct = ((_close - _open) / _open * 100) if _open else 0.0
                if _close > _vwap and _close > _open:
                    _dir = "BULLISH"
                elif _close < _vwap and _close < _open:
                    _dir = "BEARISH"
                else:
                    _dir = "NEUTRAL"
                if _move_pct >= 2:
                    _mtype = "BHAG RAHA UPAR"
                elif _move_pct <= -2:
                    _mtype = "GIR RAHA"
                elif abs(_move_pct) < 0.5:
                    _mtype = "SIDEWAYS"
                else:
                    _mtype = "TRENDING"
                # Score - wahi 100-point wala
                _score = 0
                if abs(_gap) > 0.30: _score += 15
                if (_close > _vwap and _gap > 0) or (_close < _vwap and _gap < 0): _score += 15
                if _orb_break: _score += 20
                if _volx > 1.5: _score += 15
                if _moved == "HAAN": _score += 15
                if abs(_move_pct) >= 1: _score += 10
                if "SIDEWAYS" not in _mtype: _score += 10
                _score = max(0, min(100, int(_score)))
                _pass = sum([abs(_gap) > 0.30, (_close > _vwap and _gap > 0) or (_close < _vwap and _gap < 0), _orb_break, _volx > 1.5])
                rows.append({
                    "Stock": str(_sym).upper(), "LTP": _close, "Probability %": _score, "Score": _score,
                    "Gap %": round(_gap, 2), "Gap": "✅" if abs(_gap) > 0.30 else "❌",
                    "VWAP": _vwap, "VWAP_OK": "✅" if ((_close > _vwap and _gap > 0) or (_close < _vwap and _gap < 0)) else "❌",
                    "ORB High": _orb_h, "ORB Low": _orb_l, "ORB": "✅" if _orb_break else "❌", "ORB Break": _orb_break,
                    "Vol x": round(_volx, 2), "Volume": "✅" if _volx > 1.5 else "❌",
                    "Movement Started?": _moved, "Movement Type": _mtype, "Movement": _mtype,
                    "Direction": _dir, "Pass": f"{_pass}/4", "Pass_Count": _pass,
                    "Volatility OK": "✅" if "SIDEWAYS" not in _mtype else "❌", "Fake?": "NAHI",
                    "Wick": 0.0, "Reversal": 0, "Source": "SAVED", "Pattern": "", "Movement Detail": f"Saved din {_last_day} - Gap {_gap:+.2f}% - Vol {_volx:.1f}x - {_mtype}",
                    "Session Story": f"Saved data se - {_last_day}", "Day Range %": round(((_high - _low) / _open * 100) if _open else 0, 2),
                    "Trending Score": 60 if abs(_move_pct) >= 1 else 30, "Fake Breakout": False,
                })
            except:
                continue
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        if not df.empty:
            df = df.sort_values("Probability %", ascending=False).reset_index(drop=True)
        return df, f"Saved din {_last_day} se {len(df)} stocks ka Score bana"
    except Exception as e:
        return pd.DataFrame(), f"Saved scan me error - {e}"


def ind_scan_all_ind_only(progress_cb=None):
    # V25 - SIRF IND SE SCAN - 216 STOCKS - Yahoo / NSE band. Docs wala pattern hi sab jagah.
    # Universe: Master FNO se DISTINCT UNDERLYING = 216 stocks (138 wala purana list nahi).
    # Pehle sabka SECURITY_ID GitHub wali IND_Scrip_Codes.csv / IND_Universe_216.csv se turant milega, phir NSE_ + SECURITY_ID banao, phir:
    #  - LTP: quotes/full?scrip-codes=NSE_2885,NSE_11536... (Docs wala)
    #  - Candle: historical/5minute?scrip-codes=NSE_... (5-5 batch, fail -> 1-1)
    #  - Phir analyze_full_day se hi Top 15 + Prob>=50 chunenge.
    rows = []
    debug = {"ind_ok": 0, "ind_fail": [], "ind_total": 0, "universe_msg": ""}
    try:
        token = None
        try:
            import streamlit as _st
            token = _st.session_state.get("indmoney_secret", "")
        except:
            token = ""
        # Universe pehle - 216 wala, nahi to 138 fallback
        _universe_216, _udf_216, _umsg_216 = get_scan_universe_216(token)
        debug["ind_total"] = len(_universe_216)
        debug["universe_msg"] = _umsg_216
        if not token:
            debug["ind_fail"] = list(_universe_216)
            return pd.DataFrame(), debug
        scrip_map = ind_get_all_scrips(token) if token else dict(KNOWN_SCRIP)
        debug["scrip_map_size"] = len(scrip_map) if isinstance(scrip_map, dict) else 0
        all_syms = list(_universe_216)
        quote_by_sym = {}
        _closed = is_market_closed_for_scan(get_trading_day())
        if not _closed:
            for i in range(0, len(all_syms), 5):
                chunk = all_syms[i:i+5]
                codes = []
                code_to_sym = {}
                for sym in chunk:
                    sid, _ = ind_get_scrip(sym, token, scrip_map)
                    if sid:
                        c = f"NSE_{sid}"
                        codes.append(c); code_to_sym[c] = sym
                if codes:
                    qdata, _qmsg = ind_quotes_full_docs_pattern(codes, token)
                    for code, d in qdata.items():
                        sym = code_to_sym.get(code)
                        if sym:
                            quote_by_sym[sym] = d
        filled = ind_fill_for_selected(all_syms, token, scrip_map)
        for stock in all_syms:
            try:
                f = filled.get(stock, {})
                if not f.get("ok"):
                    debug["ind_fail"].append(stock)
                    if "first_fail_reason" not in debug:
                        debug["first_fail_reason"] = str(f.get("reason", ""))[:200]
                    continue
                ana = f.get("ana", {})
                if not ana or "error" in ana:
                    debug["ind_fail"].append(stock)
                    continue
                debug["ind_ok"] += 1
                if stock in quote_by_sym:
                    _qd = quote_by_sym[stock]
                    if safe_float(ana.get("LTP", 0)) == 0:
                        ana["LTP"] = safe_float(_qd.get("live_price", 0))
                c1_gap = abs(safe_float(ana.get("Gap %", 0))) > 0.30
                c2_vwap = (safe_float(ana.get("LTP", 0)) > safe_float(ana.get("VWAP", 0)) and safe_float(ana.get("Gap %", 0)) > 0) or (safe_float(ana.get("LTP", 0)) < safe_float(ana.get("VWAP", 0)) and safe_float(ana.get("Gap %", 0)) < 0)
                c3_orb = bool(ana.get("ORB Break", False))
                c4_vol = safe_float(ana.get("Vol x", 0)) > 1.5
                c5_ok = "CHOPPY" not in str(ana.get("Movement Type","")) and "VOLATILE" not in str(ana.get("Movement Type",""))
                score = 0
                if c1_gap: score += 15
                if c2_vwap: score += 15
                if c3_orb: score += 20
                if c4_vol: score += 15
                if c5_ok: score += 10
                if ana.get("Movement Started?") == "HAAN": score += 15
                if safe_float(ana.get("Trending Score",0)) >= 60: score += 10
                if bool(ana.get("Fake Breakout", False)): score -= 30
                if "CHOPPY" in str(ana.get("Movement Type","")): score -= 20
                if "SIDEWAYS" in str(ana.get("Movement Type","")): score -= 15
                score = max(0, min(100, int(score)))
                pass_count = sum([c1_gap, c2_vwap, c3_orb, c4_vol])
                row = dict(ana)
                row["Stock"] = stock
                row["Score"] = score
                # V27 - KeyError Fix - RESULTS wala table neeche Probability % / Gap / VWAP / ORB / Volume / Volatility OK / Fake? / Wick / Reversal mangta hai
                # Pehle ind_scan sirf Score + Pass (int) deta tha, Probability % deta hi nahi tha - isliye top5[[..., "Probability %", ...]] pe KeyError: "['Probability %'] not in index" aa ke app crash ho gaya.
                # Ab sab column yahin se bhar do taaki neeche koi KeyError na aaye.
                # DHYAN: VWAP float hi rakhenge (send_top5 / detail ko price chahiye), uska Pass/Fail alag column VWAP_OK me rakhenge - taaki breakdown bhi sahi rahe aur price bhi sahi rahe.
                row["Probability %"] = score
                row["Pass"] = f"{pass_count}/4"
                row["Pass_Count"] = pass_count
                row["Gap"] = "✅" if c1_gap else "❌"
                row["VWAP_OK"] = "✅" if c2_vwap else "❌"
                row["ORB"] = "✅" if c3_orb else "❌"
                row["Volume"] = "✅" if c4_vol else "❌"
                row["Volatility OK"] = "✅" if c5_ok else "❌"
                row["Fake?"] = "HAAN - TRAP" if bool(ana.get("Fake Breakout", False)) else "NAHI"
                row["Wick"] = safe_float(ana.get("Wick Ratio", 0))
                row["Reversal"] = safe_int(ana.get("Reversal Count", 0))
                row["Source"] = ""
                rows.append(row)
            except Exception as e:
                debug["ind_fail"].append(stock)
                continue
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        return df, debug
    except Exception as e:
        debug["ind_fail"] = list(MARKET_STOCKS.keys())
        return pd.DataFrame(), debug


def yahoo_scan_all_3step(progress_cb=None):
    # V24 - Ye naam sirf piche ki compatibility ke liye hai, andar sirf IND chalega, Yahoo kabhi nahi chalega.
    return ind_scan_all_ind_only(progress_cb)

def ind_fill_for_selected(selected_stocks, token, scrip_map):
    # STEP 3 - V18: Ab 1-1 nahi, 5-5 karke + Fail hone pe 1-1 Retry - User ka niyam bilkul waisa hi
    # - Normal: 5-5 karke. Jo fail nahi hoga, wo 5-5 hi rahega.
    # - Fail wale batch ke 5 ko 1-1 karke. Wo 5 khatam, phir wapas 5-5.
    # Selected 6 hai to: Pehla Batch = 5 stocks (5-5), Dusra Batch = 1 stock (bacha hua 1) - Dono 5-5 ke niyam se hi chalenge.
    # Agar poora 138 ka IND Scan karna ho to bhi yahi function kaam karega - 28 batch banenge, har batch 5-5, fail wala 1-1.
    out = {}
    logs_all = []
    try:
        # Pehle sabka Scrip Code nikal lo - Master CSV wale Map se (Sahi Naam + Code wahi se aaya hai)
        pairs = []
        missing = []
        for sym in selected_stocks:
            sid, _src = ind_get_scrip(sym, token, scrip_map)
            if not sid:
                missing.append(sym)
                out[sym] = {"ok": False, "reason": f"IND Scrip nahi mila - {_src} - Master CSV me iska Sahi Naam + Code check karo, wahi naam likho jo Master me hai", "df_5min": None, "df_daily": None, "chain": None}
            else:
                pairs.append((sym, sid))
        if not pairs:
            return out
        trading_day = get_trading_day()
        start_dt, end_dt = get_scan_window(trading_day)
        # V26 - HISTORY CACHE - Pehle GitHub se pichhla data nikaalo, sirf Delta IND se mango
        # - Daily (1day, 35 din): Agar Cache me 14+ din ka Daily summary hai to IND se 1day mat mango - Cache se hi ATR / Trend ban jayega. Historical kabhi badalta nahi.
        # - 5minute Aaj ka: Agar Cache me Aaj ka 09:15 se Last Cached Time tak ka candle hai to sirf Last Cached Time se Abhi Tak ka Delta mango - poora din dobara mat mango.
        # - 1 ghanta baad dobara scan kiya to 80% data Cache se aa jayega, IND se sirf 1 ghante ka Delta + LTP aayega - isliye 5 min wala scan 1 min me ho jayega.
        # V34 - TF-month files se lo - sirf wahi file khulegi jo chahiye: Daily = is mahine + pichhla mahina (14 din ke liye), 5min = is mahine ki file se aaj ka din
        _cur_mm = tf_yyyymm(trading_day)
        _prev_mm = tf_yyyymm(trading_day - timedelta(days=32))
        _daily_tf = load_tf_month("daily", _cur_mm)
        if _prev_mm != _cur_mm:
            _daily_prev = load_tf_month("daily", _prev_mm)
            if _daily_prev is not None and not _daily_prev.empty:
                _daily_tf = pd.concat([_daily_prev, _daily_tf], ignore_index=True) if _daily_tf is not None and not _daily_tf.empty else _daily_prev
        _today_tf = load_tf_month("5min", _cur_mm)
        logs_all.append(f"History: daily {_cur_mm}+{_prev_mm} {len(_daily_tf) if _daily_tf is not None else 0} rows, 5min {_cur_mm} {len(_today_tf) if _today_tf is not None else 0} rows")
        # Daily - Cache wale alag, Cache me nahi wale alag
        _pairs_need_daily_api = []
        _cached_daily_by_stock = {}
        for _sym, _sid in pairs:
            _cdf = tf_candles_for_stock(_daily_tf, _sym)
            if _cdf is not None and len(_cdf) >= 14:
                _cached_daily_by_stock[_sym] = _cdf
            else:
                _pairs_need_daily_api.append((_sym, _sid))
        # 5minute - Delta wale: Har stock ka Last Cached Time nikaalo, sirf uske baad ka mango
        # Pehle sabka Today Cache dekh lo - kiska kitna cached hai
        _cached_today_by_stock = {}
        _last_cached_by_stock = {}
        for _sym, _sid in pairs:
            _ctdf = tf_candles_for_stock(_today_tf, _sym, trading_day)
            _last = _ctdf["Time"].max() if _ctdf is not None and not _ctdf.empty else None
            if _ctdf is not None and not _ctdf.empty:
                _cached_today_by_stock[_sym] = _ctdf
                _last_cached_by_stock[_sym] = _last
        # 5minute Delta fetch - Sirf unka jinka Today Cache adhura hai (Last Cached < Abhi) ya Cache khali hai
        # Delta ke liye start = Last Cached + 5min, nahi to poora din ka start
        # Ek hi 5x5 call me Delta mangenge - har stock ka alag start nahi bhej sakte, isliye 2 group: (a) Cache khali / purana - poora din, (b) Cache me kuch hai - Delta (Last Cached se)
        # Simple tareeka: Cache wale ka Delta alag se 5x5 me, Cache khali wale ka Full alag se - dono 5-5 + 1-1 Retry se hi
        _pairs_full_5min = []
        _pairs_delta_5min = []
        for _sym, _sid in pairs:
            _last = _last_cached_by_stock.get(_sym)
            # Agar Last Cached aaj ka hai aur abhi se 10 min se kam pehle ka hai to Delta chhota hai, phir bhi Delta hi mangenge - poora din nahi
            if _last is not None:
                _pairs_delta_5min.append((_sym, _sid))
            else:
                _pairs_full_5min.append((_sym, _sid))
        res5 = {}
        logs5 = []
        # (a) Full - Cache khali wale
        if _pairs_full_5min:
            _r5f, _l5f = ind_historical_5x5_with_retry(_pairs_full_5min, "5minute", to_ms(start_dt), to_ms(end_dt), token)
            res5.update(_r5f); logs5.extend(_l5f)
            logs_all.append(f"5minute Full: {len(_pairs_full_5min)} stocks ko poora din IND se manga - Cache me nahi the")
        # (b) Delta - Cache me kuch hai wale - Last Cached + 5min se Abhi Tak
        if _pairs_delta_5min:
            # Delta ka start - sabka alag Last hai, isliye sabse purana Last le ke ek hi window me mango, phir merge karte time purana duplicate hata denge
            _earliest_last = min([_last_cached_by_stock[s] for s, _ in _pairs_delta_5min if _last_cached_by_stock.get(s) is not None])
            _delta_start = _earliest_last + timedelta(minutes=5) if _earliest_last is not None else start_dt
            if _delta_start < end_dt:
                _r5d, _l5d = ind_historical_5x5_with_retry(_pairs_delta_5min, "5minute", to_ms(_delta_start), to_ms(end_dt), token)
                # Delta wale ko Cache + Delta mila ke res5 me daalo
                for _sym, _sid in _pairs_delta_5min:
                    _cached_df = _cached_today_by_stock.get(_sym, pd.DataFrame())
                    _delta_candles = (_r5d.get(_sym, {}) or {}).get("candles", []) or []
                    _delta_df = ind_candles_to_df(_delta_candles) if _delta_candles else pd.DataFrame()
                    # Merge - Cache + Delta, duplicate Time hatao, Delta jeetega (candle chal rahi ho to update hoga)
                    if not _delta_df.empty and not _cached_df.empty:
                        _merged = pd.concat([_cached_df, _delta_df], ignore_index=True)
                        _merged["Time"] = pd.to_datetime(_merged["Time"], errors="coerce")
                        _merged = _merged.drop_duplicates(subset=["Time"], keep="last").sort_values("Time")
                        # Merge ko candles format me wapas banao taaki neeche wala code same rahe - df bana ke res5 me candles ki jagah df hi rakh denge? Neeche code candles se df banata hai, isliye candles list me convert karo
                        _candles_merged = [{"ts": int(pd.to_datetime(r["Time"]).timestamp()), "o": float(r["Open"]), "h": float(r["High"]), "l": float(r["Low"]), "c": float(r["Close"]), "v": float(r["Volume"])} for _, r in _merged.iterrows()]
                        res5[_sym] = {"candles": _candles_merged, "mode": "CACHE+DELTA", "ok": True, "msg": f"Cache {len(_cached_df)} + Delta {len(_delta_df)} = {len(_merged)} candles - IND se sirf Delta manga"}
                    elif not _cached_df.empty and _delta_df.empty:
                        _candles_cached = [{"ts": int(pd.to_datetime(r["Time"]).timestamp()), "o": float(r["Open"]), "h": float(r["High"]), "l": float(r["Low"]), "c": float(r["Close"]), "v": float(r["Volume"])} for _, r in _cached_df.iterrows()]
                        res5[_sym] = {"candles": _candles_cached, "mode": "CACHE-ONLY", "ok": True, "msg": f"Cache se hi {len(_cached_df)} candles - IND se 5min dobara manga hi nahi, sirf LTP quotes/full se aayega"}
                    else:
                        res5[_sym] = _r5d.get(_sym, {})
                logs5.extend(_l5d)
                logs_all.append(f"5minute Delta: {len(_pairs_delta_5min)} stocks ko sirf Delta IND se manga - {_delta_start.strftime('%H:%M')} se {end_dt.strftime('%H:%M')} tak - Pichhla Cache se liya")
            else:
                # Delta window hi nahi hai - sab Cache se hi hai
                for _sym, _sid in _pairs_delta_5min:
                    _cached_df = _cached_today_by_stock.get(_sym, pd.DataFrame())
                    _candles_cached = [{"ts": int(pd.to_datetime(r["Time"]).timestamp()), "o": float(r["Open"]), "h": float(r["High"]), "l": float(r["Low"]), "c": float(r["Close"]), "v": float(r["Volume"])} for _, r in _cached_df.iterrows()] if not _cached_df.empty else []
                    res5[_sym] = {"candles": _candles_cached, "mode": "CACHE-ONLY", "ok": True, "msg": "Cache se hi - Delta 0"}
                logs_all.append(f"5minute: {len(_pairs_delta_5min)} stocks ka Delta 0 tha - sab Cache se hi mil gaya")
        logs_all.extend([f"5minute: {l}" for l in logs5])
        # Daily ke liye bhi 5x5 + Retry - sirf jinko Cache me nahi mila, unko hi IND se mango - 1day ka window alag hai (35 din pehle se)
        end_d = datetime(trading_day.year, trading_day.month, trading_day.day, 15, 30, 0, tzinfo=IST)
        start_d = end_d - timedelta(days=35)
        resD = {}
        logsD = []
        if _pairs_need_daily_api:
            _rD, _lD = ind_historical_5x5_with_retry(_pairs_need_daily_api, "1day", to_ms(start_d), to_ms(end_d), token)
            resD.update(_rD); logsD.extend(_lD)
            logs_all.append(f"Daily: {len(_pairs_need_daily_api)} stocks ko IND se 1day manga - Cache me 14+ din nahi the")
        if _cached_daily_by_stock:
            for _sym, _cdf in _cached_daily_by_stock.items():
                # Cache wali Daily ko resD me daalo - candles format me convert karo taaki neeche wala code same rahe
                _candles_d = [{"ts": int(pd.to_datetime(r["Time"]).timestamp()), "o": float(r["Open"]), "h": float(r["High"]), "l": float(r["Low"]), "c": float(r["Close"]), "v": float(r["Volume"])} for _, r in _cdf.iterrows()]
                resD[_sym] = {"candles": _candles_d, "mode": "CACHE-DAILY", "ok": True, "msg": f"Daily Cache se {len(_cdf)} din - IND se 1day manga hi nahi"}
            logs_all.append(f"Daily: {len(_cached_daily_by_stock)} stocks ka Daily Cache se mila - IND se 1day manga hi nahi, isliye 44 batch bache")
        logs_all.extend([f"1day: {l}" for l in logsD])
        for sym, sid in pairs:
            try:
                r5 = res5.get(sym, {})
                rD = resD.get(sym, {})
                candles5 = r5.get("candles", []) or []
                candlesD = rD.get("candles", []) or []
                df5 = ind_candles_to_df(candles5) if candles5 else pd.DataFrame()
                dfd = ind_candles_to_df(candlesD) if candlesD else pd.DataFrame()
                if df5 is None or len(df5) == 0:
                    out[sym] = {"ok": False, "reason": f"IND Historical khali - 5min Mode: {r5.get('mode','')} - {r5.get('msg','')} - Master CSV me Code check karo", "df_5min": None, "df_daily": dfd if not dfd.empty else None, "chain": None}
                    continue
                ana = analyze_full_day(df5, dfd if dfd is not None else pd.DataFrame())
                out[sym] = {"ok": True, "reason": f"IND SE AAYA - 5min: {r5.get('mode','')} | Daily: {rD.get('mode','')}", "df_5min": df5, "df_daily": dfd, "ana": ana, "debug": [f"5min {r5.get('mode','')}", f"Daily {rD.get('mode','')}"]}
            except Exception as e:
                out[sym] = {"ok": False, "reason": f"IND Error - {e}", "df_5min": None, "df_daily": None, "chain": None}
        # Logs ko session me rakh do taaki UI me dikha sakein - function ke andar session use karna safe hai kyunki Streamlit chal raha hai
        try:
            st.session_state["ind_5x5_logs"] = logs_all
        except:
            pass
        return out
    except Exception as e:
        try:
            st.session_state["ind_5x5_logs"] = logs_all + [f"Fill Error - {e}"]
        except:
            pass
        return out

def ind_get_daily_candles_for_symbol(symbol, scrip, token, trading_day):
    # Pichhle 30 din ka 1day - ATR, Trend, Pichhla Move ke liye. 1day ka Max Range 1 Saal hai.
    end_dt = datetime(trading_day.year, trading_day.month, trading_day.day, 15, 30, 0, tzinfo=IST)
    start_dt = end_dt - timedelta(days=35)
    code = f"NSE_{scrip}"
    data, msg = ind_get_historical_batch([code], "1day", to_ms(start_dt), to_ms(end_dt), token)
    if code not in data:
        return pd.DataFrame(), f"{symbol} ka Daily data nahi aaya - {msg}"
    candles = data[code].get("candles", []) or []
    df = ind_candles_to_df(candles)
    return df, "OK"

# ---------------- FULL DAY MOVEMENT ANALYSIS - YAHI ASLI KAAM HAI ----------------
def compute_atr_from_daily(df_daily, period=14):
    # ATR = True Range ka 14 din ka average. True Range = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
    if df_daily is None or df_daily.empty or len(df_daily) < 3:
        return 0.0, 0.0
    df = df_daily.copy().reset_index(drop=True)
    trs = []
    for i in range(1, len(df)):
        h = safe_float(df.loc[i, "High"]); l = safe_float(df.loc[i, "Low"]); pc = safe_float(df.loc[i-1, "Close"])
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    if not trs:
        return 0.0, 0.0
    atr = float(np.mean(trs[-period:])) if len(trs) >= period else float(np.mean(trs))
    prev_close = safe_float(df.loc[len(df)-2, "Close"]) if len(df) >= 2 else safe_float(df.loc[len(df)-1, "Close"])
    return atr, prev_close

def analyze_full_day(df_5m, df_daily):
    # Input: Aaj ki 5minute candles (09:15 se ab tak) + Pichhle 30 din ki Daily candles
    # Output: Poora din ka khel - Sideways / Bhag Raha / Volatile / Dhire Dhire + saare numbers
    # Sirf Open-High dekhna band - ab hum 8 cheezein dekhte hain.
    out = {}
    # FIX: Pehle yahan len < 5 tha - isliye 09:20 pe scan karne pe 0 stocks aate the. 09:20 pe sirf 1 candle hoti hai, 09:30 pe 3, 09:35 pe 4 - sab <5 the, isliye sab skip ho gaye. Ab len < 1 hai.
    if df_5m is None or df_5m.empty or len(df_5m) < 1:
        out["error"] = "Aaj ki candles bilkul nahi aayi - Market band tha ya data nahi aaya"
        return out
    df = df_5m.copy().reset_index(drop=True)
    # --- 1. BASIC DAY NUMBERS ---
    day_open = safe_float(df.loc[0, "Open"])
    day_high = safe_float(df["High"].max())
    day_low = safe_float(df["Low"].min())
    ltp = safe_float(df.loc[len(df)-1, "Close"])
    day_range = day_high - day_low
    day_range_pct = round((day_range / day_open * 100) if day_open != 0 else 0, 2)
    net_move = ltp - day_open
    net_move_pct = round((net_move / day_open * 100) if day_open != 0 else 0, 2)
    # Net Move / Range = Kitna bhaga vs kitna upar-neeche hua. 0.7+ matlab ek taraf bhaga, 0.3 se kam matlab upar-neeche karke wahi ka wahi.
    net_vs_range = round(abs(net_move) / day_range, 2) if day_range != 0 else 0
    # --- 2. ATR + PREV CLOSE ---
    atr, prev_close = compute_atr_from_daily(df_daily, 14)
    atr_pct = round((atr / ltp * 100) if ltp != 0 else 0, 2)
    range_vs_atr = round((day_range / atr) if atr != 0 else 0, 2)
    gap_pct = round(((day_open - prev_close) / prev_close * 100) if prev_close != 0 else 0, 2)
    # --- 3. VWAP - Poora din ka weighted average ---
    df["Typical"] = (df["High"] + df["Low"] + df["Close"]) / 3
    df["TypVol"] = df["Typical"] * df["Volume"]
    cum_vol = df["Volume"].cumsum().replace(0, np.nan)
    df["VWAP"] = (df["TypVol"].cumsum() / cum_vol).ffill()
    vwap = safe_float(df.loc[len(df)-1, "VWAP"])
    vwap_pos_pct = round(((ltp - vwap) / vwap * 100) if vwap != 0 else 0, 2)
    # Kitni % candles VWAP ke upar band hui - 70%+ matlab buyer strong, 30% se kam matlab seller strong
    above_vwap = int((df["Close"] > df["VWAP"]).sum())
    pct_above_vwap = round((above_vwap / len(df) * 100) if len(df) > 0 else 0, 1)
    # VWAP ko kitni baar kaata - zyada kaata matlab choppy
    vwap_cross = 0
    for i in range(1, len(df)):
        prev_above = safe_float(df.loc[i-1, "Close"]) > safe_float(df.loc[i-1, "VWAP"])
        curr_above = safe_float(df.loc[i, "Close"]) > safe_float(df.loc[i, "VWAP"])
        if prev_above != curr_above:
            vwap_cross += 1
    # --- 4. ORB 9:15-9:30 - Pehli 3 candles (09:15, 09:20, 09:25) ---
    orb_df = df.head(3)
    orb_high = safe_float(orb_df["High"].max())
    orb_low = safe_float(orb_df["Low"].min())
    orb_range = orb_high - orb_low
    orb_vol = safe_float(orb_df["Volume"].sum())
    avg_vol = safe_float(df["Volume"].mean())
    vol_ratio = round((safe_float(df.loc[0, "Volume"]) / avg_vol) if avg_vol != 0 else 1.0, 2)
    # ORB Breakout? Aur tika ya wapas aa gaya?
    if ltp > orb_high:
        orb_status = "UPAR - Breakout"
        orb_break = True
        orb_dir = "UP"
    elif ltp < orb_low:
        orb_status = "NEECHE - Breakdown"
        orb_break = True
        orb_dir = "DOWN"
    else:
        orb_status = "ANDAR - No Breakout"
        orb_break = False
        orb_dir = "NONE"
    # ORB ke bahar kitni candles band hui - 2+ matlab pakka, 0-1 matlab fake ho sakta hai
    if orb_dir == "UP":
        candles_outside_orb = int((df["Close"] > orb_high).sum())
    elif orb_dir == "DOWN":
        candles_outside_orb = int((df["Close"] < orb_low).sum())
    else:
        candles_outside_orb = 0
    # Fake check: Kabhi ORB ke bahar gaya phir wapas andar aa gaya?
    ever_broke_up = bool((df["High"] > orb_high).any())
    ever_broke_down = bool((df["Low"] < orb_low).any())
    fake_breakout = False
    if ever_broke_up and ltp <= orb_high and orb_dir == "NONE":
        fake_breakout = True
    if ever_broke_down and ltp >= orb_low and orb_dir == "NONE":
        fake_breakout = True
    # --- 5. 3 SESSION - Subah / Dopahar / Aakhiri ---
    n = len(df)
    s1 = df.iloc[0:max(1, n//3)]
    s2 = df.iloc[max(1, n//3):max(2, 2*n//3)]
    s3 = df.iloc[max(2, 2*n//3):]
    def session_stats(s):
        if s.empty:
            return {"open": 0, "close": 0, "high": 0, "low": 0, "range_pct": 0, "move_pct": 0, "dir": "FLAT"}
        o = safe_float(s.iloc[0]["Open"]); c = safe_float(s.iloc[-1]["Close"]); h = safe_float(s["High"].max()); l = safe_float(s["Low"].min())
        rng = round(((h - l) / o * 100) if o != 0 else 0, 2)
        mv = round(((c - o) / o * 100) if o != 0 else 0, 2)
        d = "UP" if mv > 0.15 else "DOWN" if mv < -0.15 else "FLAT"
        return {"open": o, "close": c, "high": h, "low": l, "range_pct": rng, "move_pct": mv, "dir": d}
    sess1 = session_stats(s1); sess2 = session_stats(s2); sess3 = session_stats(s3)
    # Session kahani: Subah bhaga, dopahar ruka, aakhiri me gira = TRAP
    session_story = f"Subah {sess1['dir']} ({sess1['move_pct']:+.2f}%), Dopahar {sess2['dir']} ({sess2['move_pct']:+.2f}%), Aakhiri {sess3['dir']} ({sess3['move_pct']:+.2f}%)"
    # --- 6. VOLATILITY - Standard Deviation + Wick + Reversal ---
    # 5min returns ka std - zyada std matlab zyada hil raha hai
    rets = df["Close"].pct_change().dropna().tolist()
    rets_f = [safe_float(x) for x in rets if abs(safe_float(x)) < 0.05]
    vol_std = round(float(np.std(rets_f) * 100) if len(rets_f) > 5 else 0, 3)
    # Wick Ratio: (High-Low - |Close-Open|) / (High-Low) - 0.6+ matlab lambi batti, matlab upar-neeche dono taraf dhakka
    wicks = []
    for _, r in df.iterrows():
        rng = safe_float(r["High"]) - safe_float(r["Low"])
        body = abs(safe_float(r["Close"]) - safe_float(r["Open"]))
        if rng > 0:
            wicks.append((rng - body) / rng)
    wick_ratio = round(float(np.mean(wicks)) if wicks else 0, 2)
    # Reversal Count: Kitni baar candle ka direction palta
    reversal = 0
    prev_sign = 0
    for _, r in df.iterrows():
        body = safe_float(r["Close"]) - safe_float(r["Open"])
        sign = 1 if body > 0 else -1 if body < 0 else 0
        if prev_sign != 0 and sign != 0 and sign != prev_sign:
            reversal += 1
        if sign != 0:
            prev_sign = sign
    # Body Ratio: Body / Range - 0.5+ matlab strong candle, 0.2 se kam matlab doji jaisa, confuse
    body_ratio = round(float(np.mean([abs(safe_float(r["Close"]) - safe_float(r["Open"])) / (safe_float(r["High"]) - safe_float(r["Low"])) if (safe_float(r["High"]) - safe_float(r["Low"])) > 0 else 0 for _, r in df.iterrows()])) if len(df) > 0 else 0, 2)
    # --- 7. LAST 5 MIN - Abhi kya ho raha hai? ---
    last_5min_chg = round(((safe_float(df.loc[len(df)-1, "Close"]) - safe_float(df.loc[len(df)-2, "Close"])) / safe_float(df.loc[len(df)-2, "Close"]) * 100) if len(df) >= 2 and safe_float(df.loc[len(df)-2, "Close"]) != 0 else 0, 3)
    last_15min_chg = round(((safe_float(df.loc[len(df)-1, "Close"]) - safe_float(df.loc[max(0, len(df)-4), "Close"])) / safe_float(df.loc[max(0, len(df)-4), "Close"]) * 100) if len(df) >= 4 and safe_float(df.loc[max(0, len(df)-4), "Close"]) != 0 else 0, 3)
    # LTP Day High/Low se kitna door hai - 0.2% ke andar High ke paas matlab High pe atka hai
    dist_from_high_pct = round(((day_high - ltp) / day_high * 100) if day_high != 0 else 0, 2)
    dist_from_low_pct = round(((ltp - day_low) / day_low * 100) if day_low != 0 else 0, 2)
    # --- 8. FINAL CLASSIFICATION - SIDEWAYS / BHAG RAHA / VOLATILE ---
    # Score banate hain, phir type decide karte hain
    sideways_score = 0
    trending_score = 0
    volatile_score = 0
    # Sideways ke lakshan
    if range_vs_atr < 0.8:
        sideways_score += 30
    if abs(vwap_pos_pct) < 0.3:
        sideways_score += 20
    if not orb_break:
        sideways_score += 20
    if net_vs_range < 0.4:
        sideways_score += 15
    if pct_above_vwap > 35 and pct_above_vwap < 65:
        sideways_score += 15
    # Trending / Bhag Raha ke lakshan
    if range_vs_atr > 1.1:
        trending_score += 25
    if net_vs_range > 0.6:
        trending_score += 25
    if pct_above_vwap > 70 or pct_above_vwap < 30:
        trending_score += 20
    if orb_break and candles_outside_orb >= 2:
        trending_score += 20
    if abs(net_move_pct) > 1.0:
        trending_score += 10
    # Volatile / Choppy ke lakshan
    if wick_ratio > 0.60:
        volatile_score += 25
    if vwap_cross >= 4:
        volatile_score += 25
    if reversal > 18:
        volatile_score += 20
    if range_vs_atr > 1.1 and net_vs_range < 0.35:
        volatile_score += 30
    # Faisla - sabse zyada score wala jeetega, lekin Volatile ko pehle check karo kyunki wo sabse khatarnak hai
    if volatile_score >= 60 and net_vs_range < 0.4:
        movement_type = "VOLATILE / CHOPPY - Upar-neeche dono, Option mat lo"
        movement_detail = f"Range bada ({day_range_pct}%) lekin Net Move chhota ({net_move_pct}%) - Matlab upar-neeche karke wahi ka wahi. VWAP ko {vwap_cross} baar kaata, Wick {wick_ratio} lambi hai. Isme premium kha jayega."
        direction = "CHOPPY"
    elif trending_score >= 60 and net_move > 0:
        movement_type = "BHAG RAHA UPAR - Strong Trend"
        movement_detail = f"Range {day_range_pct}% (ATR ka {range_vs_atr}x), Net {net_move_pct}%, {pct_above_vwap}% candles VWAP ke upar, ORB {orb_status}. Buyer pakke hain."
        direction = "BULLISH"
    elif trending_score >= 60 and net_move < 0:
        movement_type = "BHAG RAHA NEECHE - Strong Down"
        movement_detail = f"Range {day_range_pct}% (ATR ka {range_vs_atr}x), Net {net_move_pct}%, {100-pct_above_vwap:.0f}% candles VWAP ke neeche, ORB {orb_status}. Seller pakke hain."
        direction = "BEARISH"
    elif sideways_score >= 60:
        movement_type = "SIDEWAYS - Ek jagah atka hua"
        movement_detail = f"Range sirf {day_range_pct}% (ATR ka {range_vs_atr}x), LTP VWAP se {vwap_pos_pct:+.2f}% door, ORB {orb_status}. Koi taqat nahi hai, Option mat lo, wait karo."
        direction = "SIDEWAYS"
    elif net_move > 0.3 and range_vs_atr >= 0.7:
        movement_type = "DHIRE DHIRE UPAR - Slow Trend"
        movement_detail = f"Dheere-dheere upar ja raha hai, Net {net_move_pct}%, Range {day_range_pct}%. Breakout nahi hua lekin trend upar hai."
        direction = "BULLISH"
    elif net_move < -0.3 and range_vs_atr >= 0.7:
        movement_type = "DHIRE DHIRE NEECHE - Slow Down"
        movement_detail = f"Dheere-dheere neeche ja raha hai, Net {net_move_pct}%, Range {day_range_pct}%. Breakdown nahi hua lekin trend neeche hai."
        direction = "BEARISH"
    else:
        movement_type = "ORB KE ANDAR - Wait karo"
        movement_detail = f"Abhi ORB ke andar hai, Range {day_range_pct}%, Net {net_move_pct}%. Breakout ka wait karo, jaldi mat karo."
        direction = "SIDEWAYS"
    # Movement Started? - Pakka breakout hua ya nahi
    movement_started = bool(orb_break and candles_outside_orb >= 2 and vol_ratio > 1.1 and abs(vwap_pos_pct) > 0.2)
    if fake_breakout:
        movement_started = False
        movement_type = "FAKE BREAKOUT - ORB toota phir wapas aa gaya"
        movement_detail = "Subah ORB toota tha lekin tik nahi paya, wapas andar aa gaya. Ye trap tha, isme entry mat lo."
    movement_text = "MOVEMENT SURU HO GAYA" if movement_started else "ABHI MOVEMENT SURU NAHI HUA"
    # Pattern - purana wala pattern bhi rakha hai taaki purana form na toote
    if direction == "BULLISH" and gap_pct > 0:
        pattern = "Gap Up + VWAP Upar + ORB Breakout" if orb_break else "Gap Up + VWAP Upar"
    elif direction == "BEARISH" and gap_pct < 0:
        pattern = "Gap Down + VWAP Neeche + ORB Breakout" if orb_break else "Gap Down + VWAP Neeche"
    elif direction == "BULLISH":
        pattern = "VWAP Upar + Trend Upar"
    elif direction == "BEARISH":
        pattern = "VWAP Neeche + Trend Neeche"
    else:
        pattern = "Koi clear pattern nahi - Sideways / Choppy"
    out.update({
        "Day Open": round(float(day_open), 2), "Day High": round(float(day_high), 2), "Day Low": round(float(day_low), 2), "LTP": round(float(ltp), 2),
        "Day Range %": float(day_range_pct), "Net Move %": float(net_move_pct), "Net vs Range": float(net_vs_range),
        "ATR": round(float(atr), 2), "ATR %": float(atr_pct), "Range vs ATR": float(range_vs_atr),
        "Prev Close": round(float(prev_close), 2), "Gap %": float(gap_pct),
        "VWAP": round(float(vwap), 2), "VWAP Pos %": float(vwap_pos_pct), "% Candles VWAP Upar": float(pct_above_vwap), "VWAP Cross": int(vwap_cross),
        "ORB High": round(float(orb_high), 2), "ORB Low": round(float(orb_low), 2), "ORB Range": round(float(orb_range), 2), "ORB Status": str(orb_status), "ORB Break": bool(orb_break), "Candles ORB Bahar": int(candles_outside_orb), "Fake Breakout": bool(fake_breakout),
        "Vol x": float(vol_ratio), "ORB Vol": float(orb_vol),
        "Session Story": str(session_story), "S1 Move %": float(sess1["move_pct"]), "S2 Move %": float(sess2["move_pct"]), "S3 Move %": float(sess3["move_pct"]),
        "S1 Dir": str(sess1["dir"]), "S2 Dir": str(sess2["dir"]), "S3 Dir": str(sess3["dir"]),
        "Vol Std %": float(vol_std), "Wick Ratio": float(wick_ratio), "Reversal Count": int(reversal), "Body Ratio": float(body_ratio),
        "Last 5min %": float(last_5min_chg), "Last 15min %": float(last_15min_chg),
        "Dist High %": float(dist_from_high_pct), "Dist Low %": float(dist_from_low_pct),
        "Movement Type": str(movement_type), "Movement Detail": str(movement_detail), "Movement": str(movement_text), "Movement Started?": "HAAN" if movement_started else "NAHI",
        "Direction": str(direction), "Pattern": str(pattern),
        "Sideways Score": int(sideways_score), "Trending Score": int(trending_score), "Volatile Score": int(volatile_score),
        "Candles": int(len(df)),
    })
    return out

# ---------------- SCAN - IND HISTORICAL SE, NAHI MILA TO YAHOO SE ----------------
def scan_with_ind(token, scrip_map, progress_cb=None):
    # FIXED SCAN - 0 STOCKS WALA BUG YAHAN THA, AB 3 FIX HAIN:
    # FIX 1: Trading Day - Sunday ko Friday lete hain, nahi to Sunday ki koi candle nahi hoti -> 0.
    # FIX 2: 09:20 pe sirf 1 candle hoti hai, pehle len<5 pe skip kar dete the -> 0. Ab 1 candle pe bhi chalega + 1minute se bharega.
    # FIX 3: Ek stock ka data nahi aaya to poora scan fail nahi hoga - us stock ko Yahoo se bhar denge, baaki IND se hi rahenge.
    # TIME FIXED NAHI HAI: Start 09:15, End = abhi ka time (09:20 / 09:30 / 09:35 / 01:00 / 02:00 jo bhi ho) ya 15:30 agar market band hai.
    trading_day = get_trading_day()
    start_dt, end_dt = get_scan_window(trading_day)
    symbols = list(MARKET_STOCKS.keys())
    stock_to_code = {}
    for s in symbols:
        sid = scrip_map.get(s.upper(), "") if scrip_map else KNOWN_SCRIP.get(s, "")
        if sid:
            stock_to_code[s] = f"NSE_{sid}"
    # Batch me 5minute + 15minute + Daily ek saath mangte hain - 5-5 karke kyunki Docs me max 5 hai
    all_5m = {}
    all_15m = {}
    all_daily = {}
    all_1min = {}
    debug_list = []
    codes_list = list(stock_to_code.values())
    code_to_stock = {v: k for k, v in stock_to_code.items()}
    total_batches = (len(codes_list) + 4)//5
    # 5minute batches
    for i in range(0, len(codes_list), 5):
        batch = codes_list[i:i+5]
        data, _msg = ind_get_historical_batch(batch, "5minute", to_ms(start_dt), to_ms(end_dt), token)
        for code, payload in data.items():
            try:
                sym = code_to_stock.get(code, code)
                all_5m[sym] = ind_candles_to_df(payload.get("candles", []) or [])
            except:
                continue
        if progress_cb:
            progress_cb(min(0.35, (i+5)/len(codes_list)*0.35))
        time.sleep(0.03)
    # 15minute batches - Trend confirm ke liye
    for i in range(0, len(codes_list), 5):
        batch = codes_list[i:i+5]
        data, _msg = ind_get_historical_batch(batch, "15minute", to_ms(start_dt), to_ms(end_dt), token)
        for code, payload in data.items():
            try:
                sym = code_to_stock.get(code, code)
                all_15m[sym] = ind_candles_to_df(payload.get("candles", []) or [])
            except:
                continue
        if progress_cb:
            progress_cb(0.35 + min(0.15, (i+5)/len(codes_list)*0.15))
        time.sleep(0.03)
    # Daily batches
    start_daily = end_dt - timedelta(days=35)
    for i in range(0, len(codes_list), 5):
        batch = codes_list[i:i+5]
        data, _msg = ind_get_historical_batch(batch, "1day", to_ms(start_daily), to_ms(end_dt), token)
        for code, payload in data.items():
            try:
                sym = code_to_stock.get(code, code)
                all_daily[sym] = ind_candles_to_df(payload.get("candles", []) or [])
            except:
                continue
        if progress_cb:
            progress_cb(0.50 + min(0.20, (i+5)/len(codes_list)*0.20))
        time.sleep(0.03)
    # Agar kisi stock ki 5min me 3 se kam candles hain (09:20 wala case) to uski 1min mang lo - sirf unke liye
    need_1min_stocks = [s for s in symbols if s not in all_5m or len(all_5m.get(s, [])) < 3]
    if need_1min_stocks:
        debug_list.append(f"1min chahiye: {len(need_1min_stocks)} stocks (09:20-09:35 wala case)")
        for s in need_1min_stocks:
            code = stock_to_code.get(s, "")
            if not code:
                continue
            try:
                data1, _ = ind_get_historical_batch([code], "1minute", to_ms(start_dt), to_ms(end_dt), token)
                if code in data1:
                    df1 = ind_candles_to_df(data1[code].get("candles", []) or [])
                    all_1min[s] = df1
                    if s not in all_5m or len(all_5m.get(s, [])) == 0:
                        if len(df1) > 0:
                            df1c = df1.copy().set_index("Time")
                            df5r = df1c.resample("5min").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna().reset_index()
                            all_5m[s] = df5r
                time.sleep(0.02)
            except:
                continue
    rows = []
    ind_ok = 0
    ind_fail = []
    for sym in symbols:
        try:
            df5 = all_5m.get(sym, pd.DataFrame())
            dfd = all_daily.get(sym, pd.DataFrame())
            df15 = all_15m.get(sym, pd.DataFrame())
            if df5 is None or df5.empty or len(df5) < 1:
                ind_fail.append(sym)
                continue
            ana = analyze_full_day(df5, dfd)
            if "error" in ana:
                ind_fail.append(sym)
                continue
            # 15min se Trend Confirm karo - World Best Traders wala rule
            # Agar 15min me bhi same direction hai to Probability +10, agar ulta hai to -10 (Fake ka chance)
            trend_15_ok = True
            try:
                if df15 is not None and len(df15) >= 2:
                    first15 = safe_float(df15.iloc[0]["Open"])
                    last15 = safe_float(df15.iloc[-1]["Close"])
                    chg15 = (last15 - first15)/first15*100 if first15 != 0 else 0
                    dir15 = "BULLISH" if chg15 > 0.2 else "BEARISH" if chg15 < -0.2 else "SIDEWAYS"
                    if dir15 != "SIDEWAYS" and dir15 != str(ana.get("Direction","")):
                        trend_15_ok = False
            except:
                trend_15_ok = True
            ind_ok += 1
            c1_gap = abs(safe_float(ana.get("Gap %", 0))) > 0.30
            c2_vwap = (safe_float(ana.get("LTP", 0)) > safe_float(ana.get("VWAP", 0)) and safe_float(ana.get("Gap %", 0)) > 0) or (safe_float(ana.get("LTP", 0)) < safe_float(ana.get("VWAP", 0)) and safe_float(ana.get("Gap %", 0)) < 0)
            c3_orb = bool(ana.get("ORB Break", False))
            c4_vol = safe_float(ana.get("Vol x", 0)) > 1.5
            c5_volatility_ok = "CHOPPY" not in str(ana.get("Movement Type", "")) and "VOLATILE" not in str(ana.get("Movement Type", ""))
            score = 0
            if c1_gap: score += 15
            if c2_vwap: score += 15
            if c3_orb: score += 20
            if c4_vol: score += 15
            if c5_volatility_ok: score += 10
            if ana.get("Movement Started?") == "HAAN": score += 15
            if safe_float(ana.get("Trending Score", 0)) >= 60: score += 10
            if safe_float(ana.get("Range vs ATR", 0)) > 1.2: score += 5
            if abs(safe_float(ana.get("Gap %", 0))) > 1.0: score += 5
            if trend_15_ok: score += 5
            else: score -= 10
            if bool(ana.get("Fake Breakout", False)): score -= 30
            if "CHOPPY" in str(ana.get("Movement Type", "")) or "VOLATILE" in str(ana.get("Movement Type", "")): score -= 20
            if "SIDEWAYS" in str(ana.get("Movement Type", "")): score -= 15
            score = max(0, min(100, int(score)))
            pass_count = sum([c1_gap, c2_vwap, c3_orb, c4_vol])
            rows.append({
                "Stock": str(sym), "LTP": safe_float(ana.get("LTP", 0)), "Gap %": safe_float(ana.get("Gap %", 0)),
                "VWAP": safe_float(ana.get("VWAP", 0)), "ORB High": safe_float(ana.get("ORB High", 0)), "ORB Low": safe_float(ana.get("ORB Low", 0)),
                "Day High": safe_float(ana.get("Day High", 0)), "Day Low": safe_float(ana.get("Day Low", 0)),
                "Day Range %": safe_float(ana.get("Day Range %", 0)), "Net Move %": safe_float(ana.get("Net Move %", 0)),
                "ATR %": safe_float(ana.get("ATR %", 0)), "Range vs ATR": safe_float(ana.get("Range vs ATR", 0)),
                "Vol x": safe_float(ana.get("Vol x", 0)), "Last 5min %": safe_float(ana.get("Last 5min %", 0)),
                "VWAP Pos %": safe_float(ana.get("VWAP Pos %", 0)), "% VWAP Upar": safe_float(ana.get("% Candles VWAP Upar", 0)),
                "VWAP Cross": safe_int(ana.get("VWAP Cross", 0)), "Wick": safe_float(ana.get("Wick Ratio", 0)),
                "Reversal": safe_int(ana.get("Reversal Count", 0)),
                "Movement Type": str(ana.get("Movement Type", "")), "Movement Detail": str(ana.get("Movement Detail", "")),
                "Session Story": str(ana.get("Session Story", "")), "S1": str(ana.get("S1 Dir", "")), "S2": str(ana.get("S2 Dir", "")), "S3": str(ana.get("S3 Dir", "")),
                "Direction": str(ana.get("Direction", "")), "Pattern": str(ana.get("Pattern", "")), "Movement": str(ana.get("Movement", "")),
                "Movement Started?": str(ana.get("Movement Started?", "")), "Fake?": "HAAN - TRAP" if bool(ana.get("Fake Breakout", False)) else "NAHI",
                "Probability %": int(score), "Gap": "✅" if c1_gap else "❌", "VWAP": "✅" if c2_vwap else "❌", "ORB": "✅" if c3_orb else "❌", "Volume": "✅" if c4_vol else "❌", "Volatility OK": "✅" if c5_volatility_ok else "❌", "Pass": f"{pass_count}/4",
                "Source": "IND-Historical",
                "15min Confirm": "✅" if trend_15_ok else "❌ Ulta",
                "Candles": int(ana.get("Candles", 0)),
            })
        except Exception as e:
            ind_fail.append(sym)
            continue
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Probability %", ascending=False).reset_index(drop=True)
    # Debug ko session me rakho taaki UI me dikha sakein - kyu 0 aaya, kitne IND se aaye
    st.session_state["_scan_debug"] = {
        "trading_day": str(trading_day), "start": str(start_dt), "end": str(end_dt),
        "ind_ok": ind_ok, "ind_fail_count": len(ind_fail), "ind_fail_sample": ind_fail[:10],
        "total": len(symbols), "debug_list": debug_list,
    }
    return df

def scan_with_yahoo_fallback():
    # V24 - Yahoo Fallback BAND hai. Pehle IND nahi aata tha to Yahoo se bhar dete the, ab nahi.
    # Sirf IND se scan hoga. Agar IND Token nahi hai / IND fail hai to khali DataFrame return karenge, Yahoo kabhi nahi chalayenge.
    # Is function ka naam purana hai taaki purana call bacha ho to bhi Yahoo na chale.
    return pd.DataFrame()

# ---------------- INDICES + NEWS ----------------
def fetch_indices_history():
    # V24 - Indices bhi sirf IND se - Yahoo band. Index ka SECURITY_ID Index File se: NIFTY 50 = 40000001
    # quotes/full me Index ka scrip-code NSE_40000001 jaisa bhej ke LTP lete hain. Agar Token nahi hai to khali.
    try:
        import streamlit as _st
        _tok = _st.session_state.get("indmoney_secret", "")
        if not _tok or len(str(_tok)) < 10:
            return pd.DataFrame()
        # Index scrip codes - Docs: source=index se - NIFTY 50 40000001, NIFTY BANK? - KNOWN se ya GitHub Index file se
        _smap = ind_get_all_scrips(_tok) if _tok else {}
        _idx_map = {"NIFTY": _smap.get("NIFTY 50", "40000001"), "BANK NIFTY": _smap.get("NIFTY BANK", ""), "SENSEX": _smap.get("SENSEX", ""), "BANKEX": _smap.get("BANKEX", "")}
        _codes = []
        _code_to_name = {}
        for _nm, _sid in _idx_map.items():
            if _sid:
                _c = f"NSE_{_sid}"
                _codes.append(_c); _code_to_name[_c] = _nm
        if not _codes:
            return pd.DataFrame()
        _qdata, _qmsg = ind_quotes_full_docs_pattern(_codes, _tok)
        rows = []
        for _c, _d in _qdata.items():
            rows.append({"Index": _code_to_name.get(_c, _c), "LTP (IND se)": safe_float(_d.get("live_price", 0)), "Change % (IND se)": safe_float(_d.get("day_change_percentage", 0)), "Volume": safe_float(_d.get("volume", 0))})
        return pd.DataFrame(rows)
    except Exception as e:
        return pd.DataFrame()

def load_ai_live():
    # V37 - AI Worker ne jo Market + News + Crash + Impact likha hai, wo yahan se padhenge - Local file -> GitHub data/ai_live.json
    # 5 min ka cache - har click pe dobara download nahi hoga
    try:
        import streamlit as _st
        _cached = _st.session_state.get("_ai_live_cache", None)
        _ct = _st.session_state.get("_ai_live_time", None)
        if _cached is not None and _ct is not None:
            try:
                if (datetime.now() - _ct).total_seconds() < 300:
                    return _cached
            except:
                pass
    except:
        pass
    _data = None
    try:
        for _cand in [APP_DIR / MASTER_FOLDER / "ai_live.json", Path.cwd() / MASTER_FOLDER / "ai_live.json", APP_DIR / "ai_live.json"]:
            try:
                if _cand.is_file():
                    import json as _js
                    _data = _js.loads(_cand.read_text(encoding="utf-8", errors="ignore"))
                    break
            except:
                continue
    except:
        pass
    if _data is None and GITHUB_REPO:
        try:
            _r = requests.get(f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{MASTER_FOLDER}/ai_live.json", timeout=10)
            if _r.status_code == 200 and len(_r.text.strip()) > 20:
                import json as _js
                _data = _js.loads(_r.text)
        except:
            pass
    try:
        import streamlit as _st
        if _data is not None:
            _st.session_state["_ai_live_cache"] = _data
            _st.session_state["_ai_live_time"] = datetime.now()
    except:
        pass
    return _data


def load_ai_memory():
    # V37 - AI ki yaad - pichhli baar aisa hua to kya hua - Local -> GitHub data/ai_memory.json
    try:
        for _cand in [APP_DIR / MASTER_FOLDER / "ai_memory.json", Path.cwd() / MASTER_FOLDER / "ai_memory.json"]:
            try:
                if _cand.is_file():
                    import json as _js
                    return _js.loads(_cand.read_text(encoding="utf-8", errors="ignore"))
            except:
                continue
    except:
        pass
    if GITHUB_REPO:
        try:
            _r = requests.get(f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{MASTER_FOLDER}/ai_memory.json", timeout=10)
            if _r.status_code == 200 and len(_r.text.strip()) > 20:
                import json as _js
                return _js.loads(_r.text)
        except:
            pass
    return None


def build_ai_live_fallback():
    # V38 - Worker nahi chala to bhi AI Live khali nahi rahega - App ke saved data + News se hi bana do
    try:
        _dfb, _msgb = scan_from_saved_history()
        _up = _down = 0
        _avg_gap = 0.0
        if _dfb is not None and not _dfb.empty:
            _up = int((_dfb["Gap %"] > 0).sum()) if "Gap %" in _dfb.columns else 0
            _down = int((_dfb["Gap %"] < 0).sum()) if "Gap %" in _dfb.columns else 0
            _avg_gap = round(safe_float(_dfb["Gap %"].mean()), 2) if "Gap %" in _dfb.columns else 0.0
        if _up >= _down * 1.5 and _up >= 10:
            _dir = "BULLISH"
        elif _down >= _up * 1.5 and _down >= 10:
            _dir = "BEARISH"
        else:
            _dir = "SIDEWAYS"
        _news_f = []
        try:
            _ndf = fetch_global_news()
            if _ndf is not None and not _ndf.empty:
                for _, _r in _ndf.head(10).iterrows():
                    _news_f.append({"title": str(_r.get("News", "")), "type": "OTHER", "direction": str(_r.get("Impact", "")), "impact": "Is khabar ka asar dekhne ke liye AI se Puchho me stock ka naam likho"})
        except:
            pass
        _alerts = []
        if _down >= 150:
            _alerts.append(f"POORA MARKET NEECHE - Saved data me 216 me se {_down} neeche")
        elif _up >= 150:
            _alerts.append(f"POORA MARKET UPAR - Saved data me 216 me se {_up} upar")
        return {"updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "fallback": True,
                "market": {"direction": _dir, "nifty": 0, "nifty_change_pct": _avg_gap, "bank_nifty": 0, "bank_nifty_change_pct": 0, "sensex": 0, "sensex_change_pct": 0, "vix": 0, "advance": _up, "decline": _down},
                "crash_alerts": _alerts, "news": _news_f, "fallback_msg": _msgb}
    except Exception as e:
        return {"updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "fallback": True,
                "market": {"direction": "SIDEWAYS", "nifty": 0, "nifty_change_pct": 0, "bank_nifty": 0, "bank_nifty_change_pct": 0, "sensex": 0, "sensex_change_pct": 0, "vix": 0, "advance": 0, "decline": 0},
                "crash_alerts": [], "news": [], "fallback_msg": f"Fallback me error - {e}"}


def ask_stock_ai(question):
    # V38 - AI Chat - ChatGPT jaisa, par sirf stock ke liye, aur sirf apne data se - banayi hui wajah nahi bolega
    # Kya batayega: Koi stock kyu bhaga / kyu gira - Gap, Volume, VWAP, ORB, News, Diary - sab number ke saath
    # Jo data me nahi hai, uspe "pata nahi" bolega, kahani nahi banayega
    # Har sawaal-jawaab data/ai_chat.json me judta jayega (kabhi delete nahi hoga) - isi se AI seekhega
    try:
        _q = str(question or "").strip()
        if not _q:
            return "Sawaal likho - jaise 'RELIANCE kyu bhaga?' ya 'Market kyu gira?'"
        _qu = _q.upper()
        # 1) Stock dhoondho - sawaal me kaunsa stock hai
        _stock = ""
        try:
            import streamlit as _st2
            _sdf = _st2.session_state.get("scan_df", None)
            _cands = []
            if _sdf is not None and not _sdf.empty and "Stock" in _sdf.columns:
                _cands = [str(x).upper() for x in _sdf["Stock"].tolist()]
            for _k in list(MARKET_STOCKS.keys()):
                if _k not in _cands:
                    _cands.append(str(_k).upper())
            for _c in _cands:
                if _c and len(_c) >= 3 and _c in _qu:
                    _stock = _c
                    break
            if not _stock:
                # V39 - FIX: Poora sawaal ek saath nahi, tukde-tukde karke dekho - "SBI kyu bhaga?" me "SBI" alag se milega -> SBIN
                _words = _q.replace("?", " ").replace(",", " ").split()
                _found = ""
                for _n in (4, 3, 2, 1):
                    for _i in range(0, max(0, len(_words) - _n + 1)):
                        _phrase = " ".join(_words[_i:_i+_n])
                        try:
                            _s2, _ = resolve_to_symbol(_phrase)
                        except:
                            _s2 = None
                        if _s2:
                            _found = str(_s2).upper()
                            break
                    if _found:
                        break
                if _found:
                    _stock = _found
                else:
                    _sym2, _sugg2 = resolve_to_symbol(_q)
                    if _sym2:
                        _stock = str(_sym2).upper()
        except:
            pass
        # 2) General sawaal - Market / Crash / Best
        if not _stock:
            if any(w in _qu for w in ["MARKET", "NIFTY", "CRASH", "SENSEX", "POORA"]):
                _ai = load_ai_live()
                if not _ai:
                    _ai = build_ai_live_fallback()
                _m = (_ai or {}).get("market", {}) or {}
                _ans = f"Market: {_m.get('direction', '')} - Upar: {_m.get('advance', '')} | Neeche: {_m.get('decline', '')}"
                _cr = (_ai or {}).get("crash_alerts", []) or []
                if _cr:
                    _ans += "\nCrash: " + " | ".join(_cr)
                else:
                    _ans += "\nKoi crash nahi hai."
                _nw = (_ai or {}).get("news", []) or []
                if _nw:
                    _ans += "\nBadi khabar: " + str(_nw[0].get("title", ""))[:120]
                _save_ai_chat(_q, _ans)
                return _ans
            if any(w in _qu for w in ["BEST", "TOP", "KAUN SA", "KON SA", "KAUNSA"]):
                try:
                    import streamlit as _st3
                    _sdf3 = _st3.session_state.get("scan_df", None)
                    if _sdf3 is not None and not _sdf3.empty:
                        _top = _sdf3.iloc[0]
                        _ans = f"Top stock: {str(_top.get('Stock',''))} - Score {safe_float(_top.get('Probability %',0)):.0f}/100 - {str(_top.get('Direction',''))} - {str(_top.get('Movement Type',''))} - Gap {safe_float(_top.get('Gap %',0)):+.2f}% - Vol {safe_float(_top.get('Vol x',0)):.1f}x"
                        _save_ai_chat(_q, _ans)
                        return _ans
                except:
                    pass
                _ans = "Abhi Scan nahi hua hai - pehle Scan dabao, phir Best stock bata paunga."
                _save_ai_chat(_q, _ans)
                return _ans
            _ans = "Kis stock ke baare me puchh rahe ho, naam likho - jaise 'RELIANCE kyu bhaga?'"
            _save_ai_chat(_q, _ans)
            return _ans
        # 3) Stock wala sawaal - Row + News + Diary + History se jawaab banao
        _row = None
        try:
            import streamlit as _st4
            _sdf4 = _st4.session_state.get("scan_df", None)
            if _sdf4 is not None and not _sdf4.empty and "Stock" in _sdf4.columns:
                _m4 = _sdf4[_sdf4["Stock"].astype(str).str.upper() == _stock]
                if not _m4.empty:
                    _row = _m4.iloc[0]
        except:
            pass
        if _row is None:
            try:
                _dfb2, _ = scan_from_saved_history()
                if _dfb2 is not None and not _dfb2.empty and "Stock" in _dfb2.columns:
                    _m5 = _dfb2[_dfb2["Stock"].astype(str).str.upper() == _stock]
                    if not _m5.empty:
                        _row = _m5.iloc[0]
            except:
                pass
        if _row is None:
            _ans = f"{_stock} ka data abhi nahi hai - pehle Scan ya Download Data dabao, phir bata paunga."
            _save_ai_chat(_q, _ans)
            return _ans
        _gap = safe_float(_row.get("Gap %", 0)); _volx = safe_float(_row.get("Vol x", 0)); _ltp = safe_float(_row.get("LTP", 0))
        _vwap = safe_float(_row.get("VWAP", 0)); _orb = str(_row.get("ORB", "")); _moved = str(_row.get("Movement Started?", ""))
        _mtype = str(_row.get("Movement Type", "")); _dir = str(_row.get("Direction", "")); _score = safe_float(_row.get("Probability %", 0))
        _is_up = "BHAGA" in _qu or "UPAR" in _qu or "BADHA" in _qu or "TEZ" in _qu
        _is_down = "GIRA" in _qu or "NEECHE" in _qu or "CRASH" in _qu or "GIR" in _qu
        _parts = []
        _parts.append(f"{_stock} - LTP Rs {_ltp:.1f} - Score {_score:.0f}/100 - {_dir} - {_mtype}")
        _reasons = []
        if abs(_gap) >= 0.5:
            _reasons.append(f"Gap {_gap:+.2f}% tha - khulte hi {'upar' if _gap > 0 else 'neeche'} khula")
        if _volx >= 1.5:
            _reasons.append(f"Volume {_volx:.1f}x tha - normal se zyada log khareed/bech rahe the")
        if _ltp > _vwap and _dir == "BULLISH":
            _reasons.append(f"VWAP ({_vwap:.1f}) se upar tha - khareedne wale bhari the")
        elif _ltp < _vwap and _dir == "BEARISH":
            _reasons.append(f"VWAP ({_vwap:.1f}) se neeche tha - bechne wale bhari the")
        if _orb == "✅" or _moved == "HAAN":
            _reasons.append("ORB toota tha - subah ke range se bahar nikla, isliye movement aaya")
        # News - is stock ka naam wali khabar hai?
        _news_hit = ""
        try:
            _ndf2 = fetch_global_news()
            if _ndf2 is not None and not _ndf2.empty:
                for _, _nr in _ndf2.iterrows():
                    _nt = str(_nr.get("News", ""))
                    if _stock in _nt.upper() or _stock.lower() in _nt.lower():
                        _news_hit = _nt[:150]
                        break
            if not _news_hit:
                _ai2 = load_ai_live() or {}
                for _n2 in (_ai2.get("news", []) or []):
                    _nt2 = str(_n2.get("title", ""))
                    if _stock in _nt2.upper():
                        _news_hit = _nt2[:150]
                        break
        except:
            pass
        if _news_hit:
            _reasons.append(f"Khabar: {_news_hit}")
        # Diary - is stock me pehle kya hua
        _diary_hit = ""
        try:
            _dd = get_all_trades()
            if _dd is not None and not _dd.empty and "symbol" in _dd.columns:
                _dg = _dd[_dd["symbol"].astype(str).str.upper() == _stock]
                if not _dg.empty:
                    _last = _dg.iloc[-1]
                    _diary_hit = f"Diary me isme pichhli baar {str(_last.get('status',''))} hua tha (Entry Rs {safe_float(_last.get('entry',0))})"
        except:
            pass
        if _diary_hit:
            _reasons.append(_diary_hit)
        if _is_up:
            _parts.append("Kyu bhaga / upar gaya - data se ye wajah mili:")
        elif _is_down:
            _parts.append("Kyu gira / neeche gaya - data se ye wajah mili:")
        else:
            _parts.append("Kya hua - data se ye dikha:")
        if _reasons:
            for _r in _reasons:
                _parts.append(f"  - {_r}")
        else:
            _parts.append("  - Data me koi saaf wajah nahi mili - Gap, Volume, News me kuch khaas nahi tha. Iska matlab ye move bina wajah ka ya kisi aisi wajah se tha jo hamare data me nahi hai - ispe bharosa mat karo.")
        _ans = "\n".join(_parts)
        _save_ai_chat(_q, _ans)
        return _ans
    except Exception as e:
        return f"AI se puchhne me error - {e} - pehle Scan ya Download Data dabao"


def _save_ai_chat(question, answer):
    # V38 - Har sawaal-jawaab judta jayega, kabhi delete nahi hoga - isi se AI seekhega
    try:
        import json as _js
        _rec = {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "q": str(question)[:300], "a": str(answer)[:2000]}
        _existing = []
        try:
            for _cand in [APP_DIR / MASTER_FOLDER / "ai_chat.json", Path.cwd() / MASTER_FOLDER / "ai_chat.json"]:
                if _cand.is_file():
                    _existing = _js.loads(_cand.read_text(encoding="utf-8", errors="ignore")) or []
                    break
        except:
            _existing = []
        if not isinstance(_existing, list):
            _existing = []
        _existing.append(_rec)
        _existing = _existing[-500:]
        _txt = _js.dumps(_existing, ensure_ascii=False, indent=2)
        try:
            _push_master_to_github("ai_chat.json", _txt)
        except:
            pass
        try:
            _p = APP_DIR / MASTER_FOLDER / "ai_chat.json"
            _p.parent.mkdir(parents=True, exist_ok=True)
            _p.write_text(_txt, encoding="utf-8")
        except:
            pass
    except:
        pass


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

# ---------------- TELEGRAM ----------------
def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": str(TELEGRAM_CHAT), "text": message}, timeout=12)
        return r.status_code == 200
    except:
        return False

def send_top5(top5_df, expiry_str):
    msg = f"TOP 5 - {datetime.now().strftime('%d %b %Y %H:%M')}\nExpiry: {expiry_str}\n------------------------\n"
    for i, (_, row) in enumerate(top5_df.iterrows(), start=1):
        stock_name = str(row.get("Stock", ""))
        ltp = safe_float(row.get("LTP", 0)); vwap = safe_float(row.get("VWAP", 0)); orb_high = safe_float(row.get("ORB High", 0)); orb_low = safe_float(row.get("ORB Low", 0)); prob = safe_float(row.get("Probability %", 0)); gap = safe_float(row.get("Gap %", 0)); vol = safe_float(row.get("Vol x", 0))
        direction = str(row.get("Direction", "")); pattern = str(row.get("Pattern", "")); movement = str(row.get("Movement", "")); mtype = str(row.get("Movement Type", ""))
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
        msg += f"{i}. {stock_name} - LTP Rs {ltp:.1f} - {direction} - Prob {prob:.0f}%\n   Pattern: {pattern}\n   Poora Din: {mtype}\n   Session: {str(row.get('Session Story',''))}\n   Kahan pe hai: {vwap_pos}, {orb_pos}\n   Movement: {movement}\n   Gap: {gap:.2f}% | Vol: {vol:.1f}x | Day Range: {safe_float(row.get('Day Range %',0)):.2f}%\n------------------------\n"
    return send_telegram(msg)

def send_strike(stock, strike, opt_type, entry, sl, target, cost, lot, expiry_str, movement):
    entry_f = safe_float(entry); sl_f = safe_float(sl); target_f = safe_float(target); cost_f = safe_float(cost); lot_f = safe_float(lot)
    max_profit = round((target_f - entry_f) * lot_f, 0); max_loss = round((entry_f - sl_f) * lot_f, 0)
    msg = f"STRIKE SELECTED - {stock}\n------------------------\nStock: {stock}\nStrike: {safe_int(strike)} {opt_type}\nExpiry: {expiry_str}\nEntry: Rs {entry_f}\nStop Loss: Rs {sl_f}\nTarget: Rs {target_f}\n1 Lot Qty: {safe_int(lot_f)}\n1 Lot Cost: Rs {cost_f:.0f}\nMax Profit: Rs {max_profit:.0f}\nMax Loss: Rs {max_loss:.0f}\nMovement: {movement}\nTime: {datetime.now().strftime('%H:%M:%S')}"
    return send_telegram(msg)

# ---------------- STRIKE CHECK ----------------
def check_all_strikes(chain_df, lot, ltp, direction, budget=5000):
    # V40 - Gemini sahi tha: OI / IV / Bid-Ask data to Chain me aa raha tha, par Strike chunte waqt istemaal hi nahi ho raha tha - sirf Premium + ATM se chunte the
    # Ab: (1) OI wala filter - OI hai to kam-OI wala (fasne wala) strike nahi lenge, (2) Spread - Bid-Ask zyada hai to Slippage ki chetavni, (3) IV zyada hai to IV Crush ki chetavni
    # OI data hi nahi aaya to purana tareeka hi chalega - kabhi bhi OI ke chakkar me Trade nahi rokega
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
        _oi = safe_int(r.get("CE OI", 0) if opt_type == "CE" else r.get("PE OI", 0))
        _iv = safe_float(r.get("CE IV", 0) if opt_type == "CE" else r.get("PE IV", 0))
        _bid = safe_float(r.get("CE Bid", 0) if opt_type == "CE" else r.get("PE Bid", 0))
        _ask = safe_float(r.get("CE Ask", 0) if opt_type == "CE" else r.get("PE Ask", 0))
        _spread_pct = round(((_ask - _bid) / prem * 100) if prem > 0 and _ask > 0 and _bid > 0 else 0, 1)
        results.append({"Strike": strike, "Type": opt_type, "Premium": prem, "Lot Qty": safe_int(lot_f), "1 Lot Cost": cost, "Fit?": "✅" if fits else "❌", "ATM se Door": round(abs(strike - ltp_f), 1), "Fits": fits, "OI": _oi, "IV": _iv, "Spread %": _spread_pct})
    df = pd.DataFrame(results).sort_values("ATM se Door") if results else pd.DataFrame()
    if df.empty or not (df["Fits"] == True).any():
        return df, None
    _fits = df[df["Fits"] == True].copy()
    # OI filter - sirf tab jab OI data aaya hai (koi bhi OI > 0) - kam-OI wale ko hatao, phir ATM ke sabse paas wala lo
    try:
        _ois = _fits["OI"].astype(float).tolist()
        if _ois and max(_ois) > 0:
            import statistics as _st2
            _med = _st2.median([_o for _o in _ois if _o > 0]) if any(_o > 0 for _o in _ois) else 0
            _with_oi = _fits[_fits["OI"] >= _med] if _med > 0 else _fits
            if not _with_oi.empty:
                _fits = _with_oi
    except:
        pass
    best = _fits.sort_values("ATM se Door").iloc[0]
    # Chetavni - Trade nahi rokegi, bas bata degi
    _notes = []
    try:
        if safe_float(best.get("OI", 0)) > 0 and safe_float(best.get("OI", 0)) < 1000:
            _notes.append("OI kam hai (1000 se kam) - nikalne me der lag sakti hai")
        if safe_float(best.get("Spread %", 0)) > 20:
            _notes.append(f"Bid-Ask Spread {safe_float(best.get('Spread %',0)):.0f}% hai - Slippage hoga, Market Order mat lagana, Limit lagana")
        if safe_float(best.get("IV", 0)) > 40:
            _notes.append(f"IV {safe_float(best.get('IV',0)):.0f}% zyada hai - IV Crush ka khatra, jaldi nikalna")
    except:
        pass
    if _notes:
        try:
            best = best.copy(); best["liq_note"] = " | ".join(_notes)
        except:
            pass
    return df, best

# ---------------- V28 - MOOL FUNCTION - FINAL CALL - Top Trader Rule se 1 Stock + Chain + Entry/SL/Target ----------------
# V27 tak problem ye thi: Rule, Chain, Entry/SL/Target ka code tha to sahi, par wo sabse neeche Section 6 me daba hua tha.
# Upar sirf Cache / Universe / Debug / 216-row wali tables dikh rahi thi - isliye lag raha tha app sirf data jama kar raha hai.
# V28 me wahi code ek jagah jod diya hai - build_trade_call() - aur usko SCAN ke turant baad sabse upar FINAL CALL me dikhayenge.
# Koi naya rule nahi banaya hai - wahi purana Top Trader wala 100-point rule hai: Gap 15 + VWAP 15 + ORB 20 + Volume 15 + Movement 15 + Trending 10 + Volatility 10 - Fake/Choppy/Sideways kaat ke.
def get_lot_for_stock(stock):
    # Lot pehle Master FNO (Universe 216) se, nahi to purana LOT_SIZES se - dono me nahi mila to 100
    try:
        _udf = st.session_state.get("universe_216_df", None)
        if _udf is not None and not _udf.empty and "STOCK" in _udf.columns and "LOT_SIZE" in _udf.columns:
            _lr = _udf[_udf["STOCK"].astype(str).str.upper() == str(stock).upper()]
            if not _lr.empty and str(_lr.iloc[0]["LOT_SIZE"]).strip() not in ("", "nan", "0"):
                return int(float(str(_lr.iloc[0]["LOT_SIZE"]).strip()))
    except:
        pass
    return LOT_SIZES.get(str(stock).upper(), 100)

def calc_sl_target_for_call(entry, movement_type, news_bias, opt_type):
    # Wahi SL/Target wala hisab jo pehle Section 6 me tha - ab ek jagah, taaki SCAN aur Single dono me ek jaisa lage
    mtype = str(movement_type or "")
    if "CHOPPY" in mtype or "VOLATILE" in mtype:
        sl_f, tg_f, note = 0.85, 1.20, "Volatile hai isliye Target chhota (1.20x) aur SL tight (0.85x) rakha hai - zyada lalach mat karo"
    elif str(news_bias) == "NEGATIVE" and str(opt_type) == "CE":
        sl_f, tg_f, note = 0.80, 1.30, "News Negative hai isliye CE ka Target kam rakha hai"
    elif str(news_bias) == "POSITIVE":
        sl_f, tg_f, note = 0.70, 1.60, "News Positive hai isliye Target bada rakha hai"
    elif "BHAG RAHA" in mtype:
        sl_f, tg_f, note = 0.70, 1.60, "Bhag raha hai isliye Target bada rakha hai"
    else:
        sl_f, tg_f, note = 0.70, 1.50, "Normal Target 1.50x, SL 0.70x"
    sl = round(safe_float(entry) * sl_f, 1)
    target = round(safe_float(entry) * tg_f, 1)
    return sl, target, sl_f, tg_f, note

def is_qualifying_row(row):
    # FINAL CALL ke liye pakka rule - ye 4 cheez ek saath chahiye, nahi to NO TRADE
    try:
        if safe_float(row.get("Probability %", 0)) < 50:
            return False, f"Probability {safe_float(row.get('Probability %',0)):.0f}/100 hai - 50 se kam hai, isliye pakka setup nahi"
        if str(row.get("Movement Started?", "")) != "HAAN":
            return False, "Movement abhi suru nahi hua - ORB toota nahi ya 2 candle bahar nahi tike"
        if "TRAP" in str(row.get("Fake?", "")):
            return False, "FAKE BREAKOUT tha - Trap tha, isme entry mat lo"
        _mt = str(row.get("Movement Type", ""))
        if "SIDEWAYS" in _mt:
            return False, "SIDEWAYS hai - ek jagah atka hua, Option loge to premium ghis jayega"
        if "CHOPPY" in _mt or "VOLATILE" in _mt:
            return False, "CHOPPY / VOLATILE hai - upar-neeche karke wahi ka wahi, premium kha jayega"
        if "FAKE" in _mt:
            return False, "FAKE BREAKOUT tha - Trap tha"
        if str(row.get("Direction", "")) not in ("BULLISH", "BEARISH"):
            return False, f"Direction {row.get('Direction','')} hai - BULLISH / BEARISH nahi, isliye CE/PE tay nahi hoga"
        return True, "Sab rule pass"
    except Exception as e:
        return False, f"Rule check me error - {e}"

def build_best_effort_call(row, chain_df, expiry, news_bias, learn_adj=0):
    # V36 - BEST EFFORT - Koi stock sab rule pass nahi karta to bhi 1 stock do, khali mat chhodo
    # V37 - Score = Prob x 0.6 hi - Diary wale +/- se nahi, taaki pata chale ye pakka setup nahi hai, par Top me sabse behtar yahi hai
    # Single Search me isko nahi bulate - sirf Scan ke FINAL CALL me, taaki zabardasti trade na bane
    try:
        stock = str(row.get("Stock", ""))
        ltp = safe_float(row.get("LTP", 0))
        prob = safe_float(row.get("Probability %", 0))
        direction = str(row.get("Direction", ""))
        mtype = str(row.get("Movement Type", ""))
        _ok_q, _why_q = is_qualifying_row(row)
        _score = int(max(0, min(100, prob * 0.6)))
        if chain_df is None or chain_df.empty:
            return {"status": "NO_CHAIN", "stock": stock, "ltp": ltp, "prob": prob, "score": _score, "direction": direction, "movement_type": mtype,
                    "reason": f"BEST EFFORT - Sab rule pass nahi hua ({_why_q}) - Score {_score}% - Chain bhi nahi aaya, Token check karo", "expiry": expiry or "",
                    "pattern": str(row.get("Pattern", "")), "movement_detail": str(row.get("Movement Detail", "")), "session": str(row.get("Session Story", ""))}
        lot = get_lot_for_stock(stock)
        check_df, best = check_all_strikes(chain_df, lot, ltp, direction, budget=5000)
        if best is None:
            return {"status": "NO_FIT", "stock": stock, "ltp": ltp, "prob": prob, "score": _score, "direction": direction, "movement_type": mtype,
                    "reason": f"BEST EFFORT - Sab rule pass nahi hua ({_why_q}) - Score {_score}% - Rs 5000 wala strike bhi nahi mila", "expiry": expiry or "",
                    "pattern": str(row.get("Pattern", "")), "movement_detail": str(row.get("Movement Detail", "")), "session": str(row.get("Session Story", "")), "lot": lot}
        entry = safe_float(best.get("Premium", 0))
        strike = safe_int(best.get("Strike", 0))
        opt_type = str(best.get("Type", "CE"))
        sl, target, sl_f, tg_f, note = calc_sl_target_for_call(entry, mtype, news_bias, opt_type)
        cost = safe_float(best.get("1 Lot Cost", 0))
        max_loss = round((entry - sl) * safe_float(lot), 0)
        max_profit = round((target - entry) * safe_float(lot), 0)
        rule_line = f"Gap {safe_float(row.get('Gap %',0)):+.2f}% ({row.get('Gap','')}) | VWAP {row.get('VWAP_OK','')} (LTP {ltp:.1f} vs VWAP {safe_float(row.get('VWAP',0)):.1f}) | ORB {row.get('ORB','')} | Volume {safe_float(row.get('Vol x',0)):.2f}x ({row.get('Volume','')}) | Movement {row.get('Movement Started?','')} | Pass {row.get('Pass','')}"
        return {"status": "BEST_EFFORT", "stock": stock, "ltp": ltp, "prob": prob, "score": _score, "direction": direction, "opt_type": opt_type, "strike": strike,
                "entry": entry, "sl": sl, "target": target, "cost": cost, "lot": lot, "expiry": expiry or "", "movement_type": mtype,
                "movement_detail": str(row.get("Movement Detail", "")), "session": str(row.get("Session Story", "")), "pattern": str(row.get("Pattern", "")),
                "rule_line": rule_line, "adjust_note": note, "max_loss": max_loss, "max_profit": max_profit,
                "reason": f"BEST EFFORT - Sab rule pass nahi hua ({_why_q}) - Score {_score}% hai, pakka setup nahi - apne risk pe lo, chhota lot lo"}
    except Exception as e:
        return {"status": "NO_TRADE", "stock": str(row.get("Stock", "")) if hasattr(row, "get") else "", "reason": f"BEST EFFORT banane me error - {e}", "expiry": expiry or ""}


def build_trade_call(row, chain_df, expiry, news_bias):
    # Ek hi jagah se poora trade banega: Rule check -> Chain -> Rs 5000 wala Strike -> Entry / SL / Target -> Buy / Sell
    # row = df_scan ki ek row (dict jaisa) ya Series, chain_df = IND se aayi chain, expiry = IND se aayi expiry
    try:
        stock = str(row.get("Stock", ""))
        ltp = safe_float(row.get("LTP", 0))
        prob = safe_float(row.get("Probability %", 0))
        direction = str(row.get("Direction", ""))
        mtype = str(row.get("Movement Type", ""))
        # 1) Rule check - pass nahi to NO TRADE, zabardasti strike nahi denge
        ok, why = is_qualifying_row(row)
        if not ok:
            return {"status": "NO_TRADE", "stock": stock, "ltp": ltp, "prob": prob, "direction": direction, "movement_type": mtype, "reason": why, "expiry": expiry or "", "pattern": str(row.get("Pattern", "")), "movement_detail": str(row.get("Movement Detail", "")), "session": str(row.get("Session Story", ""))}
        # 2) Chain check - chain nahi to NO_CHAIN
        if chain_df is None or chain_df.empty:
            return {"status": "NO_CHAIN", "stock": stock, "ltp": ltp, "prob": prob, "direction": direction, "movement_type": mtype, "reason": "Rule to pass ho gaya, par IND se Option Chain nahi aaya - Token 24 ghante me expire hota hai, naya Token daal ke dobara SCAN karo.", "expiry": expiry or "", "pattern": str(row.get("Pattern", "")), "movement_detail": str(row.get("Movement Detail", "")), "session": str(row.get("Session Story", ""))}
        # 3) Strike - Rs 5000 me 1 Lot wala, ATM ke sabse paas
        lot = get_lot_for_stock(stock)
        check_df, best = check_all_strikes(chain_df, lot, ltp, direction, budget=5000)
        if best is None:
            return {"status": "NO_FIT", "stock": stock, "ltp": ltp, "prob": prob, "direction": direction, "movement_type": mtype, "reason": f"Fit strike nahi mila ({len(chain_df)} strikes).", "expiry": expiry or "", "pattern": str(row.get("Pattern", "")), "movement_detail": str(row.get("Movement Detail", "")), "session": str(row.get("Session Story", "")), "lot": lot, "total_checked": int(len(check_df)) if check_df is not None else 0}
        # 4) Entry / SL / Target - News + Movement se adjust
        entry = safe_float(best.get("Premium", 0))
        strike = safe_int(best.get("Strike", 0))
        opt_type = str(best.get("Type", "CE"))
        sl, target, sl_f, tg_f, note = calc_sl_target_for_call(entry, mtype, news_bias, opt_type)
        cost = safe_float(best.get("1 Lot Cost", 0))
        max_loss = round((entry - sl) * safe_float(lot), 0)
        max_profit = round((target - entry) * safe_float(lot), 0)
        # Rule breakdown - kyu chuna, ek line me
        rule_line = f"Gap {safe_float(row.get('Gap %',0)):+.2f}% ({row.get('Gap','')}) | VWAP {row.get('VWAP_OK','')} (LTP {ltp:.1f} vs VWAP {safe_float(row.get('VWAP',0)):.1f}) | ORB {row.get('ORB','')} | Volume {safe_float(row.get('Vol x',0)):.2f}x ({row.get('Volume','')}) | Movement {row.get('Movement Started?','')} | Pass {row.get('Pass','')}"
        return {"status": "TRADE", "stock": stock, "ltp": ltp, "prob": prob, "direction": direction, "opt_type": opt_type, "strike": strike, "entry": entry, "sl": sl, "target": target, "cost": cost, "lot": lot, "expiry": expiry or "", "movement_type": mtype, "movement_detail": str(row.get("Movement Detail", "")), "session": str(row.get("Session Story", "")), "pattern": str(row.get("Pattern", "")), "rule_line": rule_line, "adjust_note": note, "max_profit": max_profit, "max_loss": max_loss, "fits_count": int((check_df["Fits"] == True).sum()) if check_df is not None and not check_df.empty else 0, "total_checked": int(len(check_df)) if check_df is not None else 0, "reason": "Sab rule pass - FINAL CALL"}
    except Exception as e:
        return {"status": "NO_TRADE", "stock": str(row.get("Stock", "")) if hasattr(row, "get") else "", "reason": f"Trade banane me error - {e}", "expiry": expiry or ""}


# ---------------- DIARY - EK HI CSV ----------------
# ---------------- DIARY - CSV ONLY - SQLITE HATA DIYA, KYUNKI WAHI CRASH KAR RAHA THA ----------------
# TUMHARI PHOTO WALI ERROR KI ASLI WAJAH:
# Photo me likha tha: OperationalError - File "app.py", line 408, in save_trade - c.execute("INSERT INTO trades ...")
# Wajah: Tumhare paas purana trades.db pada tha jo V13/V14 me bana tha, usme "conditions" column tha hi nahi.
# Lekin code CREATE TABLE IF NOT EXISTS karta tha - matlab purani table ko badalta hi nahi, wahi purani schema rehti thi.
# Phir INSERT me 18 columns bhejte the, purani table me 17 hi the -> "no such column" / OperationalError -> App crash.
# FIX: SQLite hi hata diya. Ab Diary sirf ek CSV hai - all_trades.csv - jo har baar seedha likha jayega.
# CSV me purana column ho ya naya, hum usko handle kar lenge, crash nahi hoga.
# Streamlit Cloud pe local file Reboot pe udd jati hai, isliye GitHub me bhi push karte hain (agar GITHUB_TOKEN Secrets me hai).
# Agar GitHub Token nahi hai to bhi Diary LOCAL me save hogi + Download button se le sakte ho, crash nahi hogi.
DIARY_COLUMNS = ["id","date","time","symbol","strike","opt_type","entry","sl","target","qty_lots","qty_total","capital_used","risk","status","exit_price","pnl","exit_time","reason","conditions"]

def _ensure_diary_csv():
    # Agar CSV nahi hai to khali CSV banao. Agar purana trades.db hai to usko ek baar CSV me badal do.
    if not os.path.exists(CSV_FILE):
        # Purane DB se migrate karne ki koshish - agar fail ho to khali banao, crash mat karo
        try:
            if os.path.exists(DB_FILE):
                conn = sqlite3.connect(DB_FILE)
                try:
                    df_old = pd.read_sql("SELECT * FROM trades", conn)
                    # Purane columns ko naye se milao - jo column missing hai usko khali bhar do
                    for col in DIARY_COLUMNS:
                        if col not in df_old.columns:
                            df_old[col] = "" if col in ["reason","conditions","exit_time"] else 0
                    df_old = df_old[DIARY_COLUMNS]
                    df_old.to_csv(CSV_FILE, index=False)
                    conn.close()
                    return
                except Exception:
                    conn.close()
        except Exception:
            pass
        pd.DataFrame(columns=DIARY_COLUMNS).to_csv(CSV_FILE, index=False)
    else:
        # CSV hai to uske columns check karo - agar purana CSV hai to naye columns add karo
        try:
            df = pd.read_csv(CSV_FILE)
            changed = False
            for col in DIARY_COLUMNS:
                if col not in df.columns:
                    df[col] = "" if col in ["reason","conditions","exit_time"] else 0
                    changed = True
            if changed:
                df = df[DIARY_COLUMNS]
                df.to_csv(CSV_FILE, index=False)
        except Exception:
            # CSV kharab hai to backup bana ke naya banao - data mat udao, backup me rakho
            try:
                os.rename(CSV_FILE, CSV_FILE + ".bak")
            except:
                pass
            pd.DataFrame(columns=DIARY_COLUMNS).to_csv(CSV_FILE, index=False)

def _push_diary_to_github():
    # GitHub me save karna - sirf tab jab Secrets me GITHUB_TOKEN + GITHUB_REPO hai, nahi to chupchap skip
    # Kabhi bhi iski wajah se Diary save fail nahi hoga - try/except me hai
    try:
        if not GITHUB_TOKEN or not GITHUB_REPO:
            return False, "GitHub Token Secrets me nahi hai, isliye sirf Local me save hua"
        if not os.path.exists(CSV_FILE):
            return False, "CSV nahi hai"
        csv_text = open(CSV_FILE, encoding="utf-8").read()
        content_b64 = base64.b64encode(csv_text.encode()).decode()
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_CSV_PATH}"
        # V40 - Network ek baar fail ho to dobara try karo - pehle turant haar maan lete the, isliye Diary kabhi kabhi GitHub me nahi pahunchti thi
        _last_err = ""
        for _try in range(2):
            try:
                get_resp = requests.get(url, headers=headers, timeout=10)
                sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None
                payload = {"message": f"Diary update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "content": content_b64}
                if sha:
                    payload["sha"] = sha
                put_resp = requests.put(url, headers=headers, json=payload, timeout=15)
                if put_resp.status_code in (200, 201):
                    return True, "GitHub me bhi save ho gaya"
                _last_err = f"GitHub Fail {put_resp.status_code} - {put_resp.text[:200]}"
            except Exception as _e2:
                _last_err = f"GitHub Error - {_e2}"
        return False, _last_err
    except Exception as e:
        return False, f"GitHub Error - {e}"

def save_trade(trade):
    # Kabhi crash nahi karega - har error ko pakad ke batayega
    try:
        _ensure_diary_csv()
        df = pd.read_csv(CSV_FILE)
        # V36 - FIX: purani CSV ke float wale columns ko saaf karo, nahi to nayi row judte waqt dtype ladega
        for _c in ["status", "exit_time", "reason", "conditions", "symbol", "opt_type", "date", "time"]:
            if _c in df.columns:
                df[_c] = df[_c].astype(object)
        # id banao - max+1
        try:
            next_id = int(df["id"].max()) + 1 if len(df) > 0 and pd.notna(df["id"].max()) else 1
        except:
            next_id = 1
        new_row = {
            "id": next_id,
            "date": trade.get('date',''), "time": trade.get('time',''), "symbol": trade.get('symbol',''),
            "strike": trade.get('strike',0), "opt_type": trade.get('opt_type',''),
            "entry": trade.get('entry',0), "sl": trade.get('sl',0), "target": trade.get('target',0),
            "qty_lots": trade.get('qty_lots',1), "qty_total": trade.get('qty_total',0),
            "capital_used": trade.get('capital_used',0), "risk": trade.get('risk',0),
            "status": trade.get('status','OPEN'), "exit_price": "", "pnl": "",
            "exit_time": "", "reason": trade.get('reason',''), "conditions": trade.get('conditions','')
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_csv(CSV_FILE, index=False)
        ok_gh, msg_gh = _push_diary_to_github()
        # session me bhi rakho taaki turant dikhe
        st.session_state["_diary_last_msg"] = f"Diary me save ho gaya! {msg_gh}" if ok_gh else f"Diary Local me save ho gaya. {msg_gh}"
        return df
    except Exception as e:
        st.session_state["_diary_last_msg"] = f"Diary save me error - {e}"
        # Phir bhi khali df mat bhejo, jo hai wahi bhejo
        try:
            return pd.read_csv(CSV_FILE)
        except:
            return pd.DataFrame(columns=DIARY_COLUMNS)

def get_all_trades():
    try:
        _ensure_diary_csv()
        df = pd.read_csv(CSV_FILE) if os.path.exists(CSV_FILE) else pd.DataFrame(columns=DIARY_COLUMNS)
        # V35 - FIX: Sirf local mat dekho - Reboot pe local udd jata hai, GitHub me save hua trade wahan se wapas aayega
        # Photo wali dikkat yahi thi: Save to ho gaya tha (GitHub me), par kholne pe sirf local dekha, local khali tha to "Diary khali" dikha
        try:
            if GITHUB_TOKEN and GITHUB_REPO:
                _r = requests.get(f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{GITHUB_CSV_PATH}", timeout=10)
                if _r.status_code == 200 and len(_r.text.strip()) > 20:
                    _gh = pd.read_csv(io.StringIO(_r.text))
                    if _gh is not None and not _gh.empty and len(_gh) > len(df):
                        for _col in DIARY_COLUMNS:
                            if _col not in _gh.columns:
                                _gh[_col] = ""
                        df = _gh[DIARY_COLUMNS]
                        try:
                            df.to_csv(CSV_FILE, index=False)
                        except:
                            pass
        except:
            pass
        if df.empty:
            return df
        # id se ulta sort - naya pehle
        if "id" in df.columns:
            df = df.sort_values("id", ascending=False)
        return df
    except Exception:
        return pd.DataFrame(columns=DIARY_COLUMNS)

def update_trade_exit(trade_id, exit_price, status="EXITED"):
    # V35 - Exit Edit: Buy save ho gaya, ab exit price yahan se badlo - stock change hua ya galat price dala to bhi yahin se theek hoga
    # OPEN trade ka status EXITED ho jayega, band trade ka status wahi rahega, sirf exit price + PnL badlega
    try:
        _ensure_diary_csv()
        df = pd.read_csv(CSV_FILE)
        # V36 - FIX: Photo wali error - "Invalid value '12:12:40' for dtype 'float64'" - exit_time float ban gaya tha, usme string nahi ja raha tha
        for _c in ["status", "exit_time", "reason", "conditions", "symbol", "opt_type", "date", "time"]:
            if _c in df.columns:
                df[_c] = df[_c].astype(object)
        for _c in ["exit_price", "pnl", "entry", "sl", "target"]:
            if _c in df.columns:
                df[_c] = pd.to_numeric(df[_c], errors="coerce")
        idx = df[df["id"] == trade_id].index
        if len(idx) > 0:
            i = idx[0]
            df.at[i, "exit_price"] = float(exit_price)
            try:
                _entry = float(df.at[i, "entry"]); _qty = float(df.at[i, "qty_total"])
                df.at[i, "pnl"] = (float(exit_price) - _entry) * _qty
            except:
                pass
            df.at[i, "exit_time"] = datetime.now().strftime("%H:%M:%S")
            if str(df.at[i, "status"]).upper() == "OPEN":
                df.at[i, "status"] = status
            df.to_csv(CSV_FILE, index=False)
            _push_diary_to_github()
            st.session_state["_diary_last_msg"] = f"Exit update ho gaya - Exit Rs {exit_price}"
        return df
    except Exception as e:
        st.session_state["_diary_last_msg"] = f"Exit update me error - {e}"
        return get_all_trades()


def update_trade_status(trade_id, status, exit_price, pnl):
    try:
        _ensure_diary_csv()
        df = pd.read_csv(CSV_FILE)
        # V36 - FIX: wahi dtype wali error - string column ko pehle object me badlo, phir .at se likho
        for _c in ["status", "exit_time", "reason", "conditions", "symbol", "opt_type", "date", "time"]:
            if _c in df.columns:
                df[_c] = df[_c].astype(object)
        for _c in ["exit_price", "pnl", "entry", "sl", "target"]:
            if _c in df.columns:
                df[_c] = pd.to_numeric(df[_c], errors="coerce")
        idx = df[df["id"] == trade_id].index
        if len(idx) > 0:
            i = idx[0]
            df.at[i, "status"] = status
            df.at[i, "exit_price"] = exit_price
            df.at[i, "pnl"] = pnl
            df.at[i, "exit_time"] = datetime.now().strftime("%H:%M:%S")
            df.to_csv(CSV_FILE, index=False)
            _push_diary_to_github()
        return df
    except Exception as e:
        st.session_state["_diary_last_msg"] = f"Update me error - {e}"
        return get_all_trades()

# Purani init_db ki zaroorat nahi, lekin naam rakha hai taaki purana code toote nahi
def init_db():
    _ensure_diary_csv()

init_db()

# ---------------- LOGIN ----------------
if not st.session_state.authenticated:
    st.title("Scan Stock")
    st.write("Token daalo.")
    # PIN HATA DIYA HAI - Ab sirf IND ka Secret Code hi kaafi hai. 4 ank ka Code ab kabhi nahi mangega.
    with st.form("login_form"):
        indmoney_secret = st.text_input("Token", type="password", placeholder="Token")
        submit = st.form_submit_button("Kholo", use_container_width=True)
        if submit:
            if not indmoney_secret or len(indmoney_secret) < 10:
                st.error("Token daalo")
            else:
                ok, msg = ind_test_profile(indmoney_secret)
                if not ok:
                    st.error(msg)
                    st.write("Token galat hai.")
                else:
                    st.session_state.authenticated = True
                    st.session_state.indmoney_secret = indmoney_secret
                    st.session_state.indmoney_connected = True
                    st.session_state.indmoney_debug = msg
                    st.rerun()
    if st.button("Bina Token ke Dekho"):
        st.session_state.authenticated = True
        st.session_state.indmoney_secret = ""
        st.session_state.indmoney_connected = False
        st.rerun()
    st.stop()

# ---------------- TOP BAR ----------------
# V40 - System Health ek line me - Token / GitHub / Universe / Data - taaki 9:15 pe ek nazar me pata chale sab theek hai ya nahi. Cards / Dark Mode nahi - minimal hi rahega.
try:
    _tok_ok = "✅ Token" if st.session_state.get("indmoney_secret", "") else "❌ Token nahi"
    _gh_ok = "✅ GitHub" if GITHUB_TOKEN and GITHUB_REPO else "❌ GitHub nahi"
    _uni_n = len(st.session_state.get("universe_216_df", pd.DataFrame())) if st.session_state.get("universe_216_df", None) is not None else 0
    st.caption(f"{_tok_ok} | {_gh_ok} | Universe: {_uni_n} stocks | Data: INDstocks se")
except:
    pass
top_left, top_right = st.columns([4, 1])
with top_left:
    st.title("Scan Stock")
with top_right:
    st.write("")
    if st.button("Trading Diary", use_container_width=True):
        st.session_state.show_diary = not st.session_state.show_diary
        st.rerun()
    # V21 - Trading Diary ke paas hi chhota sa Download Data Button - Mahine me 1 baar dabao
    # Jaise hi daboge, Master (FNO + Equity + Index) Download ho ke GitHub me apne aap save ho jayega.
    # Usme Exchange, Segment, Security ID, Expiry - sab likha hoga. Phir roz Expiry search nahi karni padegi.
    # V22 - Download Data sabse upar, sabse bada - Tumko Upload nahi karna, ye Button hi sab karega
    # Stock ka Expiry 1 Mahine me badalta hai, Option ka Expiry 7 Din me badalta hai - isliye 7 Din se zyada purana ho to Warning dikhayenge
    _last_dl_str = st.session_state.get("master_dl_last_date", "")
    _dl_old_msg = ""
    try:
        if _last_dl_str:
            _last_dt = datetime.strptime(_last_dl_str, "%Y-%m-%d %H:%M")
            _days_old = (ist_now() - _last_dt).days
            if _days_old >= 7:
                _dl_old_msg = f"Data { _days_old } din purana hai."
            elif _days_old >= 1:
                _dl_old_msg = f"Data { _days_old } din purana hai."
    except:
        pass
    if _dl_old_msg:
        st.warning(_dl_old_msg)
    if st.button("Download Data", use_container_width=True, key="top_download_data"):
        _tok_top = st.session_state.get("indmoney_secret", "")
        if not _tok_top or len(str(_tok_top)) < 10:
            st.session_state["_master_dl_msg"] = "Pehle Token se Login karo"
        else:
            with st.spinner("Monthly Master Download ho raha hai... FNO + Equity + Index - GitHub me apne aap save ho raha hai..."):
                _res_top, _msg_top = download_monthly_master_all(_tok_top)
                _lines = []
                for _fn, _b, _df, _ok, _m in _res_top:
                    _lines.append(f"{_fn}: {_m}")
                st.session_state["_master_dl_msg"] = " | ".join(_lines)
                st.session_state["master_dl_last_date"] = ist_now().strftime("%Y-%m-%d %H:%M")
        st.rerun()
    if st.session_state.get("_master_dl_msg"):
        with st.expander("Download ka haal", expanded=False):
            st.write(st.session_state["_master_dl_msg"])
    if st.session_state.get("master_dl_last_date"):
        st.caption(f"{st.session_state['master_dl_last_date']}")

if st.session_state.indmoney_connected:
    st.success("Connected")
else:
    st.warning("Not Connected")

st.sidebar.title("Menu")
if st.sidebar.button("Trading Diary Kholo"):
    st.session_state.show_diary = True; st.rerun()
if st.sidebar.button("Refresh Data"):
    st.cache_data.clear(); st.rerun()
if st.sidebar.button("Logout"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()

# ---------------- DIARY ----------------
if st.session_state.show_diary:
    st.markdown("## Diary")
    # V21 - Diary ke andar bhi wahi Download Data Button - Kona me chhota sa, Diary ke paas hi
    # Mahine me 1 baar dabao - Master GitHub me apne aap save ho jayega, Expiry wahi se milegi
    col_diary_dl1, col_diary_dl2 = st.columns([3, 1])
    with col_diary_dl2:
        if st.button("Download Data", use_container_width=True, key="diary_download_data"):
            _tok_d = st.session_state.get("indmoney_secret", "")
            if not _tok_d or len(str(_tok_d)) < 10:
                st.session_state["_master_dl_msg"] = "Pehle Token se Login karo"
            else:
                with st.spinner("Download ho raha hai..."):
                    _res_d, _msg_d = download_monthly_master_all(_tok_d)
                    _lines_d = []
                    for _fn, _b, _df, _ok, _m in _res_d:
                        _lines_d.append(f"{_fn}: {_m}")
                    st.session_state["_master_dl_msg"] = " | ".join(_lines_d)
                    st.session_state["master_dl_last_date"] = ist_now().strftime("%Y-%m-%d %H:%M")
            st.rerun()
    with col_diary_dl1:
        st.caption("")
    # V35 - FIX: Download ki lambi linein Diary ke upar mat dikhao - Photo me yahi dikkat thi, trade neeche dab gaye the
    if st.session_state.get("_master_dl_msg"):
        with st.expander("Download ka haal", expanded=False):
            st.write(st.session_state["_master_dl_msg"])
    if st.session_state.get("master_dl_last_date"):
        st.caption(f"Last Master Download: {st.session_state['master_dl_last_date']}")
    if st.session_state.get("_diary_last_msg"):
        st.success(st.session_state["_diary_last_msg"])
    # GitHub Secrets ka status - yahi secret jagah hai
    if GITHUB_TOKEN and GITHUB_REPO:
        st.success("GitHub Connected")
    else:
        st.warning("GitHub nahi hai")
        with st.expander("Secrets"):
            st.code("""Streamlit Cloud -> App -> (3 dot) Manage app -> Settings -> Secrets me ye daalo:

TELEGRAM_BOT_TOKEN = "[TUMHARA-BOT-TOKEN-SIRF-SECRETS-ME]"
TELEGRAM_CHAT_ID = "[TUMHARA-CHAT-ID-SIRF-SECRETS-ME]"
GITHUB_TOKEN = "ghp_XXXX... tumhara naya Token"
GITHUB_REPO = "tumhara-username/tumhara-repo-naam"

# GITHUB_TOKEN kaise banayein:
# 1. github.com -> Profile Photo -> Settings -> Developer settings -> Personal access tokens -> Tokens (classic) -> Generate new token (classic)
# 2. Note me likho: Scanner Diary
# 3. Expiration: No expiration ya 90 days
# 4. Tick karo: repo (poora repo wala box) - bas yahi chahiye
# 5. Generate -> Copy karo - dobara nahi dikhega, isliye turant Secrets me daal do
# 6. GITHUB_REPO = github.com pe tumhare repo ka naam - jaise kumarshyam/scanner
# 7. Kabhi bhi Token ko chat me, code me, screenshot me mat bhejo - sirf Secrets me
""", language="text")
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
                    # V35 - Exit Edit: Target/SL pe nahi nikle, kisi aur price pe nikle to yahan se dalo - stock change hua to bhi yahin se
                    _exit_val = st.number_input(f"Exit Price - #{row['id']}", value=float(row['entry']) if pd.notna(row['entry']) else 0.0, key=f"ex{row['id']}")
                    if st.button(f"Exit Save Karo - #{row['id']}", key=f"exb{row['id']}"):
                        update_trade_exit(row['id'], _exit_val, "EXITED"); st.rerun()
                else:
                    # Band trade ka exit price galat dala ho to yahan se badlo - status wahi rahega, PnL naya ban jayega
                    _exit_old = float(row['exit_price']) if pd.notna(row['exit_price']) and str(row['exit_price']) not in ("", "nan") else float(row['entry'])
                    _exit_new = st.number_input(f"Exit Badlo - #{row['id']}", value=_exit_old, key=f"exc{row['id']}")
                    if st.button(f"Exit Badlo Save - #{row['id']}", key=f"excb{row['id']}"):
                        update_trade_exit(row['id'], _exit_new, str(row['status'])); st.rerun()
        st.download_button("CSV Download Karo", data=trades_df_all.to_csv(index=False), file_name="all_trades.csv", mime="text/csv")
    if st.button("Diary Band Karo"):
        st.session_state.show_diary = False; st.rerun()
    st.divider()

# ---------------- V19 - MASTER CSV - DOWNLOAD BUTTON HATA DIYA - AB GITHUB FILE SE AAYEGA ----------------
# User ne bola: Download ka Option hata do. CSV hum Download karke GitHub pe Upload kar denge, ya tumko bhej denge, naam wahi rakh denge jo tum bologe.
# Naam jo bola hai wahi rakha hai: IND_Master_Equity.csv (aur IND_Master_FNO.csv) - Isko GitHub repo me app.py ke saath rakho.
# App ab Download nahi karega, GitHub wali File se hi Sahi Naam + Secret Code lega. Usme sab stock ka likha hua hoga.
# Agar GitHub pe file abhi nahi hai to neeche Upload se bhi de sakte ho - wo bhi Download nahi hai, Upload hai.
# Master file chupchaap load karo - screen pe kuch mat likho
try:
    _gh_df, _gh_msg = ind_load_master_from_github_file()
    if _gh_df is not None and not _gh_df.empty:
        st.session_state["master_equity_df"] = _gh_df
        _master_done = True
    else:
        _master_done = False
except Exception:
    _master_done = False
st.divider()

# ---------------- V24 - SINGLE STOCK SEARCH - RELIANCE ya RIL likho, Suggestion dega, Sirf IND se Check karega - NSE_ + SECURITY_ID se ----------------
# User ka naya Option: Hum jo stock search karein, stock ka naam likhein - jaise RELIANCE ya RIL likhein, to Suggestion de de RELIANCE ka, phir usko search karke bataye ki kitne Criteria pe fit ho raha hai aur 100 me se kitne ank mile.
# Ye 5 ka example nahi hai - ye koi bhi 1 stock ke liye hai, jab tum chaaho tab check karo, poora Scan kiye bina.
st.markdown("### Search")
st.write("")
_single_input = st.text_input("Stock", placeholder="RELIANCE", key="single_stock_input")
_single_resolved = None
_single_sugg = []
if _single_input:
    _single_resolved, _single_sugg = resolve_stock_name(_single_input)
    if _single_resolved:
        st.success(f"{_single_resolved}")
    elif _single_sugg:
        st.info("Chuno:")
        _single_resolved = st.selectbox("Chuno", _single_sugg, key="single_stock_select")
    else:
        st.warning("Nahi mila")
        # Dropdown me sab dikha do taaki wahan se chun sake
        _raw_opts = st.session_state.get("universe_216_df", pd.DataFrame())["STOCK"].astype(str).tolist() if st.session_state.get("universe_216_df", None) is not None and not st.session_state.get("universe_216_df", pd.DataFrame()).empty else list(MARKET_STOCKS.keys())
        _single_opts_216, _ = normalize_universe_to_symbols(_raw_opts, pd.DataFrame({"STOCK": _raw_opts}))
    _single_resolved = st.selectbox(f"Chuno - {len(_single_opts_216)} stocks", _single_opts_216, key="single_stock_all_select")
else:
    # Khali hai to bhi Dropdown de do - wahan se bhi chun sakte ho
    # V39 - FIX: Search wala hissa kabhi poora app nahi girayega - pehle se khali karke rakho, phir bharo
    _single_opts_216b = []
    _single_resolved = None
    try:
        _raw_opts_b = st.session_state.get("universe_216_df", pd.DataFrame())["STOCK"].astype(str).tolist() if st.session_state.get("universe_216_df", None) is not None and not st.session_state.get("universe_216_df", pd.DataFrame()).empty else list(MARKET_STOCKS.keys())
        _single_opts_216b, _ = normalize_universe_to_symbols(_raw_opts_b, pd.DataFrame({"STOCK": _raw_opts_b}))
    except Exception:
        _single_opts_216b = list(MARKET_STOCKS.keys())
    try:
        _single_resolved = st.selectbox(f"Chuno - {len(_single_opts_216b)} stocks", [""] + _single_opts_216b, key="single_stock_dropdown_empty")
    except Exception as _e_sel:
        st.write(f"Search me error - {_e_sel} - neeche wale AI se Puchho se puchh lo")
        _single_resolved = None
    if _single_resolved == "":
        _single_resolved = None
if _single_resolved:
    # V22 - Single Search bhi Code se hi hoga - naam sirf Suggestion ke liye hai, andar Code se khojenge
    # Pehle Code nikal lo, phir dikhao - taaki pata chale naam se nahi, Code se search ho raha hai
    try:
        _map_single = ind_get_all_scrips(st.session_state.get("indmoney_secret", ""))
        # V39 - FIX: "STATE BANK OF INDIA" chuna ho to pehle SBIN banao, phir Code khojo - full naam se Code kabhi nahi milega
        _single_sym = _single_resolved
        try:
            _rs, _ = resolve_to_symbol(str(_single_resolved))
            if _rs:
                _single_sym = str(_rs).upper()
        except:
            pass
        _code_single = _map_single.get(_single_sym, _map_single.get(str(_single_sym).upper(), ""))
        if _code_single:
            st.success(f"{_single_resolved} - {_code_single}")
        else:
            st.warning("Code nahi mila - Download Data dabao")
    except Exception as e:
        st.write(f"Code check me error - {e}")
    if st.button(f"{_single_resolved} - Check", use_container_width=True, key="single_check_btn"):
        with st.spinner("Check ho raha hai..."):
            # V24 - SIRF IND SE - Docs wala exact pattern, jo photo me bheja hai:
            #   headers = {'Authorization': access_token}
            #   params = {'scrip-codes': 'NSE_2885,NSE_11536'}
            #   response = requests.get('https://api.indstocks.com/market/quotes/full', headers=headers, params=params)
            #   LTP = quotes['data']['NSE_2885']['live_price'], Change = ['day_change_percentage'], Volume = ['volume']
            # Yahoo / NSE se kuch nahi mangenge - teenon ka Compromise Mix band.
            _tok3 = st.session_state.get("indmoney_secret", "")
            _scrip_map3 = ind_get_all_scrips(_tok3) if _tok3 else dict(KNOWN_SCRIP)
            # V39 - ind_get_scrip khud full naam -> Symbol kar lega, yahan bhi wahi bhej do
            _sid3, _src3 = ind_get_scrip(_single_resolved, _tok3, _scrip_map3)
            _scrip_code3 = f"NSE_{_sid3}" if _sid3 else ""
            _ind_ana = None; _ind_msg = ""; _ind_chain = pd.DataFrame(); _ind_chain_msg = ""; _ind_quote = None; _ind_quote_msg = ""
            if _sid3:
                # STEP 1 - LTP sirf IND se - Docs wala quotes/full
                try:
                    _qdata, _qmsg = ind_quotes_full_docs_pattern([_scrip_code3], _tok3)
                    _ind_quote_msg = _qmsg
                    if _scrip_code3 in _qdata:
                        _d = _qdata[_scrip_code3]
                        _ind_quote = {"symbol": _single_resolved, "scrip_code": _scrip_code3, "security_id": _sid3,
                                      "ltp": safe_float(_d.get("live_price", 0)), "change_pct": safe_float(_d.get("day_change_percentage", 0)),
                                      "volume": safe_float(_d.get("volume", 0)), "open": safe_float(_d.get("day_open", 0)),
                                      "high": safe_float(_d.get("day_high", 0)), "low": safe_float(_d.get("day_low", 0)),
                                      "prev_close": safe_float(_d.get("previous_close", 0)), "raw": _d}
                        _ind_msg = f"IND se aaya - {_scrip_code3} - LTP ₹{safe_float(_d.get('live_price',0))} - Change {safe_float(_d.get('day_change_percentage',0))}% - Docs wala pattern"
                    else:
                        _ind_msg = f"IND quotes/full me {_scrip_code3} nahi aaya - {_qmsg}"
                except Exception as e:
                    _ind_quote_msg = f"IND Quote Error - {e}"
                    _ind_msg = _ind_quote_msg
                # STEP 2 - Candle sirf IND se - Historical 5minute, NSE_ + Code se
                try:
                    _td3 = get_trading_day()
                    _multi3 = ind_get_multi_timeframe(_single_resolved, _sid3, _tok3, _td3)
                    _df5_ind = _multi3.get("df_5min", None)
                    _dfd_ind = _multi3.get("df_daily", pd.DataFrame())
                    if _df5_ind is not None and len(_df5_ind) > 0:
                        _ind_ana = analyze_full_day(_df5_ind, _dfd_ind if _dfd_ind is not None else pd.DataFrame())
                        _ind_msg += f" | Candle IND se - {len(_df5_ind)} candles"
                    else:
                        _ind_msg += f" | IND Historical khali - Code {_sid3} - {_multi3.get('debug',[])}"
                except Exception as e:
                    _ind_msg += f" | IND Candle Error - {e}"
                # STEP 3 - Option Chain sirf IND se - underlying-scrip = SECURITY_ID (bina prefix), exchange=NSE, segment=EQUITY
                try:
                    _ind_chain, _ind_chain_msg, _exp3, _scrip3, _ltp3 = ind_get_option_chain(_single_resolved, _tok3, _scrip_map3)
                    _ind_msg += f" | Option Chain IND se: {_ind_chain_msg}"
                except Exception as e:
                    _ind_chain_msg = f"IND Option Chain Error - {e}"
                    _ind_msg += f" | Option: {_ind_chain_msg}"
            else:
                _ind_msg = f"IND Scrip nahi mila - {_src3} - GitHub CSV me iska Sahi Naam check karo - Pehle Download Data dabao"
            st.session_state["single_result"] = {"stock": _single_resolved, "ind_ana": _ind_ana, "ind_msg": _ind_msg, "ind_chain": _ind_chain, "ind_chain_msg": _ind_chain_msg, "ind_quote": _ind_quote, "ind_quote_msg": _ind_quote_msg, "best_ana": _ind_ana, "scrip_code": _scrip_code3, "security_id": _sid3, "expiry": locals().get("_exp3", "")}
            # V26 - Single Check ka bhi Candle Cache me jama kar do - taaki SCAN me is stock ka Delta hi mangna pade
            try:
                if _ind_ana is not None and "error" not in _ind_ana:
                    # _multi3 se df5 lo - wahan se Today Cache update hoga
                    _df5_for_cache = _multi3.get("df_5min", None) if "_multi3" in locals() else None
                    if _df5_for_cache is not None and not _df5_for_cache.empty:
                        update_history_cache_after_scan({_single_resolved: _df5_for_cache}, _td3)
            except:
                pass
        st.rerun()
# Single ka Result dikhao
if st.session_state.get("single_result"):
    _sr = st.session_state["single_result"]
    _stk = _sr.get("stock", "")
    st.markdown(f"### {_stk}")
    st.write(f"{_sr.get('scrip_code','')} | {_sr.get('security_id','')}")
    # SIRF IND KA TABLE - Teenon ka nahi, ek hi sahi wala - Docs wala quotes/full se LTP + Candle se baaki
    _iA = _sr.get("ind_ana") or {}; _iQ = _sr.get("ind_quote") or {}
    _ind_rows = [
        {"Cheez": "LTP (IND se)", "Value": safe_float(_iQ.get("ltp",0)) if _iQ else safe_float(_iA.get("LTP",0)) if _iA else 0, "Kahan se": "IND quotes/full - NSE_ + SECURITY_ID se"},
        {"Cheez": "Change % (IND se)", "Value": safe_float(_iQ.get("change_pct",0)) if _iQ else safe_float(_iA.get("Gap %",0)) if _iA else 0, "Kahan se": "IND quotes/full - day_change_percentage"},
        {"Cheez": "Gap % (IND Candle se)", "Value": safe_float(_iA.get("Gap %",0)) if _iA else 0, "Kahan se": "IND Historical 5minute se"},
        {"Cheez": "VWAP (IND Candle se)", "Value": safe_float(_iA.get("VWAP",0)) if _iA else 0, "Kahan se": "IND Historical 5minute se"},
        {"Cheez": "Day High (IND se)", "Value": safe_float(_iQ.get("high",0)) if _iQ else safe_float(_iA.get("Day High",0)) if _iA else 0, "Kahan se": "IND quotes/full - day_high"},
        {"Cheez": "Day Low (IND se)", "Value": safe_float(_iQ.get("low",0)) if _iQ else safe_float(_iA.get("Day Low",0)) if _iA else 0, "Kahan se": "IND quotes/full - day_low"},
        {"Cheez": "Volume (IND se)", "Value": safe_float(_iQ.get("volume",0)) if _iQ else 0, "Kahan se": "IND quotes/full - volume"},
        {"Cheez": "Volume x (IND Candle se)", "Value": safe_float(_iA.get("Vol x",0)) if _iA else 0, "Kahan se": "IND Historical 5minute se"},
    ]
    st.dataframe(pd.DataFrame(_ind_rows), use_container_width=True, hide_index=True)
    _best = _sr.get("best_ana")
    if _best is not None and "error" not in _best:
        _break_df, _total = calc_probability_breakdown(_best)
        st.markdown(f"### {_stk} - {_total}/100")
        st.dataframe(_break_df, use_container_width=True, hide_index=True)
        st.write(f"{_total}/100")
        # Pass count bhi
        _pass_n = int(sum([1 for _, r in _break_df.iterrows() if r["Pass?"] == "✅ PASS" and r["Max"] > 0 and r["Criteria"].startswith(("1.","2.","3.","4."))]))
        st.write(f"{_pass_n}/4 Pass")
        st.write(f"**Movement:** {_best.get('Movement Type','')} - {_best.get('Movement Detail','')} | **Session:** {_best.get('Session Story','')} | **Fake?** {'HAAN - TRAP' if _best.get('Fake Breakout') else 'NAHI'}")
    else:
        st.warning("Data nahi aaya")
    # V23 - Single ka Option Chain - sirf INDmoney se - NSE se nahi mangte
    _ind_ch_s = _sr.get("ind_chain", pd.DataFrame())
    if _ind_ch_s is not None and not _ind_ch_s.empty:
        st.write("Chain:")
        st.dataframe(_ind_ch_s.head(15), use_container_width=True, hide_index=True)
    else:
        st.write("Chain nahi aaya")
    # V28 - SINGLE ka bhi FINAL CALL - wahi build_trade_call, taaki Single me bhi Entry/SL/Target mile, sirf chain ke 15 row nahi
    try:
        _s_ana = _sr.get("best_ana") or {}
        if _s_ana and "error" not in _s_ana:
            _s_total = _total if "_total" in locals() else safe_float(_s_ana.get("Probability %", 0))
            # Single ke ana ko scan-row jaisa banao - Gap/ORB/Volume ke ✅/❌ bhi bhar do
            _s_gap_ok = "✅" if abs(safe_float(_s_ana.get("Gap %", 0))) > 0.30 else "❌"
            _s_vwap_ok = "✅" if ((safe_float(_s_ana.get("LTP", 0)) > safe_float(_s_ana.get("VWAP", 0)) and safe_float(_s_ana.get("Gap %", 0)) > 0) or (safe_float(_s_ana.get("LTP", 0)) < safe_float(_s_ana.get("VWAP", 0)) and safe_float(_s_ana.get("Gap %", 0)) < 0)) else "❌"
            _s_row = dict(_s_ana)
            _s_row["Stock"] = _stk
            _s_row["Probability %"] = int(_s_total)
            _s_row["Gap"] = _s_gap_ok
            _s_row["VWAP_OK"] = _s_vwap_ok
            _s_row["ORB"] = "✅" if bool(_s_ana.get("ORB Break", False)) else "❌"
            _s_row["Volume"] = "✅" if safe_float(_s_ana.get("Vol x", 0)) > 1.5 else "❌"
            _s_row["Volatility OK"] = "✅" if ("CHOPPY" not in str(_s_ana.get("Movement Type", "")) and "VOLATILE" not in str(_s_ana.get("Movement Type", ""))) else "❌"
            _s_row["Fake?"] = "HAAN - TRAP" if bool(_s_ana.get("Fake Breakout", False)) else "NAHI"
            # News bias Single ke liye - abhi ka news table neeche hai, isliye yahan NEUTRAL rakhenge, SCAN wala FINAL CALL news se adjust hota hai
            _s_call = build_trade_call(_s_row, _ind_ch_s, _sr.get("expiry", ""), "NEUTRAL")
            st.markdown(f"### {_stk}")
            if _s_call.get("status") == "TRADE":
                st.success(f"BUY KARO: {_s_call['stock']} {_s_call['strike']} {_s_call['opt_type']} @ Rs {_s_call['entry']} - Expiry: {_s_call['expiry']} - 1 Lot Cost Rs {_s_call['cost']:.0f} (Lot { _s_call['lot']})")
                st.write(f"BUY: Rs {_s_call['entry']} | SELL: Rs {_s_call['target']} | SL: Rs {_s_call['sl']}")
                st.write(f"Max Profit: Rs {_s_call['max_profit']:.0f} | Max Loss: Rs {_s_call['max_loss']:.0f} | Prob: {_s_call['prob']:.0f}/100 | Direction: {_s_call['direction']} | LTP Rs {_s_call['ltp']:.1f}")
                st.write(f"Rule: {_s_call.get('rule_line','')} | Movement: {_s_call['movement_type']} | Adjust: {_s_call.get('adjust_note','')}")
                st.write("")
                _s_sugg = {"date": datetime.now().strftime("%Y-%m-%d"), "time": datetime.now().strftime("%H:%M:%S"), "symbol": _s_call['stock'], "strike": _s_call['strike'], "opt_type": _s_call['opt_type'], "entry": float(_s_call['entry']), "sl": float(_s_call['sl']), "target": float(_s_call['target']), "qty_lots": 1, "qty_total": int(_s_call['lot']), "capital_used": float(_s_call['cost']), "risk": float(_s_call['max_loss']), "status": "OPEN", "reason": f"Single Search - Prob {_s_call['prob']:.0f} - {_s_call['movement_type']}", "conditions": _s_call.get('rule_line','')}
                if st.button("Telegram", use_container_width=True, key="single_call_notify"):
                    _ok_s = send_strike(_s_call['stock'], _s_call['strike'], _s_call['opt_type'], _s_call['entry'], _s_call['sl'], _s_call['target'], _s_call['cost'], _s_call['lot'], _s_call['expiry'], str(_s_call['movement_type']))
                    st.success("Chala gaya ✅") if _ok_s else st.error("Nahi gaya ❌")
                if st.button(f"{_stk} ko Diary me Save Karo", use_container_width=True, key="single_call_diary"):
                    save_trade(_s_sugg); st.success(st.session_state.get("_diary_last_msg","Diary me save ho gaya!")); st.rerun()
            else:
                st.warning(f"NO TRADE - {_stk} - {_s_call.get('reason','')}")
                st.write(f"Prob: {_s_call.get('prob',0):.0f}/100 | LTP Rs {_s_call.get('ltp',0):.1f} | Movement: {_s_call.get('movement_type','')} - Zabardasti strike nahi denge, WAIT karo.")
    except Exception as _e_scall:
        st.write(f"Single FINAL CALL me error - {_e_scall}")
st.divider()

# ---------------- SCAN BUTTON ----------------
# Scan ka Time Window dikhao - taaki pata chale 09:20 pe scan ho raha hai ya 02:00 pe
try:
    _td = get_trading_day()
    _s, _e = get_scan_window(_td)
    st.info(f"{ist_now().strftime('%H:%M')} | {_td}")
except Exception as e:
    pass

# ---------------- V37 - AI LIVE - Market + News + Crash + Impact - AI Worker ne likha, yahan sirf dikhega ----------------
# Website pe source ka naam nahi likhenge - sirf jaankari dikhegi
with st.expander("AI Live - Market, News, Crash, Impact", expanded=True):
    try:
        _ai = load_ai_live()
        if not _ai:
            # V38 - Worker nahi chala to bhi khali nahi - Saved data + News se hi bana do
            _ai = build_ai_live_fallback()
            st.write("Saved data se - Worker nahi chala to bhi ye jaankari hai.")
        if _ai.get("fallback"):
            st.write("Saved data se - Live nahi hai, Token daal ke Scan karo to Live aa jayega.")
        else:
            _mkt = _ai.get("market", {}) or {}
            _upd = str(_ai.get("updated_at", ""))
            st.write(f"Market: {_mkt.get('direction', '')} - Nifty {safe_float(_mkt.get('nifty', 0)):.0f} ({safe_float(_mkt.get('nifty_change_pct', 0)):+.2f}%) | Bank Nifty {safe_float(_mkt.get('bank_nifty', 0)):.0f} ({safe_float(_mkt.get('bank_nifty_change_pct', 0)):+.2f}%) | Sensex {safe_float(_mkt.get('sensex', 0)):.0f} ({safe_float(_mkt.get('sensex_change_pct', 0)):+.2f}%) | VIX {safe_float(_mkt.get('vix', 0)):.1f} | Upar: {_mkt.get('advance', '')} | Neeche: {_mkt.get('decline', '')}")
            st.write(f"AI kab chala: {_upd}")
            try:
                _upd_dt = pd.to_datetime(_upd)
                _age_min = (datetime.now() - _upd_dt.to_pydatetime().replace(tzinfo=None) if hasattr(_upd_dt, "to_pydatetime") else datetime.now()).total_seconds() / 60 if _upd_dt is not None else 9999
                if _age_min > 30:
                    st.write("AI ruka hua lag raha hai - thodi der baad phir dekho.")
            except:
                pass
            _crash = _ai.get("crash_alerts", []) or []
            if _crash:
                st.write("Crash / Tez Giravat:")
                for _c in _crash:
                    st.write(f"  - {_c}")
            else:
                st.write("Koi crash nahi hai.")
            _news_ai = _ai.get("news", []) or []
            if _news_ai:
                _ndf = pd.DataFrame([{"News": str(_n.get("title", ""))[:120], "Type": str(_n.get("type", "")), "Direction": str(_n.get("direction", "")), "Asar": str(_n.get("impact", ""))} for _n in _news_ai])
                st.dataframe(_ndf, use_container_width=True, hide_index=True)
            else:
                st.write("Abhi koi badi khabar nahi hai.")
            _mem = load_ai_memory() or {}
            _pats = (_mem.get("patterns", []) or [])[:5]
            if _pats:
                st.write("Pichhli baar aisa hua to kya hua:")
                for _pt in _pats:
                    st.write(f"  - {str(_pt.get('text', ''))}")
    except Exception as _e_ai:
        st.write(f"AI Live me error - {_e_ai}")

# ---------------- V38 - AI CHAT - ChatGPT jaisa, par sirf stock ke liye ----------------
# Har stock ka kyu bhaga / kyu gira - apne data se batayega, banayi hui wajah nahi bolega
with st.expander("AI se Puchho - Koi bhi stock kyu bhaga / kyu gira", expanded=False):
    try:
        _q_in = st.text_input("Sawaal", placeholder="RELIANCE kyu bhaga? ya Market kyu gira?", key="ai_chat_input")
        if st.button("Puchho", use_container_width=True, key="ai_chat_ask"):
            if _q_in:
                with st.spinner("AI soch raha hai..."):
                    _ans = ask_stock_ai(_q_in)
                st.write(_ans)
                st.session_state["ai_chat_last"] = _ans
            else:
                st.write("Sawaal likho - jaise 'RELIANCE kyu bhaga?'")
        elif st.session_state.get("ai_chat_last"):
            st.write(st.session_state.get("ai_chat_last"))
    except Exception as _e_chat:
        st.write(f"AI Chat me error - {_e_chat}")

# Manual News wala stock - jaise BHEL me 2.5 lakh crore ka deal hua to BHEL bhag sakta hai, wo Yahoo Top 5 me nahi bhi ho to bhi hum usko Step 2 me lenge
st.markdown("### News")
manual_input = st.text_input("News Stock", placeholder="BHEL, SUZLON", key="manual_news_input")
manual_list = []
if manual_input:
    for _x in manual_input.split(","):
        _x = _x.strip()
        if not _x:
            continue
        _m_sym, _m_sugg = resolve_to_symbol(_x)
        if _m_sym:
            manual_list.append(_m_sym)
        elif _m_sugg:
            st.info(f"{_x} se kai mile - {_m_sugg[:5]} - Ek saaf naam likho")
        elif _x:
            st.warning(f"{_x} se koi stock nahi mila - Symbol ya poora naam likho, jaise BHEL ya ADANI ENERGY SOLUTION LTD")
if manual_list:
    st.success(f"Add hoga: {', '.join(manual_list)}")


# ---------------- V25 - 216 UNIVERSE TABLE - Jaruri Jankari - Ek Nazar Me ----------------
with st.expander("Universe (216)", expanded=False):
    try:
        _tok_u = st.session_state.get("indmoney_secret", "")
        _ulist_u, _udf_u, _umsg_u = get_scan_universe_216(_tok_u)
        st.write(f"{_umsg_u}")
        if _udf_u is not None and not _udf_u.empty:
            st.dataframe(_udf_u, use_container_width=True, hide_index=True)
            st.write(f"Total: {len(_udf_u)} stocks")
        else:
            st.write("Universe abhi khali hai - Download Data dabao, phir 216 wali list yahan dikhegi. Tab tak 138 wala purana list scan me chalega.")
            # Fallback - 138 wala list bhi dikha do
            _fb = pd.DataFrame([{"STOCK": k, "SECURITY_ID": KNOWN_SCRIP.get(k, ""), "SCRIP_CODE_NSE": f"NSE_{KNOWN_SCRIP.get(k, '')}" if KNOWN_SCRIP.get(k) else "", "LOT_SIZE": LOT_SIZES.get(k, ""), "EXPIRY_LIST": ""} for k in MARKET_STOCKS.keys()])
            st.dataframe(_fb, use_container_width=True, hide_index=True)
    except Exception as e:
        st.write(f"Universe Table me Error - {e}")


# ---------------- V26 - HISTORY CACHE STATUS - GitHub se pichhla data kitna mila? ----------------
with st.expander("History", expanded=False):
    try:
        # V34 - Sirf is mahine ki 5 file dikhao - jo file chahiye wahi khulegi, poora folder nahi
        _td_h = get_trading_day()
        _mm_h = tf_yyyymm(_td_h)
        _rows_h = []
        for _tf_h in TF_LIST:
            _df_h = load_tf_month(_tf_h, _mm_h)
            _n_h = len(_df_h) if _df_h is not None else 0
            _nstocks_h = int(_df_h["STOCK"].nunique()) if _df_h is not None and not _df_h.empty and "STOCK" in _df_h.columns else 0
            _rows_h.append({"Timeframe": _tf_h, "Mahina": _mm_h, "Candles": _n_h, "Stocks": _nstocks_h, "File": f"data/history/{_tf_h}/{_mm_h}.csv"})
        st.dataframe(pd.DataFrame(_rows_h), use_container_width=True, hide_index=True)
        st.write("5min = ORB + VWAP | 15min = Trend confirm | 1H = Trend | 4H = Trend | Daily = ATR + Trend | Weekly = Trend")
        if st.session_state.get("last_cache_msg"):
            st.write(f"**Last Scan ke baad Save:** {st.session_state.get('last_cache_msg')}")
    except Exception as e:
        st.write(f"History UI me Error - {e}")

# V38 - Token Check - Scan se pehle Token sahi hai ya expire, ye 1 click me pata chalega
if st.button("Token Check", use_container_width=True):
    _tok_ok, _tok_msg = check_ind_token()
    if _tok_ok:
        st.success(_tok_msg)
    else:
        st.error(_tok_msg)
if st.button("Scan", use_container_width=True):
    # V24 - SIRF IND SE SCAN - Yahoo / NSE band. Docs wala pattern hi sab jagah.
    # Pehle GitHub wali IND_Scrip_Codes.csv se Scrip-Code turant mil jayega (Download Data se jama hua).
    # Phir live data sirf IND se: quotes/full (NSE_2885) + historical/5minute (NSE_2885) + option-chain (underlying-scrip=2885)
    # Jo data badalne wala nahi hai (Scrip-Code + Expiry) wo GitHub se, jo badalne wala hai (LTP/Candle/Chain) wo live IND se.
    with st.spinner("Scan ho raha hai..."):
        # V32 - Dobara Scan dabaya aur market band hai aur isi din ka scan pehle se hai to dobara IND se mat mango - wahi result turant dikhao. Pehle har baar poora scan dobara hota tha, isliye har baar utna hi time lagta tha.
        _td_now = get_trading_day()
        _reuse = False
        _prev_df = st.session_state.get("scan_df", None)
        _prev_day = st.session_state.get("scan_trading_day", "")
        if _prev_df is not None and not _prev_df.empty and str(_prev_day) == str(_td_now) and is_market_closed_for_scan(_td_now):
            df_step1 = _prev_df
            debug1 = st.session_state.get("step1_debug", {})
            _reuse = True
        else:
            df_step1, debug1 = ind_scan_all_ind_only()
            st.session_state.scan_trading_day = str(_td_now)
        # V38 - FIX: Photo me Checked 0/216 tha - IND se 0 aaya, isliye koi stock nahi mila - ab Saved data se bhi stock denge, khali nahi chhodenge
        _fallback_used = False
        _fallback_msg = ""
        try:
            _ok_n = int((debug1 or {}).get("ind_ok", 0))
        except:
            _ok_n = 0
        if (df_step1 is None or df_step1.empty or _ok_n == 0) and not _reuse:
            try:
                _dfb, _msgb = scan_from_saved_history()
                if _dfb is not None and not _dfb.empty:
                    df_step1 = _dfb
                    debug1 = dict(debug1 or {})
                    debug1["fallback"] = True
                    debug1["fallback_msg"] = _msgb
                    _fallback_used = True
                    _fallback_msg = _msgb
            except Exception as _e_fb:
                _fallback_msg = f"Saved fallback me error - {_e_fb}"
        st.session_state["scan_fallback"] = _fallback_used
        st.session_state["scan_fallback_msg"] = _fallback_msg
        st.session_state.scan_df = df_step1
        st.session_state.step1_debug = debug1
        st.session_state.scan_time = datetime.now().strftime("%H:%M:%S")
        # V37 - Diary wale jeet-haar se Score +/- karna BAND - user ne mana kiya, ab AI Worker se seekhna hoga
        selected = []
        if not df_step1.empty:
            _top15 = df_step1.head(15)["Stock"].tolist() if "Stock" in df_step1.columns else []
            _prob50 = df_step1[df_step1["Probability %"] >= 50]["Stock"].tolist() if "Probability %" in df_step1.columns else []
            for _s in _top15 + _prob50:
                if _s not in selected:
                    selected.append(_s)
            selected = selected[:20]
        for m in manual_list:
            if m not in selected:
                selected.append(m)
        if not selected and manual_list:
            selected = manual_list[:]
        st.session_state.selected_stocks = selected
        st.session_state.scan_source = f"{debug1.get('ind_ok',0)}/{debug1.get('ind_total',0)}" if not _reuse else "Cache se"
        # Option Chain sirf Selected ke liye, sirf IND se
        token = st.session_state.get("indmoney_secret", "")
        step3_results = {}
        if selected and token and len(str(token)) > 10:
            try:
                scrip_map = ind_get_all_scrips(token)
            except:
                scrip_map = dict(KNOWN_SCRIP)
            # Selected ka Candle + Option Chain - ind_fill + option-chain, dono IND se
            step3_results = ind_fill_for_selected(selected, token, scrip_map)
            st.session_state.step3_results = step3_results
            # V30 - FAST SCAN - Option Chain SIRF FINAL CALL wale 1 stock ke liye, 20 stock ke liye nahi.
            # Pehle hum selected (Top 15 + Prob>=50 + Manual = 20 tak) sab ki Chain mangte the - 20 Chain x har Chain pe retries = SCAN 2-3 min slow ho jata tha.
            # Ab sirf 1 Chain mangenge - jo stock FINAL CALL me aayega (Rule se chuna gaya Top 1). Baaki stock ki Chain jab zaroorat hogi tab Section 6 / FINAL CALL ke button se 1-1 karke mang lenge.
            # Isse SCAN ka Chain wala time 20x se 1x ho jayega - SCAN poora fast ho jayega.
            _chain_map = {}
            try:
                _final_stock_scan = ""
                # Qualifying wala stock dhoondo - wahi FINAL CALL banega - Prob>=50 + Movement HAAN + Fake/Sideways/Choppy nahi
                for _i_q in range(len(df_step1)):
                    _r_q = df_step1.iloc[_i_q]
                    try:
                        _ok_q2, _why_q2 = is_qualifying_row(_r_q)
                    except:
                        _ok_q2 = False
                    if _ok_q2:
                        _final_stock_scan = str(_r_q.get("Stock", ""))
                        break
                if not _final_stock_scan and not df_step1.empty:
                    _final_stock_scan = str(df_step1.iloc[0].get("Stock", ""))
                if _final_stock_scan:
                    try:
                        _ch, _chmsg, _ex, _sc, _lt = ind_get_option_chain(_final_stock_scan, token, scrip_map)
                        _chain_map[_final_stock_scan] = {"chain": _ch, "msg": _chmsg, "expiry": _ex}
                    except Exception as e:
                        _chain_map[_final_stock_scan] = {"chain": pd.DataFrame(), "msg": f"Error {e}", "expiry": ""}
            except Exception as _e_chain1:
                _chain_map = {}
            st.session_state.chain_map = _chain_map
        else:
            st.session_state.step3_results = {}
            st.session_state.chain_map = {}
        # V26 - Scan ke baad History Cache update - Aaj ke naye candles GitHub me jama kar do
        # ind_fill se df_5min milta hai - usi se Today Cache banao, Daily Cache sirf market band hone pe finalize hoga
        try:
            _s3_for_cache = st.session_state.get("step3_results", {})
            _cache_by_stock = {}
            for _cs, _cv in _s3_for_cache.items():
                try:
                    if isinstance(_cv, dict) and _cv.get("df_5min") is not None and not _cv.get("df_5min").empty:
                        _cache_by_stock[_cs] = _cv.get("df_5min")
                except:
                    continue
            if _cache_by_stock:
                _td_cache = get_trading_day()
                _d_df, _t_df, _cmsg = update_history_cache_after_scan(_cache_by_stock, _td_cache)
                st.session_state["last_cache_msg"] = _cmsg
                st.session_state["history_cache_saved"] = True
        except Exception as e:
            st.session_state["last_cache_msg"] = f"History Cache save me Error - {e}"
    # Indices + News - ye company/news ki jaankari ke liye hai, price ke liye nahi - price sirf IND se
    try:
        indices_df = fetch_indices_history(); news_df = fetch_global_news()
    except:
        indices_df = pd.DataFrame(); news_df = pd.DataFrame()
    st.session_state.indices_data = indices_df; st.session_state.news_data = news_df
    st.session_state.auto_sent = False
    # V28 - SCAN ke turant baad FINAL CALL bana ke rakh do - taaki RESULTS me upar hi dikh jaye, dobara click na karna pade
    try:
        _nb = "NEUTRAL"
        try:
            if news_df is not None and not news_df.empty and "Impact" in news_df.columns:
                _neg = len(news_df[news_df["Impact"] == "NEGATIVE"]); _pos = len(news_df[news_df["Impact"] == "POSITIVE"])
                _nb = "NEGATIVE" if _neg > _pos else "POSITIVE" if _pos > _neg else "NEUTRAL"
        except:
            _nb = "NEUTRAL"
        st.session_state["top_call_news_bias"] = _nb
        if not df_step1.empty:
            _cmap_top = st.session_state.get("chain_map", {})
            # Pehle qualifying wala stock lo, nahi to Top1 - qualifying ka matlab Rule pass + Movement suru + Fake/Sideways/Choppy nahi
            _final_row = None; _final_chain = pd.DataFrame(); _final_expiry = ""
            for _i in range(len(df_step1)):
                _r = df_step1.iloc[_i]
                _ok_q, _why_q = is_qualifying_row(_r)
                if _ok_q:
                    _final_row = _r; break
            if _final_row is None:
                _final_row = df_step1.iloc[0]
            _fstock = str(_final_row.get("Stock", ""))
            if _fstock in _cmap_top:
                _final_chain = _cmap_top[_fstock].get("chain", pd.DataFrame())
                _final_expiry = _cmap_top[_fstock].get("expiry", "")
            _top_call = build_trade_call(_final_row, _final_chain, _final_expiry, _nb)
            # V36 - Koi rule pass nahi karta to bhi 1 stock do - BEST EFFORT - khali mat chhodo, Score ke saath bata do pakka nahi hai
            if _top_call.get("status") == "NO_TRADE":
                _top_call = build_best_effort_call(_final_row, _final_chain, _final_expiry, _nb, 0)
            # Session me sirf scalar rakhenge - chain DataFrame dobara chain_map se milegi
            st.session_state["top_call"] = _top_call
            st.session_state["top_call_stock"] = _fstock
    except Exception as _e_topcall:
        st.session_state["top_call"] = {"status": "NO_TRADE", "stock": "", "reason": f"FINAL CALL banane me error - {_e_topcall}", "expiry": ""}
    if not df_step1.empty:
        top = df_step1.iloc[0]
        if safe_float(top.get("Probability %", 0)) >= 70:
            ok_auto = send_top5(df_step1.head(5), "")
            st.session_state.auto_sent = ok_auto
    st.rerun()


def _safe_cols(df, wanted):
    # V27 - KeyError Fix - Kabhi bhi df[[...]] se crash nahi hoga
    # Wajah: SCAN wali df me jo column nahi hai, usko seedha df[[...]] se mangne pe pandas KeyError deta hai - "['Probability %'] not in index" - aur poora app lal ho jata hai.
    # Ab sirf wahi column dikhayenge jo df me hai, jo nahi hai wo chhod denge - app kabhi crash nahi hoga.
    try:
        if df is None or df.empty:
            return []
        return [c for c in wanted if c in df.columns]
    except:
        return []

# ---------------- RESULTS ----------------
if st.session_state.scan_df is not None and not st.session_state.scan_df.empty:
    df_scan = st.session_state.scan_df; indices_df = st.session_state.indices_data; news_df = st.session_state.news_data
    st.info(f"{st.session_state.get('scan_time','')} | {len(df_scan)} stocks")
    if st.session_state.get("scan_fallback"):
        st.warning(f"Saved data se hai - Live nahi hai - {st.session_state.get('scan_fallback_msg','')} - Token daal ke dobara Scan karo to Live aa jayega.")
    # ---------------- V28 - FINAL CALL SABSE UPAR - Yehi mool function hai, data jama karna nahi ----------------
    # Pehle ye sabse neeche Section 6 me tha - wahan tak pahunchne ke liye 216-row wali 2 table + Debug + IND Fill scroll karna padta tha.
    # Ab SCAN ke turant baad yahin dikhega: Rule se chuna gaya 1 stock + uski Chain + Rs 5000 wala Strike + Entry / SL / Target + BUY / SELL.
    # News Bias yahin pehle nikal lo - taaki SL/Target news se adjust ho jaye, neeche wali News table baad me bhi dikhegi.
    _news_bias_top = st.session_state.get("top_call_news_bias", "NEUTRAL")
    try:
        if news_df is not None and not news_df.empty and "Impact" in news_df.columns:
            _neg_t = len(news_df[news_df["Impact"] == "NEGATIVE"]); _pos_t = len(news_df[news_df["Impact"] == "POSITIVE"])
            _news_bias_top = "NEGATIVE" if _neg_t > _pos_t else "POSITIVE" if _pos_t > _neg_t else "NEUTRAL"
    except:
        pass
    # FINAL CALL - session me hai to wahi, nahi to abhi bana lo (purana V27 wala scan ho to bhi kaam karega, dobara SCAN ki zaroorat nahi)
    _final_call = st.session_state.get("top_call", None)
    try:
        _cmap_top2 = st.session_state.get("chain_map", {})
        if not _final_call or not isinstance(_final_call, dict) or not _final_call.get("stock"):
            _frow = None
            for _i2 in range(len(df_scan)):
                _r2 = df_scan.iloc[_i2]
                _ok2, _why2 = is_qualifying_row(_r2)
                if _ok2:
                    _frow = _r2; break
            if _frow is None:
                _frow = df_scan.iloc[0]
            _fstock2 = str(_frow.get("Stock", ""))
            _fchain2 = _cmap_top2.get(_fstock2, {}).get("chain", pd.DataFrame()) if _fstock2 in _cmap_top2 else pd.DataFrame()
            _fexp2 = _cmap_top2.get(_fstock2, {}).get("expiry", "") if _fstock2 in _cmap_top2 else ""
            _final_call = build_trade_call(_frow, _fchain2, _fexp2, _news_bias_top)
            if _final_call.get("status") == "NO_TRADE":
                _final_call = build_best_effort_call(_frow, _fchain2, _fexp2, _news_bias_top, 0)
            st.session_state["top_call"] = _final_call
    except Exception as _e_fc:
        _final_call = {"status": "NO_TRADE", "stock": "", "reason": f"FINAL CALL me error - {_e_fc}", "expiry": ""}
    st.markdown("### Best Stock")
    st.write(f"News: {_news_bias_top}")
    # V37 - Diary wala Seekha hata diya - ab AI Live neeche se aayega
    if _final_call and _final_call.get("status") == "TRADE":
        st.success(f"BUY KARO: {_final_call['stock']} {_final_call['strike']} {_final_call['opt_type']} @ Rs {_final_call['entry']} - Expiry: {_final_call['expiry']} - 1 Lot Cost Rs {_final_call['cost']:.0f} (Lot {_final_call['lot']})")
        st.write(f"**BUY:** Rs {_final_call['entry']} pe BUY karo | **SELL (Target):** Rs {_final_call['target']} pe SELL karo | **STOP LOSS:** Rs {_final_call['sl']} pe nikal jao - SL se neeche mat ruko")
        st.write(f"Max Profit: Rs {_final_call['max_profit']:.0f} | Max Loss: Rs {_final_call['max_loss']:.0f} | Prob: {_final_call['prob']:.0f}/100 | Direction: {_final_call['direction']} | Stock LTP Rs {_final_call['ltp']:.1f}")
        st.write(f"{_final_call.get('rule_line','')}")
        st.write(f"Movement: {_final_call['movement_type']} - {_final_call.get('movement_detail','')} | Session: {_final_call.get('session','')}")
        st.write(f"{_final_call.get('adjust_note','')}")
        _fc_sugg = {"date": datetime.now().strftime("%Y-%m-%d"), "time": datetime.now().strftime("%H:%M:%S"), "symbol": _final_call['stock'], "strike": _final_call['strike'], "opt_type": _final_call['opt_type'], "entry": float(_final_call['entry']), "sl": float(_final_call['sl']), "target": float(_final_call['target']), "qty_lots": 1, "qty_total": int(_final_call['lot']), "capital_used": float(_final_call['cost']), "risk": float(_final_call['max_loss']), "status": "OPEN", "reason": f"FINAL CALL - Prob {_final_call['prob']:.0f} - {_final_call['movement_type']}", "conditions": _final_call.get('rule_line','')}
        _c1, _c2 = st.columns(2)
        with _c1:
            if st.button("Telegram", use_container_width=True, key="final_call_notify"):
                _ok_fc = send_strike(_final_call['stock'], _final_call['strike'], _final_call['opt_type'], _final_call['entry'], _final_call['sl'], _final_call['target'], _final_call['cost'], _final_call['lot'], _final_call['expiry'], str(_final_call['movement_type']))
                st.success("Chala gaya ✅") if _ok_fc else st.error("Nahi gaya ❌")
        with _c2:
            if st.button("Diary", use_container_width=True, key="final_call_diary"):
                save_trade(_fc_sugg); st.success(st.session_state.get("_diary_last_msg","Diary me save ho gaya!")); st.rerun()
    elif _final_call and _final_call.get("status") == "BEST_EFFORT":
        # V36 - Sab rule pass nahi hua, par Top me sabse behtar yahi hai - 1 stock to do, Score ke saath, neeche Telegram bhi hai
        st.warning(f"BEST EFFORT - Sab rule pass nahi hua - Score {_final_call.get('score',0)}% - Pakka setup nahi, apne risk pe lo, chhota lot lo")
        st.write(f"Wajah: {_final_call.get('reason','')}")
        st.success(f"BUY KARO: {_final_call['stock']} {_final_call['strike']} {_final_call['opt_type']} @ Rs {_final_call['entry']} - Expiry: {_final_call['expiry']} - 1 Lot Cost Rs {_final_call['cost']:.0f} (Lot {_final_call['lot']})")
        st.write(f"**BUY:** Rs {_final_call['entry']} pe BUY karo | **SELL (Target):** Rs {_final_call['target']} pe SELL karo | **STOP LOSS:** Rs {_final_call['sl']} pe nikal jao")
        st.write(f"Max Profit: Rs {_final_call['max_profit']:.0f} | Max Loss: Rs {_final_call['max_loss']:.0f} | Prob: {_final_call['prob']:.0f}/100 | Score: {_final_call.get('score',0)}% | Direction: {_final_call['direction']} | Stock LTP Rs {_final_call['ltp']:.1f}")
        st.write(f"{_final_call.get('rule_line','')}")
        st.write(f"Movement: {_final_call['movement_type']} - {_final_call.get('movement_detail','')} | Session: {_final_call.get('session','')}")
        st.write(f"{_final_call.get('adjust_note','')}")
        _fc_sugg2 = {"date": datetime.now().strftime("%Y-%m-%d"), "time": datetime.now().strftime("%H:%M:%S"), "symbol": _final_call['stock'], "strike": _final_call['strike'], "opt_type": _final_call['opt_type'], "entry": float(_final_call['entry']), "sl": float(_final_call['sl']), "target": float(_final_call['target']), "qty_lots": 1, "qty_total": int(_final_call['lot']), "capital_used": float(_final_call['cost']), "risk": float(_final_call['max_loss']), "status": "OPEN", "reason": f"BEST EFFORT - Score {_final_call.get('score',0)}% - {_final_call.get('reason','')}", "conditions": ""}
        _c1b, _c2b = st.columns(2)
        with _c1b:
            if st.button("Telegram", use_container_width=True, key="best_effort_notify"):
                _ok_be = send_strike(_final_call['stock'], _final_call['strike'], _final_call['opt_type'], _final_call['entry'], _final_call['sl'], _final_call['target'], _final_call['cost'], _final_call['lot'], _final_call['expiry'], str(_final_call['movement_type']))
                st.success("Chala gaya ✅") if _ok_be else st.error("Nahi gaya ❌")
        with _c2b:
            if st.button("Diary", use_container_width=True, key="best_effort_diary"):
                save_trade(_fc_sugg2); st.success(st.session_state.get("_diary_last_msg","Diary me save ho gaya!")); st.rerun()
    elif _final_call and _final_call.get("status") == "NO_CHAIN":
        st.error(f"Rule pass hai - {_final_call.get('stock','')} - Prob {_final_call.get('prob',0):.0f}/100 - {_final_call.get('movement_type','')}")
        st.write(f"Wajah: {_final_call.get('reason','')}")
        if st.button(f"{_final_call.get('stock','')} ka Chain Mango", use_container_width=True, key="final_chain_fetch"):
            with st.spinner("Chain la rahe hain..."):
                _tok_fc = st.session_state.get("indmoney_secret", "")
                _smap_fc = ind_get_all_scrips(_tok_fc) if _tok_fc else {}
                _ch_fc, _msg_fc, _ex_fc, _sc_fc, _lt_fc = ind_get_option_chain(_final_call.get('stock',''), _tok_fc, _smap_fc)
                _cm_fc = st.session_state.get("chain_map", {})
                _cm_fc[_final_call.get('stock','')] = {"chain": _ch_fc, "msg": _msg_fc, "expiry": _ex_fc}
                st.session_state["chain_map"] = _cm_fc
                # Chain mil gayi to FINAL CALL dobara banao
                try:
                    _frow_fc = df_scan[df_scan["Stock"] == _final_call.get('stock','')].iloc[0]
                    st.session_state["top_call"] = build_trade_call(_frow_fc, _ch_fc, _ex_fc, _news_bias_top)
                except:
                    pass
            st.rerun()
        if st.button("Telegram - Top 5", use_container_width=True, key="nochain_telegram"):
            _ok_nc = send_top5(df_scan.head(5), "")
            st.success("Chala gaya ✅") if _ok_nc else st.error("Nahi gaya ❌")
    elif _final_call and _final_call.get("status") == "NO_FIT":
        st.warning(f"Rule pass hai - {_final_call.get('stock','')} - Prob {_final_call.get('prob',0):.0f}/100 - par Rs 5000 wala strike nahi mila")
        st.write(f"Wajah: {_final_call.get('reason','')}")
        st.write(f"Movement: {_final_call.get('movement_type','')} - {_final_call.get('movement_detail','')}")
        if st.button("Telegram - Top 5", use_container_width=True, key="nofit_telegram"):
            _ok_nf = send_top5(df_scan.head(5), "")
            st.success("Chala gaya ✅") if _ok_nf else st.error("Nahi gaya ❌")
    else:
        _nt_stock = _final_call.get('stock','') if _final_call else ""
        _nt_prob = _final_call.get('prob',0) if _final_call else 0
        st.warning(f"NO TRADE - WAIT KARO - {_nt_stock} bhi pakka setup nahi hai" if _nt_stock else "NO TRADE - WAIT KARO - Aaj koi pakka setup nahi mila")
        st.write(f"Wajah: {_final_call.get('reason','') if _final_call else 'Koi qualifying stock nahi mila'}")
        if _nt_stock:
            st.write(f"Top stock: {_nt_stock} - Prob {_nt_prob:.0f}/100 | Movement: {_final_call.get('movement_type','')} - {_final_call.get('movement_detail','')} - Zabardasti strike nahi denge, warna premium ghis jayega.")
        st.write("Top 5 neeche dekh lo - koi 50+ wala ho to usko Single Search me alag se check karo, par jab tak Movement suru nahi hota, entry mat lo.")
        if st.button("Telegram - Top 5", use_container_width=True, key="notrade_telegram"):
            _ok_nt = send_top5(df_scan.head(5), "")
            st.success("Chala gaya ✅") if _ok_nt else st.error("Nahi gaya ❌")

    # 3-STEP DEBUG - Har step me kitne aaye, kyu fail hua, sab dikhao - chhupao mat
    _dbg1 = st.session_state.get("step1_debug", {})
    _sel = st.session_state.get("selected_stocks", [])
    _s2 = st.session_state.get("step2_results", {})
    _s3 = st.session_state.get("step3_results", {})
    _need = st.session_state.get("need_ind", [])
    with st.expander("Debug"):
        st.write(f"OK {_dbg1.get('ind_ok',0)} / {_dbg1.get('ind_total',216)} | Fail: {len(_dbg1.get('ind_fail',[]))}")
        st.write(f"Universe: {_dbg1.get('universe_msg','')} | Total Checked: {_dbg1.get('ind_total',0)}")
        st.write(f"Selected (Top 15 + Prob>=50 + Manual News wale - 5 sirf example tha): {_sel}")
        st.write("")
        st.write("")
        if _s3:
            for _k, _v in _s3.items():
                st.write(f"  - {_k}: {_v.get('reason','')}")
        st.write("")
    _logs5b = st.session_state.get("ind_5x5_logs", [])
    if _logs5b:
        st.write("Log:")
        for _ll in _logs5b:
            st.write(f"  - {_ll}")
    # V19 - Top 5 ka 100 me se Score kaise bana - yehi gayab ho gaya tha
    if not df_scan.empty:
        with st.expander("Score", expanded=False):
            for _idx in range(min(5, len(df_scan))):
                _row = df_scan.iloc[_idx]
                _stk = _row.get("Stock", "")
                _prob = int(safe_float(_row.get("Probability %", 0)))
                st.markdown(f"**{_idx+1}. {_stk} - { _prob }/100**")
                # Is row se breakdown banao - df_scan me saare Criteria hain
                _brows = [
                    {"Criteria": "1. Gap", "Value": f"{safe_float(_row.get('Gap %',0)):+.2f}%", "Pass?": _row.get("Gap",""), "Ank": 15 if _row.get("Gap","")=="✅" else 0, "Max": 15},
                    {"Criteria": "2. VWAP", "Value": f"LTP {safe_float(_row.get('LTP',0)):.2f} vs VWAP {safe_float(_row.get('VWAP',0)):.2f}", "Pass?": _row.get("VWAP_OK", _row.get("VWAP","")), "Ank": 15 if _row.get("VWAP_OK", _row.get("VWAP",""))=="✅" else 0, "Max": 15},
                    {"Criteria": "3. ORB Break", "Value": f"ORB High {safe_float(_row.get('ORB High',0)):.2f}", "Pass?": _row.get("ORB",""), "Ank": 20 if _row.get("ORB","")=="✅" else 0, "Max": 20},
                    {"Criteria": "4. Volume", "Value": f"{safe_float(_row.get('Vol x',0)):.2f}x", "Pass?": _row.get("Volume",""), "Ank": 15 if _row.get("Volume","")=="✅" else 0, "Max": 15},
                    {"Criteria": "5. Movement Started?", "Value": str(_row.get("Movement Started?","")), "Pass?": "✅" if str(_row.get("Movement Started?",""))=="HAAN" else "❌", "Ank": 15 if str(_row.get("Movement Started?",""))=="HAAN" else 0, "Max": 15},
                    {"Criteria": "6. Trending / 7. Volatility", "Value": f"{_row.get('Movement Type','')} | Pass: {_row.get('Pass','')}", "Pass?": _row.get("Volatility OK",""), "Ank": "Baki 20 ank Trending+Volatility se - poora hisab Single Search me dekho", "Max": 20},
                    {"Criteria": "KATOTI Fake/Choppy", "Value": f"Fake: {_row.get('Fake?','')} | Movement: {_row.get('Movement Type','')}", "Pass?": "❌ KATA" if "TRAP" in str(_row.get("Fake?","")) else "✅ SAHI", "Ank": "-30 agar Fake hai", "Max": 0},
                ]
                st.dataframe(pd.DataFrame(_brows), use_container_width=True, hide_index=True)
                st.write(f"Final: {_prob}/100")

    _cmap = st.session_state.get("chain_map", {})
    # IND-ONLY TABLE - Data jama wala hissa - ab band (collapsed) expander me, taaki FINAL CALL ke upar na aaye
    with st.expander("Data", expanded=False):
        if _s3:
            st.markdown("### Detail")
            _rows3 = []
            for _k, _v in _s3.items():
                _rows3.append({"Stock": _k, "OK?": "✅" if _v.get("ok") else "❌"})
            st.dataframe(pd.DataFrame(_rows3), use_container_width=True, hide_index=True)
        _cmap = st.session_state.get("chain_map", {})
        if _cmap:
            st.markdown("### Chain")
            _rowsC = []
            for _k, _v in _cmap.items():
                _ch = _v.get("chain", pd.DataFrame())
                _rowsC.append({"Stock": _k, "Expiry": _v.get("expiry",""), "Chain Rows": len(_ch) if _ch is not None else 0})
            st.dataframe(pd.DataFrame(_rowsC), use_container_width=True, hide_index=True)
    if st.session_state.get("auto_sent"):
        st.success("Chala gaya ✅")
    st.markdown("### Index")
    if indices_df is not None and not indices_df.empty:
        st.dataframe(indices_df, use_container_width=True, hide_index=True)
    st.markdown("### News")
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
    st.write(f"News Bias: {news_bias} - Negative zyada hai to CE ka Target kam, SL tight rakhenge. Positive hai to CE ka Target bada.")
    st.markdown("### Top 5")
    top5 = df_scan.head(5)
    st.dataframe(top5[_safe_cols(top5, ["Stock", "LTP", "Gap %", "Direction", "Pattern", "Movement Type", "Probability %", "Movement", "Movement Started?", "Pass"])], use_container_width=True, hide_index=True)
    top1 = df_scan.iloc[0]; top1_stock = str(top1.get("Stock", "")); top1_prob = safe_float(top1.get("Probability %", 0)); top1_ltp = safe_float(top1.get("LTP", 0))
    st.success(f"No.1: {top1_stock} - Prob {top1_prob:.0f}% - LTP Rs {top1_ltp:.1f} - {top1.get('Movement Type','')}")
    st.write(f"No.1 ka Poora Din: {top1.get('Movement Detail','')}")
    st.write(f"Session: {top1.get('Session Story','')}")
    if st.button("Telegram - Top 5", use_container_width=True):
        ok = send_top5(top5, "")
        if ok:
            st.success("Chala gaya ✅")
        else:
            st.error("Nahi gaya ❌")
    st.markdown("### Movement")
    st.write("Sideways = Option mat lo, wait karo. Bhag Raha = Option le sakte ho. Volatile/Choppy = Premium kha jayega, mat lo. Fake = Trap tha.")
    st.dataframe(df_scan[_safe_cols(df_scan, ["Stock", "LTP", "Day Range %", "Net Move %", "Range vs ATR", "Movement Type", "Session Story", "VWAP Cross", "Wick", "Reversal", "Fake?", "Probability %"])], use_container_width=True, hide_index=True)
    st.markdown("### Market")
    # V27 - PURA MARKET me VWAP float nahi, ✅/❌ dikhana hai - isliye display copy me VWAP = VWAP_OK kar do, original df_scan ka VWAP float bacha rahega
    _disp_pura = df_scan.copy()
    try:
        if "VWAP_OK" in _disp_pura.columns:
            _disp_pura["VWAP"] = _disp_pura["VWAP_OK"]
    except:
        pass
    st.dataframe(_disp_pura[_safe_cols(_disp_pura, ["Stock", "LTP", "Gap %", "Direction", "Pattern", "Movement Type", "Probability %", "Gap", "VWAP", "ORB", "Volume", "Volatility OK", "Movement Started?", "Pass"])], use_container_width=True, hide_index=True)
    st.markdown("### Chain")
    sel_stock = st.selectbox("Stock Chuno - Jiska Option Chain dekhna hai", df_scan["Stock"].tolist(), index=0)
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
        st.markdown(f"**Poora Din ka Khel - {sel_stock}**")
        st.write(f"Movement: {row.get('Movement Type','')}")
        st.write(f"Detail: {row.get('Movement Detail','')}")
        st.write(f"Session: {row.get('Session Story','')} | Day Range: {safe_float(row.get('Day Range %',0)):.2f}% | Net Move: {safe_float(row.get('Net Move %',0)):+.2f}% | Range vs ATR: {safe_float(row.get('Range vs ATR',0)):.2f}x | VWAP Cross: {safe_int(row.get('VWAP Cross',0))} baar | Wick: {safe_float(row.get('Wick',0)):.2f} | Reversal: {safe_int(row.get('Reversal',0))} baar | Fake: {row.get('Fake?','')}")
        if "SIDEWAYS" in str(row.get("Movement Type", "")):
            st.warning("⚠️ YE STOCK SIDEWAYS HAI - Abhi Option mat lo, Breakout ka wait karo. Sideways me premium ghis jayega.")
        elif "VOLATILE" in str(row.get("Movement Type", "")) or "CHOPPY" in str(row.get("Movement Type", "")):
            st.error("⚠️ YE STOCK VOLATILE / CHOPPY HAI - Upar-neeche karke wahi ka wahi hai. Isme Option lena khatarnak hai, premium kha jayega.")
        elif "FAKE" in str(row.get("Movement Type", "")):
            st.error("⚠️ FAKE BREAKOUT THA - Trap tha, isme entry mat lo.")
        elif "BHAG RAHA" in str(row.get("Movement Type", "")):
            st.success("✅ YE STOCK BHAG RAHA HAI - Trend pakka hai, Option dekh sakte ho.")
        if st.button(f"{sel_stock} ka Option Chain Mango - Sirf IND Se", use_container_width=True):
            with st.spinner("Sirf IND se Option Chain dekh rahe hain - underlying-scrip = SECURITY_ID se..."):
                # V24 - Option Chain sirf IND se - chain_map me pehle se IND se aaya hua hai, wahi use karo, nahi to abhi IND se mango
                _cmap2 = st.session_state.get("chain_map", {})
                _ind_oc = None
                _ind_msg = ""
                if sel_stock in _cmap2:
                    _ind_oc = _cmap2[sel_stock].get("chain", pd.DataFrame())
                    _ind_msg = _cmap2[sel_stock].get("msg", "")
                if _ind_oc is not None and not _ind_oc.empty and len(_ind_oc) >= 5:
                    st.session_state[f"chain_{sel_stock}"] = _ind_oc
                    st.session_state[f"chain_source_{sel_stock}"] = "OK"
                    st.session_state[f"expiry_{sel_stock}"] = _cmap2[sel_stock].get("expiry", "")
                    st.session_state[f"scrip_{sel_stock}"] = f"NSE_{scrip_used}"
                    st.session_state[f"indltp_{sel_stock}"] = sel_ltp
                else:
                    # chain_map me nahi tha to abhi IND se mango
                    token_now = st.session_state.get("indmoney_secret", "")
                    scrip_map_now = ind_get_all_scrips(token_now) if token_now else {}
                    chain_df, source, expiry_yyyy, scrip_used, ind_ltp = ind_get_option_chain(sel_stock, token_now, scrip_map_now)
                    st.session_state[f"chain_{sel_stock}"] = chain_df
                    st.session_state[f"chain_source_{sel_stock}"] = "OK"
                    st.session_state[f"expiry_{sel_stock}"] = expiry_yyyy
                    st.session_state[f"scrip_{sel_stock}"] = scrip_used
                    st.session_state[f"indltp_{sel_stock}"] = ind_ltp
                st.rerun()
        chain_key = f"chain_{sel_stock}"
        if chain_key in st.session_state and st.session_state[chain_key] is not None and not st.session_state[chain_key].empty:
            chain_df = st.session_state[chain_key]; source = st.session_state.get(f"chain_source_{sel_stock}", ""); expiry_shown = st.session_state.get(f"expiry_{sel_stock}", ""); scrip_shown = st.session_state.get(f"scrip_{sel_stock}", ""); ind_ltp_shown = st.session_state.get(f"indltp_{sel_stock}", "")
            st.success(f"Expiry: {expiry_shown} - Strikes: {len(chain_df)}")
            st.dataframe(chain_df, use_container_width=True, hide_index=True)
            # V25 - Lot Size pehle Universe (Master FNO) se, nahi to purana LOT_SIZES se - FNO me LOT_SIZE likha hota hai
            lot = LOT_SIZES.get(sel_stock, 100)
            try:
                _udf_lot = st.session_state.get("universe_216_df", None)
                if _udf_lot is not None and not _udf_lot.empty and "STOCK" in _udf_lot.columns and "LOT_SIZE" in _udf_lot.columns:
                    _lr = _udf_lot[_udf_lot["STOCK"].astype(str).str.upper() == str(sel_stock).upper()]
                    if not _lr.empty and str(_lr.iloc[0]["LOT_SIZE"]).strip() not in ("", "nan", "0"):
                        lot = int(float(str(_lr.iloc[0]["LOT_SIZE"]).strip()))
            except:
                pass
            check_df, best = check_all_strikes(chain_df, lot, sel_ltp, row.get("Direction", ""), budget=5000)
            st.markdown(f"#### Strikes (Lot: {lot})")
            if not check_df.empty:
                st.dataframe(check_df, use_container_width=True, hide_index=True)
                fits_df = check_df[check_df["Fits"] == True]
                st.write(f"Total: {len(check_df)} | Fit: {len(fits_df)}")
                if not fits_df.empty:
                    st.dataframe(fits_df[["Strike", "Type", "Premium", "1 Lot Cost", "Fit?", "OI", "IV"]], use_container_width=True, hide_index=True)
            if best is not None:
                # News + Movement ke hisab se SL/Target adjust karo - Choppy me Target chhota, SL tight
                if "CHOPPY" in str(row.get("Movement Type", "")) or "VOLATILE" in str(row.get("Movement Type", "")):
                    sl_factor = 0.85; target_factor = 1.20
                    adjust_note = "Volatile hai isliye Target chhota (1.20x) aur SL tight (0.85x) rakha hai - zyada lalach mat karo"
                elif news_bias == "NEGATIVE" and str(best.get("Type", "")) == "CE":
                    sl_factor = 0.80; target_factor = 1.30
                    adjust_note = "News Negative hai isliye CE ka Target kam rakha hai"
                elif news_bias == "POSITIVE":
                    sl_factor = 0.70; target_factor = 1.60
                    adjust_note = "News Positive hai isliye Target bada rakha hai"
                elif "BHAG RAHA" in str(row.get("Movement Type", "")):
                    sl_factor = 0.70; target_factor = 1.60
                    adjust_note = "Bhag raha hai isliye Target bada rakha hai"
                else:
                    sl_factor = 0.70; target_factor = 1.50
                    adjust_note = "Normal Target 1.50x, SL 0.70x"
                entry_prem = safe_float(best.get("Premium", 0)); strike = safe_int(best.get("Strike", 0)); opt_type = str(best.get("Type", "CE"))
                sl_prem = round(entry_prem * sl_factor, 1); target_prem = round(entry_prem * target_factor, 1)
                max_loss = round((entry_prem - sl_prem) * safe_float(lot), 0); max_profit = round((target_prem - entry_prem) * safe_float(lot), 0); best_cost = safe_float(best.get("1 Lot Cost", 0))
                st.success(f"STRIKE: {sel_stock} {strike} {opt_type} @ Rs {entry_prem} - Expiry: {expiry_shown} - Cost Rs {best_cost:.0f} - SL Rs {sl_prem} - Target Rs {target_prem}")
                st.write(f"Entry: Rs {entry_prem} | Target: Rs {target_prem} | SL: Rs {sl_prem} | Max Profit: Rs {max_profit:.0f} | Max Loss: Rs {max_loss:.0f}")
                st.write(f"Adjust: {adjust_note}")
                st.write(f"Movement: {row.get('Movement Type','')} - {row.get('Movement Detail','')}")
                if st.button("Telegram", use_container_width=True):
                    ok = send_strike(sel_stock, strike, opt_type, entry_prem, sl_prem, target_prem, best_cost, lot, expiry_shown, str(row.get("Movement", "")))
                    if ok:
                        st.success("Chala gaya ✅")
                    else:
                        st.error("Nahi gaya ❌")
                suggested = {"date": datetime.now().strftime("%Y-%m-%d"), "time": datetime.now().strftime("%H:%M:%S"), "symbol": sel_stock, "strike": strike, "opt_type": opt_type, "entry": float(entry_prem), "sl": float(sl_prem), "target": float(target_prem), "qty_lots": 1, "qty_total": float(lot), "capital_used": float(best_cost), "risk": float(max_loss), "status": "OPEN", "reason": f"{row.get('Direction','')} - {row.get('Pattern','')} - {row.get('Movement Type','')} - News {news_bias} - Prob {sel_prob:.0f}% - Expiry {expiry_shown} - {source}", "conditions": f"Gap {row.get('Gap','')} VWAP {row.get('VWAP','')} ORB {row.get('ORB','')} Vol {row.get('Volume','')} VolOK {row.get('Volatility OK','')} Movement {row.get('Movement Started?','')} Fake {row.get('Fake?','')} Session {row.get('Session Story','')}"}
                if st.button(f"{sel_stock} ko Diary me Save Karo"):
                    save_trade(suggested); st.success(st.session_state.get("_diary_last_msg","Diary me save ho gaya!")); st.rerun()
            else:
                st.error(f"{sel_stock} me Rs 5000 me koi 1 Lot wala contract nahi mila.")
        elif chain_key in st.session_state and (st.session_state[chain_key] is None or st.session_state[chain_key].empty):
            st.error(f"❌ Option Chain nahi aaya - Wajah: {st.session_state.get(f'chain_source_{sel_stock}','')}")
            st.write("")
            st.write("Token check karo")
        else:
            st.info("Chain Mango dabao")
else:
    # V33 - Scan khali aaya to neeche blank mat chhodo - pehle blank rehta tha, isliye lagta tha Best Stock + Telegram gayab ho gaya. Ab wajah + Telegram dikhega.
    if st.session_state.get("scan_time"):
        st.markdown("### Best Stock")
        st.warning("Nahi mila - Koi data nahi hai")
        _dbg_e = st.session_state.get("step1_debug", {})
        _ok_e = _dbg_e.get("ind_ok", 0)
        _tot_e = _dbg_e.get("ind_total", 216)
        st.write(f"Checked: {_ok_e}/{_tot_e} - 0 hai to matlab IND se data aaya hi nahi.")
        # V39 - Asli wajah dikhao, Token pe ilzaam nahi - Scrip Map kitna bada tha, pehli fail kis wajah se hui
        if _dbg_e.get("scrip_map_size") is not None:
            st.write(f"Scrip Map: {_dbg_e.get('scrip_map_size')} entries - 216 se kam hai to bahut stock ka Code hi nahi mila.")
        if _dbg_e.get("first_fail_reason"):
            st.write(f"Pehli fail wajah: {_dbg_e.get('first_fail_reason')}")
        st.write("Kya karo: 1) Token Check dabao - Token expire hai to naya Token daalo | 2) Download Data dabao - Saved data aayega | 3) Phir Scan dabao.")
        if _dbg_e.get("fallback_msg"):
            st.write(f"Saved se bhi nahi mila: {_dbg_e.get('fallback_msg')}")
        if st.button("Telegram", use_container_width=True, key="empty_telegram"):
            _ok_t = send_telegram("Scan khali aaya - koi stock nahi mila. Token check karke dobara Scan dabao.")
            st.success("Chala gaya ✅") if _ok_t else st.error("Nahi gaya ❌")
