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

# ---- V48 split: ye module app_v47.py se nikala gaya, code same hai ----
# findstock/helpers.py - V48 - Shared config + helpers (split se)
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
APP_DIR = Path(__file__).resolve().parent.parent  # V48 - helpers.py ab findstock/ folder me hai, isliye repo root = parent.parent (app.py wala folder)
MASTER_FOLDER = "data"  # V33 - GitHub me sab master data ek hi folder me - bahar root me nahi. Diary alag hai, wo trades_diary me hi rahegi.

APP_VERSION = 50  # V43 - Chain ki asli wajah + Fill datetime fix + AI branch fallback  # V42 - Version sirf yahin se aayega - header + UI label dono yahin se, dobara V31 atakega nahi
def data_freshness_line():
    # Data taaza hai ya nahi - bas yehi dikhayenge, kahan se aaya ye nahi.
    # Taaza = Aaj ka Scan isi session me ho gaya, ya Universe file aaj ki hai. Nahi to - Download Data dabao.
    try:
        import streamlit as _st
        _sdf = _st.session_state.get("scan_df", None)
        if _sdf is not None and not _sdf.empty:
            return "Taaza - Aaj ka Scan ho gaya"
        _p = APP_DIR / "data" / "IND_Universe_216.csv"
        if _p.exists():
            _mt = datetime.fromtimestamp(_p.stat().st_mtime, IST)
            if _mt.date() == datetime.now(IST).date():
                return f"Taaza - Aaj {_mt.strftime('%H:%M')} ka"
            return f"Purana - {_mt.strftime('%d %b %H:%M')} ka - Download Data dabao"
        return "Nahi hai - Download Data dabao"
    except Exception:
        return "Check nahi hua - Download Data dabao"
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

def _push_master_to_github(filename, csv_bytes_or_text):
    # Diary wale hi GitHub Token/Repo se Master File ko GitHub pe save karo - apne aap save hoga.
    # Diary ka _push_diary_to_github() sirf Diary ke liye tha, ye Master ke liye hai - same tareeka.
    try:
        if not GITHUB_TOKEN or not GITHUB_REPO:
            return False, "GitHub Secrets me nahi hai - isliye GitHub me auto-save nahi hua. File ko neeche wale Download se le ke GitHub pe haath se daal do."
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
