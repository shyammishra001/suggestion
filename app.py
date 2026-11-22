# app.py - V22 - Code se Search + Download Data GitHub Token se + Expiry Master se (Stock 1 Mahina, Option 7 Din) - FULL DAY MOVEMENT + HISTORICAL DATA - INDstocks Docs se bana hua COMPLETE SCRIPT
# ============================================================================================
# KYA BADLA HAI V15 ME - USER NE SAHI KAHA THA:
# Pehle hum sirf OPEN-HIGH dekh rahe the. Matlab 9:15-9:30 ka ORB dekh ke bol dete the "Breakout hai".
# Lekin asli trading me Open-High se kuch nahi hota. Stock subah bhagta hai, dopahar me wapas aa jata hai.
# Ya subah sideways rehta hai, dopahar me bhagta hai. Ya pura din upar-neeche karke wahi ka wahi band hota hai.
# Isliye V15 me hum poora din dekhte hain - INDstocks HISTORICAL DATA se.
#
# DOCS JO CHECK KI GAYI:
# 1. Getting Started Step 3 - https://api-docs.indstocks.com/getting-started/
#    base_url = 'https://api.indstocks.com' , headers = {'Authorization': access_token} - Bearer NAHI
#    GET /market/quotes/full?scrip-codes=NSE_2885,NSE_11536
# 2. Option Chain - https://api-docs.indstocks.com/utility/
#    GET /market/option-chain?exchange=NSE&segment=EQUITY&underlying-scrip=2885&expiry=YYYY-MM-DD&strike_count=25
#    Response: data.strikes = { "24450": {"ce": {...}, "pe": {...}} } - dict hai, list NAHI
# 3. Contracts & Expiries - https://api-docs.indstocks.com/contracts/
#    GET /market/instruments/expiries?underlying=RELIANCE&segment=DERIVATIVE - ascending list, pehli wali Nearest
# 4. Instruments - https://api-docs.indstocks.com/instruments/
#    GET /market/instruments?source=equity - CSV aati hai, usme SYMBOL_NAME se SECURITY_ID nikalna hai
#    RELIANCE = 2885, TCS = 11536 - Docs me likha hai. FNO wali ID NAHI leni, EQUITY wali leni hai.
# 5. Historical Data - https://api-docs.indstocks.com/historicalData/ - TUMHARE PHOTO WALA PAGE
#    GET /market/historical/{interval} - interval = 5minute, 1day, 1minute, 15minute, 60minute etc.
#    Query: scrip-codes = max 5 - Example: NSE_3045,NFO_51011 - 5 se zyada bhejoge to 400 aayega
#           start_time = Unix epoch MILLISECONDS (inclusive)
#           end_time   = Unix epoch MILLISECONDS (exclusive)
#    Response: {"success": true, "data": {"NSE_1594": {"candles": [{"ts": 1782877500, "o":1007, "h":1013.9, "l":999.3, "c":1000.4, "v":2847163}]}}}
#    IMPORTANT:
#    - start_time / end_time MILLISECONDS me bhejne hain, lekin candle ka "ts" SECONDS me aata hai. ts*1000 karke next request banao.
#    - Candle ka ts = candle OPEN hone ka time hai. 5minute candle 09:15 wali 09:15-09:19 ko cover karti hai.
#    - Buckets 09:15 IST se align hote hain - 5minute wali 09:15, 09:20, 09:25... 15minute wali 09:15, 09:30, 09:45...
#    - 5minute ka Max Range 7 Din hai, 60minute ka 15 Din, 1day ka 1 Saal hai. Isse zyada mangoge to max window ka data aayega, error nahi.
#    - Jo code window me data nahi hai, wo "data" me aayega hi nahi - isliye returned keys check karo, assume mat karo.
#    - Candle fields har interval pe same hain: ts, o, h, l, c, v. OI ke liye Option Chain dekho, Historical me OI nahi aata.
#
# IS SCRIPT ME FULL-DAY MOVEMENT KAISE CHECK HOTA HAI - SIRF OPEN-HIGH NAHI:
# Har stock ke liye hum 2 tarah ka Historical Data mangte hain:
#   A) AAJ KA 5minute - 09:15 se ab tak - 75 candles tak. Isse poora din ka khel pata chalta hai.
#   B) PICHHLE 30 DIN KA 1day - ATR, Trend, Support, Pichhla Move nikalne ke liye.
# Phir us 5minute data se hum ye sab nikalte hain:
#   1. Day Range % = (Day High - Day Low) / Open * 100 - Din kitna bada tha?
#   2. Range vs ATR = Day Range / ATR(14 din). 1.0 se zyada matlab aaj normal se bada din tha, 0.6 se kam matlab bilkul chhota din.
#   3. VWAP - Typical Price * Volume ka weighted average. LTP VWAP se kitna upar/neeche hai, aur kitni % candles VWAP ke upar band hui.
#   4. ORB 9:15-9:30 - Pehli 3 candles (09:15, 09:20, 09:25) ka High/Low. Breakout hua? Kitni der tika? Fake breakout tha ya pakka?
#   5. 3 SESSION - Subah (09:15-11:30), Dopahar (11:30-13:30), Aakhiri (13:30-15:30) - har session ka alag Open/Close/Range/Direction.
#      Example: Subah bhaga, dopahar sideways, aakhiri me wapas gira = TRAP wala din.
#   6. VOLATILITY - 5min returns ka Standard Deviation, Wick Ratio (upar-neeche ki batti kitni lambi hai), VWAP Cross Count (kitni baar VWAP ko kaata),
#      Reversal Count (kitni baar direction palta), Body vs Range (candle ka body kitna bada hai).
#   7. SIDEWAYS vs BHAG RAHA vs VOLATILE ka faisla - in sab ko milake:
#      - SIDEWAYS = Range chhota + VWAP ke aas-paas atka + ORB nahi toota + Reversal zyada nahi, bas ek jagah atka.
#      - BHAG RAHA UPAR = Range bada + LTP Day High ke paas + 70%+ candles VWAP ke upar + Subah se dopahar tak ek hi direction + Volume badha hua.
#      - BHAG RAHA NEECHE = ulta.
#      - VOLATILE / CHOPPY = Range bada lekin Net Move chhota + VWAP ko 4+ baar kaata + Wick lambi + Baar-baar direction palta = isme Option khareedna khatarnak hai, premium kha jayega.
#      - DHIRE DHIRE = Range medium, ek direction me dheere-dheere chal raha hai, breakout nahi hua lekin trend hai.
#   8. MOVEMENT STARTED? - ORB toota + 2 candles uske bahar band hui + Volume 1.2x se zyada + VWAP confirm = HAAN, nahi to NAHI.
#   9. FAKE vs PAKKA - ORB toota lekin 15 min me wapas andar aa gaya = FAKE. ORB toota aur VWAP ke upar tik gaya = PAKKA.
#
# BAAKI SAB V14 WALA HI HAI:
# - Login sirf IND Token + 4 ank PIN se. Token 24 ghante me expire hota hai, roz naya banao indstocks.com/app/api-trading/access-tokens se.
# - Scan: NSE+BSE F&O stocks, 5 Conditions: Gap, VWAP, ORB, Volume, VIX (VIX ko hum Volatility se dekhte hain)
# - Option Chain: SIRF IND se, NSE Website se NAHI, Yahoo se NAHI. Galat hoga to wajah likhi aayegi.
# - Strike: Nearest Expiry, Total Strikes check, Rs 5000 me 1 Lot kaunsa fit hoga, Entry/SL/Target.
# - Telegram: Secrets se, Chat ID button NAHI hai, bhejne ke baad sirf "Chala gaya" likha aayega, bot ka naam / chat ID NAHI dikhega.
# - Diary: Ek hi CSV - all_trades.csv - Roz alag file NAHI. Diary button corner me.
# - Trade MANUAL hai, app kabhi auto-trade NAHI karega.
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

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except:
    IST = timezone(timedelta(hours=5, minutes=30))

st.set_page_config(page_title="Scanner V22 - Code se Search + Download Data (Tumko Upload Nahi Karna) - Full Day + PIN Hataya + Diary Fix", layout="wide")

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
        r = requests.get(f"{IND_BASE}/market/instruments/expiries", headers=ind_headers(token), params={"underlying": _sid_for_exp}, timeout=12)
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
    for fname in ["IND_master_index.csv", "IND_Master_Index.csv", "IND_Master_index.csv", "ind_master_index.csv", "IND_Master_Index.CSV"]:
        try:
            df = pd.read_csv(fname, header=0, dtype=str, keep_default_na=False)
            if not df.empty:
                return df, f"GitHub File se aaya - {fname} - {len(df)} rows - IND_master_index wali File"
        except:
            continue
    for fname in ["IND_Master_Equity.csv", "IND_Master_Equity.CSV", "ind_master_equity.csv", "IND_Master_FNO.csv", "IND_master_fno.csv"]:
        try:
            # Pehle current folder me dhoondo (Streamlit Cloud me repo ka root)
            df = pd.read_csv(fname, dtype=str, keep_default_na=False)
            if not df.empty:
                return df, f"GitHub File se aaya - {fname} - {len(df)} rows"
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
    return None, "GitHub pe IND_master_index.csv nahi mila - Upar wala Download Data dabao, Streamlit ke GitHub Code se apne aap Download ho ke GitHub me save ho jayega. Tumko Upload nahi karna hai."

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
                                _nm_s = str(_row.iloc[1]).strip().upper() if len(_row) > 1 else ""
                                if _nm_s and _nm_s != "NAN":
                                    _merged[_nm_s] = _sid_s
                                    if _nm_s == "NIFTY 50":
                                        _merged["NIFTY"] = _sid_s
                            else:
                                for _col in ["SYMBOL_NAME", "TRADING_SYMBOL", "CUSTOM_SYMBOL"]:
                                    if _col in _df_s.columns:
                                        _sym_s = str(_row[_col]).strip().upper()
                                        if _sym_s and _sym_s != "NAN":
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
    # GitHub file nahi mili to sirf KNOWN_SCRIP do - API se instruments mat mango (tumne mana kiya hai)
    return dict(KNOWN_SCRIP)
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
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
        get_resp = requests.get(url, headers=headers, timeout=10)
        sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None
        payload = {"message": f"Master update {filename} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Mahine me 1 baar", "content": content_b64}
        if sha:
            payload["sha"] = sha
        put_resp = requests.put(url, headers=headers, json=payload, timeout=20)
        if put_resp.status_code in (200, 201):
            return True, f"GitHub me apne aap save ho gaya - {filename}"
        return False, f"GitHub Fail {put_resp.status_code} - {put_resp.text[:200]}"
    except Exception as e:
        return False, f"GitHub Error - {e}"

def download_monthly_master_all(token):
    # Mahine me 1 baar - 3 File ek saath Download karo: FNO + Equity + Index
    # Ye ek hi baar IND se instruments mangta hai (mahine me 1 baar), roz nahi mangta.
    # Roz wala search sirf Security ID se hoga (V20 wala niyam), ye Monthly wala alag hai.
    # Returns (results_list, msg) - results: [(filename, bytes, df, github_ok, github_msg), ...]
    results = []
    if not token or len(str(token).strip()) < 10:
        return [], "Pehle IND Token se Login karo - bina Token ke Master Download nahi hoga"
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
            # GitHub me apne aap save karo
            ok, gmsg = _push_master_to_github(filename, csv_bytes)
            # Local session me bhi rakh do taaki isi Scan me use ho jaye
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
    return results, "Monthly Master Download ho gaya"

def get_expiry_from_master_file(stock_name, token=None):
    # V21 - Expiry ab baar-baar API se mat khojo, Master File (FNO) se hi le lo.
    # FNO Master me har contract ki EXPIRY_DATE likhi hoti hai. Us stock ke saare contract ki Expiry nikal lo, sort karo, pehli wali Nearest hai.
    # Isse roz-roz Expiry search ki zaroorat khatam - Mahine me 1 baar Master Download karne se sab Expiry mil jayegi.
    # Agar Master File me nahi mili to Fallback Thursday (V19 wala) use karenge - fail nahi karenge.
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
    # Hamare 138 stocks ka IND me kya Sahi Naam + Secret Code hai, ye table banata hai.
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
    for stock in MARKET_STOCKS.keys():
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
    rows.append({"Criteria": "1. Gap - Khula kitna upar/neeche", "Value": f"{safe_float(ana.get('Gap %',0)):+.2f}% (Chahiye >0.30%)", "Pass?": "✅ PASS" if gap_pass else "❌ FAIL", "Ank": gap_pts, "Max": 15, "Kahan se Check Hua": "Yahoo + NSE + IND - teeno se Gap same hona chahiye"})
    # 2 VWAP
    ltp = safe_float(ana.get("LTP", 0)); vwap = safe_float(ana.get("VWAP", 0)); gap = safe_float(ana.get("Gap %", 0))
    vwap_pass = (ltp > vwap and gap > 0) or (ltp < vwap and gap < 0)
    vwap_pts = 15 if vwap_pass else 0
    total += vwap_pts
    rows.append({"Criteria": "2. VWAP - LTP VWAP ke sahi taraf hai?", "Value": f"LTP {ltp:.2f} vs VWAP {vwap:.2f}", "Pass?": "✅ PASS" if vwap_pass else "❌ FAIL", "Ank": vwap_pts, "Max": 15, "Kahan se Check Hua": "Yahoo 5min se VWAP, NSE se Confirm"})
    # 3 ORB
    orb_pass = bool(ana.get("ORB Break", False))
    orb_pts = 20 if orb_pass else 0
    total += orb_pts
    rows.append({"Criteria": "3. ORB 09:15-09:30 Break", "Value": f"ORB High {safe_float(ana.get('ORB High',0)):.2f} / Low {safe_float(ana.get('ORB Low',0)):.2f} - Break: {orb_pass}", "Pass?": "✅ PASS" if orb_pass else "❌ FAIL", "Ank": orb_pts, "Max": 20, "Kahan se Check Hua": "Yahoo 5min ORB, NSE High/Low se Confirm"})
    # 4 Volume
    volx = safe_float(ana.get("Vol x", 0))
    vol_pass = volx > 1.5
    vol_pts = 15 if vol_pass else 0
    total += vol_pts
    rows.append({"Criteria": "4. Volume - Aaj zyada Volume hai?", "Value": f"{volx:.2f}x (Chahiye >1.5x)", "Pass?": "✅ PASS" if vol_pass else "❌ FAIL", "Ank": vol_pts, "Max": 15, "Kahan se Check Hua": "Yahoo Volume, NSE Total Volume se Confirm"})
    # 5 Movement Started
    mv_started = str(ana.get("Movement Started?", "")) == "HAAN"
    mv_pts = 15 if mv_started else 0
    total += mv_pts
    rows.append({"Criteria": "5. Movement Started? - Abhi bhag raha hai ya so raha hai", "Value": str(ana.get("Movement Started?", "")), "Pass?": "✅ PASS" if mv_started else "❌ FAIL", "Ank": mv_pts, "Max": 15, "Kahan se Check Hua": "Yahoo Last 5min + Day Range se"})
    # 6 Trending
    trend_score = safe_float(ana.get("Trending Score", 0))
    trend_pass = trend_score >= 60
    trend_pts = 10 if trend_pass else 0
    total += trend_pts
    rows.append({"Criteria": "6. Trending Score >=60", "Value": f"{trend_score:.0f}", "Pass?": "✅ PASS" if trend_pass else "❌ FAIL", "Ank": trend_pts, "Max": 10, "Kahan se Check Hua": "Yahoo Session Story S1/S2/S3 se"})
    # 7 Volatility OK
    mov_type = str(ana.get("Movement Type", ""))
    vol_ok = ("CHOPPY" not in mov_type and "VOLATILE" not in mov_type)
    vol_ok_pts = 10 if vol_ok else 0
    total += vol_ok_pts
    rows.append({"Criteria": "7. Volatility OK - Choppy / Volatile to nahi", "Value": mov_type, "Pass?": "✅ PASS" if vol_ok else "❌ FAIL", "Ank": vol_ok_pts, "Max": 10, "Kahan se Check Hua": "Yahoo Wick + Reversal se"})
    # Katoti
    fake = bool(ana.get("Fake Breakout", False))
    fake_pts = -30 if fake else 0
    total += fake_pts
    rows.append({"Criteria": "KATOTI: Fake Breakout - Trap hai?", "Value": "HAAN - TRAP" if fake else "NAHI", "Pass?": "❌ KATA" if fake else "✅ SAHI", "Ank": fake_pts, "Max": 0, "Kahan se Check Hua": "ORB toota lekin 15min me wapas - Yahoo + NSE"})
    choppy = "CHOPPY" in mov_type
    choppy_pts = -20 if choppy else 0
    total += choppy_pts
    rows.append({"Criteria": "KATOTI: Choppy", "Value": mov_type, "Pass?": "❌ KATA" if choppy else "✅ SAHI", "Ank": choppy_pts, "Max": 0, "Kahan se Check Hua": "Yahoo"})
    side = "SIDEWAYS" in mov_type
    side_pts = -15 if side else 0
    total += side_pts
    rows.append({"Criteria": "KATOTI: Sideways", "Value": mov_type, "Pass?": "❌ KATA" if side else "✅ SAHI", "Ank": side_pts, "Max": 0, "Kahan se Check Hua": "Yahoo"})
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

def resolve_stock_name(user_text):
    # Returns (resolved_stock_or_None, suggestions_list)
    # User ne "RIL" likha -> RELIANCE, "rel" likha -> RELIANCE, TCS, etc. wale suggestions
    if not user_text:
        return None, []
    q = str(user_text).strip().upper()
    # Pehle Alias me dekho
    if q in STOCK_ALIASES:
        resolved = STOCK_ALIASES[q]
        if resolved in MARKET_STOCKS:
            return resolved, [resolved]
    # Phir exact match
    if q in MARKET_STOCKS:
        return q, [q]
    # Phir contains - jaise "RELI" likha to RELIANCE, "TATA" likha to saare TATA
    sugg = [s for s in MARKET_STOCKS.keys() if q in s]
    # Agar 1 hi bacha to wahi resolved
    if len(sugg) == 1:
        return sugg[0], sugg
    # Agar 0 hai to alias ke andar bhi dhoondo
    if not sugg:
        # RIL jaisa chhota naam jo alias me hai lekin MARKET me nahi - wapas alias se
        for alias, real in STOCK_ALIASES.items():
            if q in alias:
                if real in MARKET_STOCKS and real not in sugg:
                    sugg.append(real)
    return None, sugg[:10]

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


def ind_get_scrip(symbol, token, scrip_map=None):
    # V22 - Naam se Search nahi, Code se Search - symbol yahan pe sirf Suggestion ke liye aaya hai, andar Code se hi khojenge.
    # Code pehle se hi Master File (Download Data se GitHub me save hui) me hai, isliye Error aayega hi nahi.
    if scrip_map and str(symbol).upper() in scrip_map:
        return str(scrip_map[str(symbol).upper()]), "MAP - Code se"
    if symbol in KNOWN_SCRIP:
        return KNOWN_SCRIP[symbol], "KNOWN"
    try:
        m = ind_get_all_scrips(token)
        if str(symbol).upper() in m:
            return str(m[str(symbol).upper()]), "CSV"
    except:
        pass
    return "", f"CSV me {symbol} nahi mila"

def ind_get_option_chain(symbol, token, scrip_map=None):
    # Docs Option Chain: GET /market/option-chain?exchange=NSE&segment=EQUITY&underlying-scrip=2885&expiry=YYYY-MM-DD&strike_count=25
    if not token or len(str(token).strip()) < 10:
        return pd.DataFrame(), "Token nahi diya", "", "", ""
    expiries, err_exp = ind_get_expiries(symbol, token)
    if not expiries:
        return pd.DataFrame(), f"Expiry nahi mili - {err_exp}", "", "", ""
    expiry_yyyy_mm_dd = str(expiries[0])
    scrip, _src = ind_get_scrip(symbol, token, scrip_map)
    if not scrip:
        return pd.DataFrame(), f"Scrip nahi mila - {_src}", expiry_yyyy_mm_dd, "", ""
    try:
        # V20 - Exchange / Segment mat bhejo, sirf Security ID se search karo.
        # Pehle hum exchange=NSE + segment=EQUITY + underlying-scrip=2885 bhejte the.
        # User ne bola: Security ID se search karoge to sab mil jayega, wesa request mat bhejo.
        # Isliye ab sirf underlying-scrip = Security ID + expiry + strike_count bhejenge.
        # scrip yahan pe IND_master_index / Equity Master CSV se aaya hua Security ID hai (jaise RELIANCE = 2885).
        params = {"underlying-scrip": scrip, "expiry": expiry_yyyy_mm_dd, "strike_count": 25}
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

# ---------------- 3-STEP SCAN - YAHI ASLI FIX HAI 86 FAIL KA ----------------
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
def yahoo_scan_all_3step(progress_cb=None):
    # STEP 1 - Yahoo se 138 stocks ek saath - yf.download ek hi call me sab le aata hai
    # Isme koi scrip-code, koi batch 5, koi 5/sec limit nahi hai.
    rows = []
    debug = {"yahoo_ok": 0, "yahoo_fail": [], "yahoo_total": len(MARKET_STOCKS)}
    try:
        tickers = list(MARKET_STOCKS.values())
        # 2 din ka 5min - aaj + kal ka thoda, taaki Prev Close bhi mil jaye
        df_all = yf.download(tickers, period="2d", interval="5m", progress=False, auto_adjust=False, group_by="ticker", threads=True)
        # yf.download group_by=ticker deta hai - har ticker ka alag DataFrame
        for stock, ticker in MARKET_STOCKS.items():
            try:
                if isinstance(df_all.columns, pd.MultiIndex):
                    try:
                        df_t = df_all[ticker].copy()
                    except Exception:
                        # Kabhi ticker .NS ke saath nahi milta, to pehla level check karo
                        continue
                else:
                    df_t = df_all.copy()
                if df_t is None or df_t.empty or len(df_t) < 1:
                    debug["yahoo_fail"].append(stock)
                    continue
                df_t = df_t.reset_index()
                # Columns saaf karo - MultiIndex se bachao
                for col in ['High','Low','Close','Volume','Open']:
                    if col in df_t.columns and isinstance(df_t[col], pd.DataFrame):
                        df_t[col] = df_t[col].iloc[:, 0]
                # Aaj ka din - aakhiri 75 candles (09:15-15:30 ka poora din)
                df_today = df_t.tail(75).copy()
                if "Datetime" in df_today.columns:
                    df_today["Time"] = pd.to_datetime(df_today["Datetime"])
                elif "Date" in df_today.columns:
                    df_today["Time"] = pd.to_datetime(df_today["Date"])
                else:
                    df_today["Time"] = pd.date_range(start=datetime.now(), periods=len(df_today), freq="5min")
                df5 = df_today[["Time","Open","High","Low","Close","Volume"]].copy()
                # Daily ATR ke liye - 1mo 1d, alag se ek hi call me nahi, per-stock chhota call - lekin sirf Top ke liye baad me lenge, abhi df5 se hi ATR approx
                # Yahan pehle df5 se hi analysis karte hain, Daily baad me Top 6 ke liye IND/NSE se confirm karenge
                # Daily ke liye pichhle din ka Close df_t se nikal lo - df_t ke pehle din ka aakhiri Close = Prev Close approx
                ana = analyze_full_day(df5, pd.DataFrame())
                if "error" in ana:
                    debug["yahoo_fail"].append(stock)
                    continue
                debug["yahoo_ok"] += 1
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
                rows.append({
                    "Stock": str(stock), "LTP": safe_float(ana.get("LTP",0)), "Gap %": safe_float(ana.get("Gap %",0)),
                    "VWAP": safe_float(ana.get("VWAP",0)), "ORB High": safe_float(ana.get("ORB High",0)), "ORB Low": safe_float(ana.get("ORB Low",0)),
                    "Day High": safe_float(ana.get("Day High",0)), "Day Low": safe_float(ana.get("Day Low",0)),
                    "Day Range %": safe_float(ana.get("Day Range %",0)), "Net Move %": safe_float(ana.get("Net Move %",0)),
                    "ATR %": safe_float(ana.get("ATR %",0)), "Range vs ATR": safe_float(ana.get("Range vs ATR",0)),
                    "Vol x": safe_float(ana.get("Vol x",0)), "Last 5min %": safe_float(ana.get("Last 5min %",0)),
                    "VWAP Pos %": safe_float(ana.get("VWAP Pos %",0)), "% VWAP Upar": safe_float(ana.get("% Candles VWAP Upar",0)),
                    "VWAP Cross": safe_int(ana.get("VWAP Cross",0)), "Wick": safe_float(ana.get("Wick Ratio",0)),
                    "Reversal": safe_int(ana.get("Reversal Count",0)),
                    "Movement Type": str(ana.get("Movement Type","")), "Movement Detail": str(ana.get("Movement Detail","")),
                    "Session Story": str(ana.get("Session Story","")), "S1": str(ana.get("S1 Dir","")), "S2": str(ana.get("S2 Dir","")), "S3": str(ana.get("S3 Dir","")),
                    "Direction": str(ana.get("Direction","")), "Pattern": str(ana.get("Pattern","")), "Movement": str(ana.get("Movement","")),
                    "Movement Started?": str(ana.get("Movement Started?","")), "Fake?": "HAAN - TRAP" if bool(ana.get("Fake Breakout", False)) else "NAHI",
                    "Probability %": int(score), "Gap": "✅" if c1_gap else "❌", "VWAP": "✅" if c2_vwap else "❌", "ORB": "✅" if c3_orb else "❌", "Volume": "✅" if c4_vol else "❌", "Volatility OK": "✅" if c5_ok else "❌", "Pass": f"{pass_count}/4",
                    "Source": "STEP1-Yahoo", "Candles": int(ana.get("Candles",0)),
                })
            except Exception as e:
                debug["yahoo_fail"].append(stock)
                continue
    except Exception as e:
        debug["yahoo_error"] = str(e)
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Probability %", ascending=False).reset_index(drop=True)
    return df, debug

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
        # 5minute ke liye 5x5 + Retry
        res5, logs5 = ind_historical_5x5_with_retry(pairs, "5minute", to_ms(start_dt), to_ms(end_dt), token)
        logs_all.extend([f"5minute: {l}" for l in logs5])
        # Daily ke liye bhi 5x5 + Retry - 1day ka window alag hai (35 din pehle se)
        end_d = datetime(trading_day.year, trading_day.month, trading_day.day, 15, 30, 0, tzinfo=IST)
        start_d = end_d - timedelta(days=35)
        resD, logsD = ind_historical_5x5_with_retry(pairs, "1day", to_ms(start_d), to_ms(end_d), token)
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
    # Agar IND Token nahi hai ya IND se data nahi aaya to Yahoo se same analysis karo taaki app khali na rahe.
    # Lekin Option Chain hamesha IND se hi aayega, Yahoo se NAHI.
    rows = []
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
            # Aaj ka din alag karo - aakhiri 75 candles
            df_today = df.tail(75).copy()
            df_today = df_today.rename(columns={"Open": "Open", "High": "High", "Low": "Low", "Close": "Close", "Volume": "Volume"})
            # Daily ke liye 1day download karo
            try:
                dfd_raw = yf.download(ticker, period="1mo", interval="1d", progress=False, auto_adjust=False)
                if isinstance(dfd_raw.columns, pd.MultiIndex):
                    dfd_raw.columns = dfd_raw.columns.get_level_values(0)
                dfd = dfd_raw.reset_index()[["Open", "High", "Low", "Close", "Volume"]].copy()
            except:
                dfd = pd.DataFrame()
            # Time column banao taaki analyze_full_day chal jaye
            if "Datetime" in df_today.columns:
                df_today["Time"] = pd.to_datetime(df_today["Datetime"])
            elif "Date" in df_today.columns:
                df_today["Time"] = pd.to_datetime(df_today["Date"])
            else:
                df_today["Time"] = pd.date_range(start=datetime.now(), periods=len(df_today), freq="5min")
            df5 = df_today[["Time", "Open", "High", "Low", "Close", "Volume"]].copy()
            ana = analyze_full_day(df5, dfd)
            if "error" in ana:
                continue
            c1_gap = abs(safe_float(ana.get("Gap %", 0))) > 0.30
            c2_vwap = (safe_float(ana.get("LTP", 0)) > safe_float(ana.get("VWAP", 0)) and safe_float(ana.get("Gap %", 0)) > 0) or (safe_float(ana.get("LTP", 0)) < safe_float(ana.get("VWAP", 0)) and safe_float(ana.get("Gap %", 0)) < 0)
            c3_orb = bool(ana.get("ORB Break", False))
            c4_vol = safe_float(ana.get("Vol x", 0)) > 1.5
            c5_volatility_ok = "CHOPPY" not in str(ana.get("Movement Type", "")) and "VOLATILE" not in str(ana.get("Movement Type", ""))
            score = 0
            if c1_gap:
                score += 15
            if c2_vwap:
                score += 15
            if c3_orb:
                score += 20
            if c4_vol:
                score += 15
            if c5_volatility_ok:
                score += 10
            if ana.get("Movement Started?") == "HAAN":
                score += 15
            if safe_float(ana.get("Trending Score", 0)) >= 60:
                score += 10
            if bool(ana.get("Fake Breakout", False)):
                score -= 30
            if "CHOPPY" in str(ana.get("Movement Type", "")):
                score -= 20
            if "SIDEWAYS" in str(ana.get("Movement Type", "")):
                score -= 15
            score = max(0, min(100, int(score)))
            pass_count = sum([c1_gap, c2_vwap, c3_orb, c4_vol])
            rows.append({
                "Stock": str(stock), "LTP": safe_float(ana.get("LTP", 0)), "Gap %": safe_float(ana.get("Gap %", 0)),
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
                "Source": "Yahoo-Fallback (Scan ke liye, Option Chain IND se hi)",
            })
        except:
            continue
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Probability %", ascending=False).reset_index(drop=True)
    return df

# ---------------- INDICES + NEWS ----------------
def fetch_indices_history():
    # Nifty / Bank Nifty / Sensex / Bankex - Pichhle 5 din ka move - Yahoo se kyunki Index ka IND Historical me alag scrip lagta hai, lekin Scan ka asli data IND se hai
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
    msg = f"TOP 5 - {datetime.now().strftime('%d %b %Y %H:%M')}\nExpiry: {expiry_str} | Capital: Rs 5000\n------------------------\n"
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
        get_resp = requests.get(url, headers=headers, timeout=10)
        sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None
        payload = {"message": f"Diary update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "content": content_b64}
        if sha:
            payload["sha"] = sha
        put_resp = requests.put(url, headers=headers, json=payload, timeout=15)
        if put_resp.status_code in (200, 201):
            return True, "GitHub me bhi save ho gaya"
        return False, f"GitHub Fail {put_resp.status_code} - {put_resp.text[:200]}"
    except Exception as e:
        return False, f"GitHub Error - {e}"

def save_trade(trade):
    # Kabhi crash nahi karega - har error ko pakad ke batayega
    try:
        _ensure_diary_csv()
        df = pd.read_csv(CSV_FILE)
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
        df = pd.read_csv(CSV_FILE)
        if df.empty:
            return df
        # id se ulta sort - naya pehle
        if "id" in df.columns:
            df = df.sort_values("id", ascending=False)
        return df
    except Exception:
        return pd.DataFrame(columns=DIARY_COLUMNS)

def update_trade_status(trade_id, status, exit_price, pnl):
    try:
        _ensure_diary_csv()
        df = pd.read_csv(CSV_FILE)
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
    st.title("Scanner V22 - Code se Search + Download Data (Tumko Upload Nahi Karna) - Full Day + PIN Hataya + Diary Fix")
    st.info("IND Token 24 ghante me expire hota hai. Roz subah naya Token banao: indstocks.com -> Login -> /app/api-trading/access-tokens -> Claim Your API Access -> Generate -> Copy karke yahan daalo.")
    st.write("V15 me Scan IND Historical Data se hota hai - 5minute candles se poora din dekha jata hai, sirf Open-High nahi.")
    # PIN HATA DIYA HAI - Ab sirf IND ka Secret Code hi kaafi hai. 4 ank ka Code ab kabhi nahi mangega.
    with st.form("login_form"):
        indmoney_secret = st.text_input("INDstocks Access Token - indstocks.com se - Roz naya wala", type="password", placeholder="indstocks.com/app/api-trading/access-tokens se Copy kiya hua Token")
        submit = st.form_submit_button("Scanner Kholo", use_container_width=True)
        if submit:
            if not indmoney_secret or len(indmoney_secret) < 10:
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
    if st.button("Bina Token ke Dekho - Scan Yahoo se hoga, Option Chain nahi aayega"):
        st.session_state.authenticated = True
        st.session_state.indmoney_secret = ""
        st.session_state.indmoney_connected = False
        st.rerun()
    st.stop()

# ---------------- TOP BAR ----------------
top_left, top_right = st.columns([4, 1])
with top_left:
    st.title("Scanner V22 - Code se Search + Download Data (Tumko Upload Nahi Karna) | Rs 5,000 | PIN Hataya | Diary Fix | Kisi bhi Time Scan")
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
                _dl_old_msg = f"⚠️ Master { _days_old } Din purana ho gaya - Option ka Expiry 7 Din me badalta hai, isliye Download Data dobara dabao, nahi to Expiry purani dikhegi. Stock ka Expiry 1 Mahine me badalta hai, wo abhi thik hai."
            elif _days_old >= 1:
                _dl_old_msg = f"Master { _days_old } Din purana hai - Option Expiry ke liye 7 Din me 1 baar Download Data dabao."
    except:
        pass
    if _dl_old_msg:
        st.warning(_dl_old_msg)
    if st.button("📥 Download Data - Teeno File GitHub me Save Karo (Tumko Upload Nahi Karna)", use_container_width=True, key="top_download_data"):
        _tok_top = st.session_state.get("indmoney_secret", "")
        if not _tok_top or len(str(_tok_top)) < 10:
            st.session_state["_master_dl_msg"] = "Pehle IND Token se Login karo - bina Token ke Master Download nahi hoga"
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
        st.caption(st.session_state["_master_dl_msg"])
    if st.session_state.get("master_dl_last_date"):
        st.caption(f"Last Master Download: {st.session_state['master_dl_last_date']} - Agla mahine me 1 baar")

if st.session_state.indmoney_connected:
    st.success(f"IND CONNECTED - {st.session_state.get('indmoney_debug','')} - Scan IND Historical se hoga")
else:
    st.warning("IND NOT CONNECTED - Scan Yahoo Fallback se hoga, Option Chain nahi aayega. Token daal ke Login karo.")

st.sidebar.title("Dashboard")
st.sidebar.markdown("### GitHub Secrets - Secret Jagah")
if GITHUB_TOKEN and GITHUB_REPO:
    st.sidebar.success(f"GitHub OK - {GITHUB_REPO}")
else:
    st.sidebar.warning("GitHub Token nahi hai - Diary Reboot pe udd jayegi. Diary kholo, wahan Secrets wala box dekho.")
    st.sidebar.code('GITHUB_TOKEN = "ghp_..."\nGITHUB_REPO = "username/repo"', language="text")
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
    st.markdown("## TRADING DIARY")
    # V21 - Diary ke andar bhi wahi Download Data Button - Kona me chhota sa, Diary ke paas hi
    # Mahine me 1 baar dabao - Master GitHub me apne aap save ho jayega, Expiry wahi se milegi
    col_diary_dl1, col_diary_dl2 = st.columns([3, 1])
    with col_diary_dl2:
        if st.button("📥 Download Data", use_container_width=True, key="diary_download_data"):
            _tok_d = st.session_state.get("indmoney_secret", "")
            if not _tok_d or len(str(_tok_d)) < 10:
                st.session_state["_master_dl_msg"] = "Pehle IND Token se Login karo - bina Token ke Master Download nahi hoga"
            else:
                with st.spinner("Monthly Master Download ho raha hai... GitHub me apne aap save ho raha hai..."):
                    _res_d, _msg_d = download_monthly_master_all(_tok_d)
                    _lines_d = []
                    for _fn, _b, _df, _ok, _m in _res_d:
                        _lines_d.append(f"{_fn}: {_m}")
                    st.session_state["_master_dl_msg"] = " | ".join(_lines_d)
                    st.session_state["master_dl_last_date"] = ist_now().strftime("%Y-%m-%d %H:%M")
            st.rerun()
    with col_diary_dl1:
        st.caption("Mahine me 1 baar Download Data dabao - Exchange, Segment, Security ID, Expiry - sab Master me aa jayega, GitHub me apne aap save hoga. Roz sirf Latest Price / Candle hi search karna padega.")
    if st.session_state.get("_master_dl_msg"):
        st.info(st.session_state["_master_dl_msg"])
    if st.session_state.get("master_dl_last_date"):
        st.caption(f"Last Master Download: {st.session_state['master_dl_last_date']}")
    if st.session_state.get("_diary_last_msg"):
        st.success(st.session_state["_diary_last_msg"])
    # GitHub Secrets ka status - yahi secret jagah hai
    if GITHUB_TOKEN and GITHUB_REPO:
        st.success(f"GitHub Connected - Repo: {GITHUB_REPO} - Diary GitHub me bhi save hogi, Reboot pe nahi udegi")
    else:
        st.warning("GitHub Token Secrets me nahi hai - Diary abhi sirf is App me save hogi, Reboot pe udd sakti hai. Neeche GitHub Secrets wala box dekho, usme daal do to hamesha ke liye save hogi.")
        with st.expander("GitHub Secrets - Kya chahiye, kahan daalna hai, ye dekho"):
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
        st.download_button("CSV Download Karo", data=trades_df_all.to_csv(index=False), file_name="all_trades.csv", mime="text/csv")
    if st.button("Diary Band Karo"):
        st.session_state.show_diary = False; st.rerun()
    st.divider()

# ---------------- V19 - MASTER CSV - DOWNLOAD BUTTON HATA DIYA - AB GITHUB FILE SE AAYEGA ----------------
# User ne bola: Download ka Option hata do. CSV hum Download karke GitHub pe Upload kar denge, ya tumko bhej denge, naam wahi rakh denge jo tum bologe.
# Naam jo bola hai wahi rakha hai: IND_Master_Equity.csv (aur IND_Master_FNO.csv) - Isko GitHub repo me app.py ke saath rakho.
# App ab Download nahi karega, GitHub wali File se hi Sahi Naam + Secret Code lega. Usme sab stock ka likha hua hoga.
# Agar GitHub pe file abhi nahi hai to neeche Upload se bhi de sakte ho - wo bhi Download nahi hai, Upload hai.
st.markdown("### IND Master - Security ID se Search - IND_master_index wali File se")
st.write("File ka naam: **IND_master_index.csv** + **IND_Master_FNO.csv** + **IND_Master_Equity.csv** - Ye 3 File Trading Diary ke paas wale **Download Data** Button se Mahine me 1 baar Download ho ke GitHub me apne aap save ho jayengi. App roz Download nahi karega, Exchange / Segment wala request bhi roz nahi bhejega, **roz sirf Security ID se search karega** - jo is File me likha hoga, wahi ID use hoga. Expiry bhi isi Master se milegi, baar-baar Expiry search nahi karni padegi. Roz sirf Latest Price / Candle jo move karega, wo hi Daily search karna padega.")
st.write("Tumko Upload nahi karna hai - Tum daloge to purana ho jayega. Download Data dabao, Streamlit ke paas jo GitHub ka Security Code hai, usi se app khud Download karke GitHub me save karega. Uske baad sab Data usi File se padha jayega, naam se Search nahi hoga, sirf Code se Search hoga, isliye Error aayega hi nahi.")
st.write("Expiry: Stock ka Expiry 1 Mahine me badalta hai, Option ka Expiry 7 Din me badalta hai - isliye 7 Din me 1 baar Download Data dabao, to Expiry hamesha fresh rahegi.")
st.write("Photo me jo 3rd file dikhi hai - IND Master Index - usme EXCH, SEGMENT, SECURITY_ID hai. SEGMENT wale column me Index ka naam hai - jaise NIFTY 50 = 40000001, NIFTY IT = 40000004. Stock wali File (IND_Master_Equity / FNO) bhi isi naam se rakhoge to wo bhi isi se milegi. RELIANCE ka Security ID = 2885, wahi se aayega - ISIN (INE002A01018) se mat milana, ISIN alag hai, Security ID alag hai.")
# GitHub File ka haal dikhao
try:
    _gh_df, _gh_msg = ind_load_master_from_github_file()
    if _gh_df is not None and not _gh_df.empty:
        st.success(f"✅ Master CSV GitHub File se mil gaya - {_gh_msg} - Isi se Sahi Naam + Code liya jayega.")
        st.session_state["master_equity_df"] = _gh_df
        _master_done = True
    else:
        st.warning(f"⚠️ GitHub pe IND_master_index.csv abhi nahi mila - {_gh_msg}. Tab tak KNOWN_SCRIP se kaam chalega, fail nahi hoga. GitHub pe file daal do, agle Reboot se wahi file use hogi.")
        _master_done = False
except Exception as e:
    st.warning(f"Master File check me error - {e}")
    _master_done = False
# V22 - Upload hata diya - Tumne bola hum nahi dalenge, hum dalenge to purana ho jayega, 23 tarikh ko expire ho jayega.
# Isliye tumko Upload nahi karna hai. Sirf upar wala Download Data dabana hai.
# Streamlit ke paas GitHub ka Security Code (GITHUB_TOKEN + GITHUB_REPO) hai hi, usi se app khud Download karke GitHub me save karega.
# Tumko kuch nahi dalna hai - Download Data dabao, teeno File GitHub me apne aap save ho jayengi.
st.info("📌 Tumko Upload nahi karna hai - Tum daloge to purana ho jayega, 23 tarikh ko expire ho jayega. Sirf upar / Diary ke paas wala **Download Data** dabao - Streamlit ke paas jo GitHub ka Security Code hai, usi se app khud teeno File Download karke GitHub me save karega. Uske baad sab Data usi File se padha jayega.")
if _master_done:
    # V20 - Ek example dikhao - RELIANCE ka Security ID File se kya aaya, taaki pata chale Security ID se hi khoj ho rahi hai
    try:
        _mp = ind_get_all_scrips(st.session_state.get("indmoney_secret", ""))
        _rel_id = _mp.get("RELIANCE", "")
        _nif_id = _mp.get("NIFTY 50", _mp.get("NIFTY", ""))
        if _rel_id:
            st.success(f"✅ Security ID se Search ON hai - RELIANCE ka Security ID File se aaya: {_rel_id} - Isi ID se ab Historical + Option Chain khoja jayega, Exchange/Segment wala request nahi jayega. NIFTY 50 ka ID: {_nif_id if _nif_id else 'Index File me dekho'}")
    except:
        pass
    with st.expander("Hamare 138 Stocks ka IND me Sahi Naam + Secret Code - GitHub wali File se - Yahi Table Dekh Ke Naam Likho", expanded=False):
        try:
            _mt = ind_build_master_table(st.session_state.get("master_equity_df", pd.DataFrame()))
            if not _mt.empty:
                _prob = _mt[_mt["Status"].str.contains("ALAG|Nahi Mila", na=False)]
                _ok = _mt[_mt["Status"].str.contains("SAME", na=False)]
                st.write(f"Total: {len(_mt)} | ✅ Same Naam: {len(_ok)} | ⚠️ Naam Alag / ❌ Nahi Mila: {len(_prob)} - Inhi ki wajah se pehle fail hota tha")
                if not _prob.empty:
                    st.write("Pehle ye wale dekho - Inka IND wala naam alag hai:")
                    st.dataframe(_prob, use_container_width=True, hide_index=True)
                st.write("Sab 138 ka poora Master Table (GitHub File se):")
                st.dataframe(_mt, use_container_width=True, hide_index=True)
            else:
                st.write("Master Table khali hai - GitHub pe IND_master_index.csv daalo")
        except Exception as e:
            st.write(f"Master Table me error - {e}")
    _logs5 = st.session_state.get("ind_5x5_logs", [])
    if _logs5:
        with st.expander("IND 5-5 + 1-1 Retry ka Log", expanded=False):
            for _l in _logs5:
                st.write(_l)
st.divider()

# ---------------- V19 - SINGLE STOCK SEARCH - RELIANCE ya RIL likho, Suggestion dega, 3-Jagah se Check karega ----------------
# User ka naya Option: Hum jo stock search karein, stock ka naam likhein - jaise RELIANCE ya RIL likhein, to Suggestion de de RELIANCE ka, phir usko search karke bataye ki kitne Criteria pe fit ho raha hai aur 100 me se kitne ank mile.
# Ye 5 ka example nahi hai - ye koi bhi 1 stock ke liye hai, jab tum chaaho tab check karo, poora Scan kiye bina.
st.markdown("### 🔍 Ek Stock Search Karo - RELIANCE ya RIL likho - Suggestion milega, 3-Jagah se Check hoga, 100 me se Score milega")
st.write("Yahan koi bhi 1 stock likho - jaise `RIL` likhoge to `RELIANCE` ka Suggestion aayega, `HDFC` likhoge to `HDFCBANK` ka. Phir usko Yahoo + NSE + IND (GitHub CSV wala Code) - teeno se check karke batayenge ki kitne Criteria pe fit hai aur 100 me se kitne ank mile.")
_single_input = st.text_input("Stock ka Naam likho - jaise RELIANCE, RIL, HDFC, BHEL, TATA", placeholder="RIL likho to RELIANCE milega", key="single_stock_input")
_single_resolved = None
_single_sugg = []
if _single_input:
    _single_resolved, _single_sugg = resolve_stock_name(_single_input)
    if _single_resolved:
        st.success(f"Suggestion: **{_single_resolved}** - Yahi stock check hoga. Agar ye sahi nahi hai to neeche wale Dropdown se doosra chuno.")
    elif _single_sugg:
        st.info(f"Kai stock mile - Neeche Dropdown se chuno: {', '.join(_single_sugg)}")
        _single_resolved = st.selectbox("Suggestion me se chuno", _single_sugg, key="single_stock_select")
    else:
        st.warning(f"'{_single_input}' se koi stock nahi mila - Sahi naam likho jaise RELIANCE, BHEL, ya thoda chhota likho jaise REL, TATA")
        # Dropdown me sab dikha do taaki wahan se chun sake
        _single_resolved = st.selectbox("Ya yahan se chuno - saare 138 stocks", list(MARKET_STOCKS.keys()), key="single_stock_all_select")
else:
    # Khali hai to bhi Dropdown de do - wahan se bhi chun sakte ho
    _single_resolved = st.selectbox("Ya yahan se stock chuno", [""] + list(MARKET_STOCKS.keys()), key="single_stock_dropdown_empty")
    if _single_resolved == "":
        _single_resolved = None
if _single_resolved:
    # V22 - Single Search bhi Code se hi hoga - naam sirf Suggestion ke liye hai, andar Code se khojenge
    # Pehle Code nikal lo, phir dikhao - taaki pata chale naam se nahi, Code se search ho raha hai
    try:
        _map_single = ind_get_all_scrips(st.session_state.get("indmoney_secret", ""))
        _code_single = _map_single.get(_single_resolved, _map_single.get(_single_resolved.upper(), ""))
        if _code_single:
            st.success(f"✅ {_single_resolved} ka Code mil gaya - **Security ID: {_code_single}** - Ab iska Search naam se nahi, sirf isi Code se hoga, isliye Error aayega hi nahi. Code pehle se hi Master File me tha.")
        else:
            st.warning(f"{_single_resolved} ka Code Master File me nahi mila - Pehle upar wala Download Data dabao, phir Code aa jayega. Download Data se Code GitHub wali File se aayega.")
    except Exception as e:
        st.write(f"Code check me error - {e}")
    if st.button(f"{_single_resolved} ko Code se Check Karo - Yahoo + NSE + IND - 100 me se Score (Naam se nahi, Code se)", use_container_width=True, key="single_check_btn"):
        with st.spinner(f"{_single_resolved} ko Yahoo + NSE + IND - teeno se check kar rahe hain..."):
            # STEP 1 - Yahoo se is 1 stock ka data
            _ticker = MARKET_STOCKS.get(_single_resolved, f"{_single_resolved}.NS")
            _y_ana = None; _y_msg = ""
            try:
                _df_y = yf.download(_ticker, period="2d", interval="5m", progress=False, auto_adjust=False)
                if _df_y is not None and not _df_y.empty:
                    _df_y = _df_y.reset_index()
                    for _c in ['High','Low','Close','Volume','Open']:
                        if _c in _df_y.columns and isinstance(_df_y[_c], pd.DataFrame):
                            _df_y[_c] = _df_y[_c].iloc[:, 0]
                    _df_today = _df_y.tail(75).copy()
                    if "Datetime" in _df_today.columns:
                        _df_today["Time"] = pd.to_datetime(_df_today["Datetime"])
                    elif "Date" in _df_today.columns:
                        _df_today["Time"] = pd.to_datetime(_df_today["Date"])
                    else:
                        _df_today["Time"] = pd.date_range(start=datetime.now(), periods=len(_df_today), freq="5min")
                    _df5_y = _df_today[["Time","Open","High","Low","Close","Volume"]].copy()
                    _y_ana = analyze_full_day(_df5_y, pd.DataFrame())
                    _y_msg = f"Yahoo se aaya - {len(_df5_y)} candles"
                else:
                    _y_msg = "Yahoo se khali aaya"
            except Exception as e:
                _y_msg = f"Yahoo Error - {e}"
            # STEP 2 - NSE se is 1 stock ka data
            _nse_q = None; _nse_qmsg = ""; _nse_oc = pd.DataFrame(); _nse_ocmsg = ""
            try:
                _sess = nse_get_session()
                _nse_q, _nse_qmsg = nse_get_quote(_single_resolved, _sess)
                _nse_oc, _nse_ocmsg = nse_get_option_chain(_single_resolved, _sess)
            except Exception as e:
                _nse_qmsg = f"NSE Error - {e}"
            # STEP 3 - IND se is 1 stock ka data - GitHub CSV wale Code se
            _ind_ana = None; _ind_msg = ""; _ind_chain = pd.DataFrame(); _ind_chain_msg = ""
            try:
                _tok3 = st.session_state.get("indmoney_secret", "")
                _scrip_map3 = ind_get_all_scrips(_tok3) if _tok3 else dict(KNOWN_SCRIP)
                _sid3, _src3 = ind_get_scrip(_single_resolved, _tok3, _scrip_map3)
                if _sid3:
                    _td3 = get_trading_day()
                    _multi3 = ind_get_multi_timeframe(_single_resolved, _sid3, _tok3, _td3)
                    _df5_ind = _multi3.get("df_5min", None)
                    _dfd_ind = _multi3.get("df_daily", pd.DataFrame())
                    if _df5_ind is not None and len(_df5_ind) > 0:
                        _ind_ana = analyze_full_day(_df5_ind, _dfd_ind if _dfd_ind is not None else pd.DataFrame())
                        _ind_msg = f"IND se aaya - Code {_sid3} (GitHub CSV wala) - {len(_df5_ind)} candles"
                    else:
                        _ind_msg = f"IND Historical khali - Code {_sid3} - {_multi3.get('debug',[])}"
                    # Option Chain bhi IND se - Expiry Fallback ke saath
                    _ind_chain, _ind_chain_msg, _exp3, _scrip3, _ltp3 = ind_get_option_chain(_single_resolved, _tok3, _scrip_map3)
                    _ind_msg += f" | Option: {_ind_chain_msg}"
                else:
                    _ind_msg = f"IND Scrip nahi mila - {_src3} - GitHub CSV me iska Sahi Naam check karo"
            except Exception as e:
                _ind_msg = f"IND Error - {e}"
            # COMBINED - teeno se data lo, sabko Compromise Milao - jo jahan se perfect mil raha hai, wahi lo
            # LTP: NSE ka LTP sabse fresh hota hai, agar NSE nahi de paya to IND, phir Yahoo
            # Gap/VWAP/ORB/Volume: Yahoo ka 5min sabse poora hota hai, NSE/IND se Confirm karo
            # OI/Option: IND/NSE ka Option Chain sabse sahi hota hai
            _best_ana = _y_ana if _y_ana is not None and "error" not in _y_ana else (_ind_ana if _ind_ana is not None and "error" not in _ind_ana else None)
            st.session_state["single_result"] = {"stock": _single_resolved, "y_ana": _y_ana, "y_msg": _y_msg, "nse_q": _nse_q, "nse_qmsg": _nse_qmsg, "nse_oc": _nse_oc, "nse_ocmsg": _nse_ocmsg, "ind_ana": _ind_ana, "ind_msg": _ind_msg, "ind_chain": _ind_chain, "ind_chain_msg": _ind_chain_msg, "best_ana": _best_ana}
        st.rerun()
# Single ka Result dikhao
if st.session_state.get("single_result"):
    _sr = st.session_state["single_result"]
    _stk = _sr.get("stock", "")
    st.markdown(f"### {_stk} ka Result - 3-Jagah se Milake - Compromise Mix")
    st.write(f"**Yahoo:** {_sr.get('y_msg','')} | **NSE:** {_sr.get('nse_qmsg','')} | Option: {_sr.get('nse_ocmsg','')} | **IND:** {_sr.get('ind_msg','')}")
    # Kahan se kya aaya - Compromise Table
    _yA = _sr.get("y_ana") or {}; _iA = _sr.get("ind_ana") or {}; _nQ = _sr.get("nse_q") or {}
    _comp_rows = [
        {"Cheez": "LTP", "Yahoo se": safe_float(_yA.get("LTP",0)) if _yA else 0, "NSE se": safe_float(_nQ.get("LTP",0)) if _nQ else 0, "IND se": safe_float(_iA.get("LTP",0)) if _iA else 0, "Final (Compromise) - Kisko Mana": "NSE ka LTP sabse fresh, nahi to IND, nahi to Yahoo"},
        {"Cheez": "Gap %", "Yahoo se": safe_float(_yA.get("Gap %",0)) if _yA else 0, "NSE se": safe_float(_nQ.get("Change%",0)) if _nQ else 0, "IND se": safe_float(_iA.get("Gap %",0)) if _iA else 0, "Final (Compromise) - Kisko Mana": "Yahoo + IND ka Gap same hona chahiye, NSE se Confirm"},
        {"Cheez": "VWAP", "Yahoo se": safe_float(_yA.get("VWAP",0)) if _yA else 0, "NSE se": safe_float(_nQ.get("VWAP",0)) if _nQ else 0, "IND se": safe_float(_iA.get("VWAP",0)) if _iA else 0, "Final (Compromise) - Kisko Mana": "Yahoo VWAP, NSE/IND se Confirm"},
        {"Cheez": "Day High", "Yahoo se": safe_float(_yA.get("Day High",0)) if _yA else 0, "NSE se": safe_float(_nQ.get("High",0)) if _nQ else 0, "IND se": safe_float(_iA.get("Day High",0)) if _iA else 0, "Final (Compromise) - Kisko Mana": "Teeno me jo sabse zyada hai, wahi sahi High"},
        {"Cheez": "Day Low", "Yahoo se": safe_float(_yA.get("Day Low",0)) if _yA else 0, "NSE se": safe_float(_nQ.get("Low",0)) if _nQ else 0, "IND se": safe_float(_iA.get("Day Low",0)) if _iA else 0, "Final (Compromise) - Kisko Mana": "Teeno me jo sabse kam hai, wahi sahi Low"},
        {"Cheez": "Volume x", "Yahoo se": safe_float(_yA.get("Vol x",0)) if _yA else 0, "NSE se": safe_float(_nQ.get("Volume",0)) if _nQ else 0, "IND se": safe_float(_iA.get("Vol x",0)) if _iA else 0, "Final (Compromise) - Kisko Mana": "Yahoo Vol x, NSE Volume se Confirm"},
    ]
    st.dataframe(pd.DataFrame(_comp_rows), use_container_width=True, hide_index=True)
    _best = _sr.get("best_ana")
    if _best is not None and "error" not in _best:
        _break_df, _total = calc_probability_breakdown(_best)
        st.markdown(f"### {_stk} ka Score - 100 me se **{_total}** ank mile - Kaise bana, ye dekho")
        st.dataframe(_break_df, use_container_width=True, hide_index=True)
        st.write(f"**Final Probability: {_total}/100** - Gap + VWAP + ORB + Volume + Movement + Trending + Volatility - Fake/Choppy/Sideways kaat ke. Pehle sirf 70/60 likha aata tha, ab poora hisab dikh raha hai ki 70 kaise bana.")
        # Pass count bhi
        _pass_n = int(sum([1 for _, r in _break_df.iterrows() if r["Pass?"] == "✅ PASS" and r["Max"] > 0 and r["Criteria"].startswith(("1.","2.","3.","4."))]))
        st.write(f"**4 Main Criteria me se {_pass_n}/4 Pass** - Gap, VWAP, ORB, Volume - 4 me se 4 pass ho to Fulfill maana jata hai, 3 pass ho to bhi dekh sakte ho.")
        st.write(f"**Movement:** {_best.get('Movement Type','')} - {_best.get('Movement Detail','')} | **Session:** {_best.get('Session Story','')} | **Fake?** {'HAAN - TRAP' if _best.get('Fake Breakout') else 'NAHI'}")
    else:
        st.warning("Yahoo + IND dono se poora data nahi aaya, isliye 100 wala Score nahi bana - Upar wali 3-Jagah wali line me dekho kahan se kya aaya, kahan fail hua.")
    # Single ka Option Chain - pehle NSE, phir IND
    _nse_oc_s = _sr.get("nse_oc", pd.DataFrame())
    _ind_ch_s = _sr.get("ind_chain", pd.DataFrame())
    if _nse_oc_s is not None and not _nse_oc_s.empty:
        st.write("**Option Chain - NSE se aaya:**")
        st.dataframe(_nse_oc_s.head(15), use_container_width=True, hide_index=True)
    elif _ind_ch_s is not None and not _ind_ch_s.empty:
        st.write("**Option Chain - IND se aaya (NSE nahi de paya):**")
        st.dataframe(_ind_ch_s.head(15), use_container_width=True, hide_index=True)
    else:
        st.write(f"Option Chain nahi aaya - NSE: {_sr.get('nse_ocmsg','')} | IND: {_sr.get('ind_chain_msg','')}")
st.divider()

# ---------------- SCAN BUTTON ----------------
# Scan ka Time Window dikhao - taaki pata chale 09:20 pe scan ho raha hai ya 02:00 pe
try:
    _td = get_trading_day()
    _s, _e = get_scan_window(_td)
    st.info(f"Abhi Time: {ist_now().strftime('%H:%M:%S')} | Trading Day: {_td} | Scan Window: {_s.strftime('%H:%M')} se {_e.strftime('%H:%M')} tak ki candles li jayengi - 09:20 ho ya 09:35 ho ya 01:00 / 02:00, sab chalega. Fixed 09:20 nahi hai.")
except Exception as e:
    pass

# Manual News wala stock - jaise BHEL me 2.5 lakh crore ka deal hua to BHEL bhag sakta hai, wo Yahoo Top 5 me nahi bhi ho to bhi hum usko Step 2 me lenge
st.markdown("### News wala Stock Add Karo - Agar kisi stock me badi khabar aayi hai to yahan likho")
manual_input = st.text_input("News wala Stock - jaise BHEL, SUZLON - comma se alag karke likho (khali bhi chhod sakte ho)", placeholder="BHEL, SUZLON", key="manual_news_input")
manual_list = []
if manual_input:
    for _x in manual_input.split(","):
        _x = _x.strip().upper()
        if _x and _x in MARKET_STOCKS:
            manual_list.append(_x)
        elif _x:
            # Agar user ne BHEL likha to MARKET_STOCKS me hai, agar nahi hai to batado
            st.warning(f"{_x} list me nahi hai - MARKET_STOCKS me check karo, sahi naam likho jaise BHEL")
if manual_list:
    st.success(f"Manual add hoga: {', '.join(manual_list)} - Ye Top 5 me nahi bhi hoga to bhi Step 2 (NSE) + Step 3 (IND) me jayega, kyunki News se bhag sakta hai")

if st.button("SCAN NOW - 3 STEP - Yahoo -> NSE -> IND", use_container_width=True):
    with st.spinner("STEP 1 chal raha hai... Yahoo/Google se 138 stocks ka data ek saath aa raha hai..."):
        # STEP 1 - Yahoo se sab
        df_step1, debug1 = yahoo_scan_all_3step()
        st.session_state.scan_df = df_step1
        st.session_state.step1_debug = debug1
        st.session_state.scan_time = datetime.now().strftime("%H:%M:%S")
        # V19 FIX: 5 sirf UDAHARAN tha, LIMIT nahi tha. Pehle hum sirf Top 5 ko NSE pe bhejte the, isliye baaki high-probability wale chhoot jaate the.
        # Ab: Top 15 + Jinka Probability >=50 hai, wo sab NSE pe jayenge + Manual News wale alag se.
        # Isse NSE pe bojh bhi kam rahega (15, 138 nahi) aur koi achha stock chhootega bhi nahi.
        # Top 15 + Prob>=50 + Manual = Selected
        selected = []
        if not df_step1.empty:
            _top15 = df_step1.head(15)["Stock"].tolist()
            _prob50 = df_step1[df_step1["Probability %"] >= 50]["Stock"].tolist()
            for _s in _top15 + _prob50:
                if _s not in selected:
                    selected.append(_s)
            # Agar Top 15 me bhi 15 se kam hai to jitne hain utne hi
            selected = selected[:20]  # Max 20 - isse zyada NSE pe ek saath mat bhejo, nahi to 403 dega
        for m in manual_list:
            if m not in selected:
                selected.append(m)
        # Agar Step 1 me hi 0 aaya to bhi manual wale ko le lo
        if not selected and manual_list:
            selected = manual_list[:]
        st.session_state.selected_stocks = selected
        st.session_state.scan_source = f"3-STEP: STEP1 Yahoo {debug1.get('yahoo_ok',0)}/{debug1.get('yahoo_total',0)} OK"
    # STEP 2 - NSE - sirf Selected 6 ko
    step2_results = {}
    if selected:
        with st.spinner(f"STEP 2 chal raha hai... NSE pe sirf {len(selected)} stocks (Top 15 + Prob>=50 + Manual - 5 sirf example tha, limit nahi) check ho rahe hain - {', '.join(selected)} - Poora 138 NSE pe nahi, sirf 6, isliye NSE block nahi karega..."):
            nse_session = nse_get_session()
            for sym in selected:
                try:
                    q, qmsg = nse_get_quote(sym, nse_session)
                    oc, ocmsg = nse_get_option_chain(sym, nse_session)
                    # NSE se jo mila wo rakho, jo nahi mila wo khali chhodo - Step 3 me IND se bharenge
                    step2_results[sym] = {"quote": q, "quote_msg": qmsg, "option_df": oc, "option_msg": ocmsg, "nse_ok": (q is not None)}
                    time.sleep(0.5)  # NSE ko 3/sec se zyada mat maaro, nahi to 403 dega
                except Exception as e:
                    step2_results[sym] = {"quote": None, "quote_msg": f"NSE Error {e}", "option_df": pd.DataFrame(), "option_msg": f"Error {e}", "nse_ok": False}
            st.session_state.step2_results = step2_results
    # STEP 3 - IND - sirf jo NSE nahi de paya, wahi IND se
    step3_results = {}
    token = st.session_state.get("indmoney_secret", "")
    if selected and token and len(str(token)) > 10:
        # Kaun se stocks ko IND chahiye? Jinka NSE quote fail hua ya Option Chain fail hua
        need_ind = []
        for sym in selected:
            r2 = step2_results.get(sym, {})
            if r2.get("quote") is None or (r2.get("option_df") is None or r2.get("option_df").empty if isinstance(r2.get("option_df"), pd.DataFrame) else True):
                need_ind.append(sym)
        st.session_state.need_ind = need_ind
        if need_ind:
            with st.spinner(f"STEP 3 chal raha hai... IND se sirf {len(need_ind)} stocks mang rahe hain - {', '.join(need_ind)} - Jo NSE de chuka hai wo IND se dobara nahi mangenge, isliye IND pe bojh 97% kam hai..."):
                try:
                    scrip_map = ind_get_all_scrips(token)
                except:
                    scrip_map = dict(KNOWN_SCRIP)
                step3_results = ind_fill_for_selected(need_ind, token, scrip_map)
                st.session_state.step3_results = step3_results
        else:
            st.session_state.step3_results = {}
            st.session_state.need_ind = []
    else:
        st.session_state.step3_results = {}
        st.session_state.need_ind = []
    # Indices + News
    try:
        indices_df = fetch_indices_history(); news_df = fetch_global_news()
    except:
        indices_df = pd.DataFrame(); news_df = pd.DataFrame()
    st.session_state.indices_data = indices_df; st.session_state.news_data = news_df
    st.session_state.auto_sent = False
    if not df_step1.empty:
        top = df_step1.iloc[0]
        if safe_float(top.get("Probability %", 0)) >= 70:
            ok_auto = send_top5(df_step1.head(5), "3-STEP: Yahoo->NSE->IND")
            st.session_state.auto_sent = ok_auto
    st.rerun()

# ---------------- RESULTS ----------------
if st.session_state.scan_df is not None and not st.session_state.scan_df.empty:
    df_scan = st.session_state.scan_df; indices_df = st.session_state.indices_data; news_df = st.session_state.news_data
    st.info(f"Scan Source: {st.session_state.get('scan_source','')} | Scan Time: {st.session_state.get('scan_time','')} | Total Stocks Checked: {len(df_scan)}")
    # 3-STEP DEBUG - Har step me kitne aaye, kyu fail hua, sab dikhao - chhupao mat
    _dbg1 = st.session_state.get("step1_debug", {})
    _sel = st.session_state.get("selected_stocks", [])
    _s2 = st.session_state.get("step2_results", {})
    _s3 = st.session_state.get("step3_results", {})
    _need = st.session_state.get("need_ind", [])
    with st.expander("3-STEP DEBUG - Step 1 / 2 / 3 me kitne aaye, kyu fail hua, ye dekho"):
        st.write(f"STEP 1 - Yahoo/Google: OK {_dbg1.get('yahoo_ok',0)} / {_dbg1.get('yahoo_total',138)} | Fail: {len(_dbg1.get('yahoo_fail',[]))} - { _dbg1.get('yahoo_fail',[])[:10]}")
        st.write(f"Selected (Top 15 + Prob>=50 + Manual News wale - 5 sirf example tha): {_sel}")
        st.write(f"STEP 2 - NSE: Har stock ka haal neeche table me hai - NSE 403 aana normal hai, uska matlab IND se lenge, fail nahi hai")
        if _s2:
            for _k, _v in _s2.items():
                st.write(f"  - {_k}: Quote: {_v.get('quote_msg','')} | Option: {_v.get('option_msg','')}")
        else:
            st.write("  STEP 2 abhi nahi chala ya selected khali tha")
        st.write(f"STEP 3 - IND: Sirf inko IND se manga: {_need} - Baaki ko IND se manga hi nahi, kyunki NSE de chuka tha, isliye IND pe bojh 97% kam hai")
        if _s3:
            for _k, _v in _s3.items():
                st.write(f"  - {_k}: {_v.get('reason','')}")
        st.write("PEHLE WALA 86 FAIL KYU HUA THA: 138 stocks ko IND se 5-5 batch me mangte the, 1 galat scrip-code se poora batch 400 de deta tha - 5 ke 5 udd jate the. Ab V18 me 5-5 hi rahega, lekin fail wale batch ke 5 ko 1-1 karke retry karenge, to 4 sahi wale bach jayenge.")
    _logs5b = st.session_state.get("ind_5x5_logs", [])
    if _logs5b:
        st.write("IND 5-5 + 1-1 Retry Log:")
        for _ll in _logs5b:
            st.write(f"  - {_ll}")
    # V19 - Top 5 ka 100 me se Score kaise bana - yehi gayab ho gaya tha
    if not df_scan.empty:
        with st.expander("Top 5 ka 100 me se Score kaise bana - Gap 15 + VWAP 15 + ORB 20 + Volume 15 + Movement 15 + Trending 10 + Volatility 10 - Fake/Choppy kaat ke", expanded=False):
            for _idx in range(min(5, len(df_scan))):
                _row = df_scan.iloc[_idx]
                _stk = _row.get("Stock", "")
                _prob = int(safe_float(_row.get("Probability %", 0)))
                st.markdown(f"**{_idx+1}. {_stk} - { _prob }/100**")
                # Is row se breakdown banao - df_scan me saare Criteria hain
                _brows = [
                    {"Criteria": "1. Gap", "Value": f"{safe_float(_row.get('Gap %',0)):+.2f}%", "Pass?": _row.get("Gap",""), "Ank": 15 if _row.get("Gap","")=="✅" else 0, "Max": 15},
                    {"Criteria": "2. VWAP", "Value": f"LTP {safe_float(_row.get('LTP',0)):.2f} vs VWAP {safe_float(_row.get('VWAP',0)):.2f}", "Pass?": _row.get("VWAP",""), "Ank": 15 if _row.get("VWAP","")=="✅" else 0, "Max": 15},
                    {"Criteria": "3. ORB Break", "Value": f"ORB High {safe_float(_row.get('ORB High',0)):.2f}", "Pass?": _row.get("ORB",""), "Ank": 20 if _row.get("ORB","")=="✅" else 0, "Max": 20},
                    {"Criteria": "4. Volume", "Value": f"{safe_float(_row.get('Vol x',0)):.2f}x", "Pass?": _row.get("Volume",""), "Ank": 15 if _row.get("Volume","")=="✅" else 0, "Max": 15},
                    {"Criteria": "5. Movement Started?", "Value": str(_row.get("Movement Started?","")), "Pass?": "✅" if str(_row.get("Movement Started?",""))=="HAAN" else "❌", "Ank": 15 if str(_row.get("Movement Started?",""))=="HAAN" else 0, "Max": 15},
                    {"Criteria": "6. Trending / 7. Volatility", "Value": f"{_row.get('Movement Type','')} | Pass: {_row.get('Pass','')}", "Pass?": _row.get("Volatility OK",""), "Ank": "Baki 20 ank Trending+Volatility se - poora hisab Single Search me dekho", "Max": 20},
                    {"Criteria": "KATOTI Fake/Choppy", "Value": f"Fake: {_row.get('Fake?','')} | Movement: {_row.get('Movement Type','')}", "Pass?": "❌ KATA" if "TRAP" in str(_row.get("Fake?","")) else "✅ SAHI", "Ank": "-30 agar Fake hai", "Max": 0},
                ]
                st.dataframe(pd.DataFrame(_brows), use_container_width=True, hide_index=True)
                st.write(f"Final: {_prob}/100 - Poora 100 wala hisab Single Search me us stock ko alag se check karne pe bhi dikhega.")

    # STEP 2 TABLE
    if _s2:
        st.markdown("### STEP 2 - NSE Check - Selected (Top 15 + Prob>=50 + Manual) ka - 5 sirf example tha - Jo NSE de paya wo NSE se, jo nahi de paya wo Step 3 me IND se")
        _rows2 = []
        for _k, _v in _s2.items():
            _q = _v.get("quote") or {}
            _rows2.append({"Stock": _k, "NSE LTP": safe_float(_q.get("LTP",0)) if _q else 0, "NSE Open": safe_float(_q.get("Open",0)) if _q else 0, "NSE High": safe_float(_q.get("High",0)) if _q else 0, "NSE Low": safe_float(_q.get("Low",0)) if _q else 0, "NSE PrevClose": safe_float(_q.get("PrevClose",0)) if _q else 0, "NSE Quote": _v.get("quote_msg",""), "NSE Option": _v.get("option_msg",""), "NSE OK?": "✅ NSE SE MILA" if _v.get("nse_ok") else "❌ NSE FAIL - IND se lenge"})
        st.dataframe(pd.DataFrame(_rows2), use_container_width=True, hide_index=True)
    if _s3:
        st.markdown("### STEP 3 - IND Fill - Sirf jo NSE nahi de paya, wahi IND se")
        _rows3 = []
        for _k, _v in _s3.items():
            _rows3.append({"Stock": _k, "IND Result": _v.get("reason",""), "IND OK?": "✅ IND SE MILA" if _v.get("ok") else "❌ IND FAIL - Yahoo+NSE ka data hi use karenge"})
        st.dataframe(pd.DataFrame(_rows3), use_container_width=True, hide_index=True)
    if st.session_state.get("auto_sent"):
        st.success("Chala gaya ✅")
    st.markdown("### 1. PICHHLA MOVE - Nifty / Bank Nifty / Sensex / Bankex")
    if indices_df is not None and not indices_df.empty:
        st.dataframe(indices_df, use_container_width=True, hide_index=True)
    st.markdown("### 2. GLOBAL NEWS - Isse Probability upar-neeche hogi")
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
    st.markdown("### 3. TOP 5 STOCKS - Full Day Movement ke saath")
    top5 = df_scan.head(5)
    st.dataframe(top5[["Stock", "LTP", "Gap %", "Direction", "Pattern", "Movement Type", "Probability %", "Movement", "Movement Started?", "Pass"]], use_container_width=True, hide_index=True)
    top1 = df_scan.iloc[0]; top1_stock = str(top1.get("Stock", "")); top1_prob = safe_float(top1.get("Probability %", 0)); top1_ltp = safe_float(top1.get("LTP", 0))
    st.success(f"No.1: {top1_stock} - Prob {top1_prob:.0f}% - LTP Rs {top1_ltp:.1f} - {top1.get('Movement Type','')}")
    st.write(f"No.1 ka Poora Din: {top1.get('Movement Detail','')}")
    st.write(f"Session: {top1.get('Session Story','')}")
    if st.button("SEND NOTIFICATION - TOP 5", use_container_width=True):
        ok = send_top5(top5, "IND se")
        if ok:
            st.success("Chala gaya ✅")
        else:
            st.error("Nahi gaya ❌")
    st.markdown("### 4. FULL DAY MOVEMENT - Kaunsa Sideways hai, Kaunsa Bhag Raha hai, Kaunsa Volatile hai")
    st.write("Sideways = Option mat lo, wait karo. Bhag Raha = Option le sakte ho. Volatile/Choppy = Premium kha jayega, mat lo. Fake = Trap tha.")
    st.dataframe(df_scan[["Stock", "LTP", "Day Range %", "Net Move %", "Range vs ATR", "Movement Type", "Session Story", "VWAP Cross", "Wick", "Reversal", "Fake?", "Probability %"]], use_container_width=True, hide_index=True)
    st.markdown("### 5. PURA MARKET - 5 Conditions Pass / Fail")
    st.dataframe(df_scan[["Stock", "LTP", "Gap %", "Direction", "Pattern", "Movement Type", "Probability %", "Gap", "VWAP", "ORB", "Volume", "Volatility OK", "Movement Started?", "Pass"]], use_container_width=True, hide_index=True)
    st.markdown("### 6. OPTION CHAIN - INDstocks se hi aayega, NSE Website se NAHI, Yahoo se NAHI")
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
        if st.button(f"{sel_stock} ka Option Chain Mango - Pehle NSE, phir IND", use_container_width=True):
            with st.spinner("Pehle NSE se Option Chain dekh rahe hain, jo NSE nahi dega wo IND se lenge..."):
                # STEP 2 ka NSE Option Chain pehle check karo - agar wahan hai to wahi use karo, IND ko pareshan mat karo
                _s2_all = st.session_state.get("step2_results", {})
                _nse_oc = None
                _nse_msg = ""
                if sel_stock in _s2_all:
                    _nse_oc = _s2_all[sel_stock].get("option_df", pd.DataFrame())
                    _nse_msg = _s2_all[sel_stock].get("option_msg", "")
                if _nse_oc is not None and not _nse_oc.empty and len(_nse_oc) >= 5:
                    st.session_state[f"chain_{sel_stock}"] = _nse_oc; st.session_state[f"chain_source_{sel_stock}"] = f"NSE SE AAYA - {_nse_msg}"; st.session_state[f"expiry_{sel_stock}"] = "NSE Expiry (Nearest)"; st.session_state[f"scrip_{sel_stock}"] = "NSE"; st.session_state[f"indltp_{sel_stock}"] = ""
                else:
                    # NSE nahi de paya to IND se
                    token_now = st.session_state.get("indmoney_secret", "")
                    scrip_map_now = ind_get_all_scrips(token_now) if token_now else {}
                    chain_df, source, expiry_yyyy, scrip_used, ind_ltp = ind_get_option_chain(sel_stock, token_now, scrip_map_now)
                    st.session_state[f"chain_{sel_stock}"] = chain_df; st.session_state[f"chain_source_{sel_stock}"] = f"IND SE AAYA (NSE nahi de paya: {_nse_msg}) - {source}"; st.session_state[f"expiry_{sel_stock}"] = expiry_yyyy; st.session_state[f"scrip_{sel_stock}"] = scrip_used; st.session_state[f"indltp_{sel_stock}"] = ind_ltp
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
                if st.button(f"{sel_stock} {strike} {opt_type} ka Notification Bhejo", use_container_width=True):
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
            st.write(f"Expiry try ki thi: {st.session_state.get(f'expiry_{sel_stock}','')} | Scrip try kiya tha: {st.session_state.get(f'scrip_{sel_stock}','')}")
            st.write("Sabse common wajah: Token 24 ghante me expire ho gaya hai. indstocks.com pe jaake naya Token banao, Logout karke dobara Login karo.")
        else:
            st.info(f"{sel_stock} ka Option Chain Mango dabao.")
else:
    st.info("SCAN NOW dabao - Poora Market Scan hoga, Full Day Movement ke saath.")
    st.write("V15 me kya check hota hai - Sirf Open-High NAHI:")
    st.write("1. Aaj ka 5minute - 09:15 se ab tak - Day Range, VWAP, ORB, Session")
    st.write("2. Pichhle 30 din ka 1day - ATR, Trend, Gap")
    st.write("3. Volatility - Wick, VWAP Cross, Reversal - Choppy hai ya nahi")
    st.write("4. Sideways / Bhag Raha / Volatile / Fake - Final faisla")
    st.write("5. Uske baad hi Option Chain - IND se - Rs 5000 wala Strike")

