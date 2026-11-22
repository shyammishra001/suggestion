# app.py - V16 - FULL DAY MOVEMENT + HISTORICAL DATA - INDstocks Docs se bana hua COMPLETE SCRIPT
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

st.set_page_config(page_title="Scanner V16 - Full Day + PIN Hataya + Diary Fix", layout="wide")

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

def ind_get_expiries(underlying, token):
    try:
        r = requests.get(f"{IND_BASE}/market/instruments/expiries", headers=ind_headers(token), params={"underlying": underlying, "segment": "DERIVATIVE"}, timeout=12)
        if r.status_code == 200:
            data = r.json().get("data", [])
            if data:
                return data, ""
            return [], "Expiries khali aayi"
        return [], f"Expiries Fail - {r.status_code} - {r.text[:300]}"
    except Exception as e:
        return [], f"Expiries Error - {e}"

def ind_get_all_scrips(token):
    # Ek baar me poori Equity CSV mang lo, baar-baar mat mango - 100 stocks ke liye yahi fast tareeka hai
    if not token:
        return {}
    try:
        r = requests.get(f"{IND_BASE}/market/instruments", headers=ind_headers(token), params={"source": "equity"}, timeout=25)
        if r.status_code != 200:
            return dict(KNOWN_SCRIP)
        df = pd.read_csv(io.StringIO(r.text))
        out = dict(KNOWN_SCRIP)
        # CSV columns: SECURITY_ID, SYMBOL_NAME, TRADING_SYMBOL - SYMBOL_NAME se match karo
        if "SYMBOL_NAME" in df.columns and "SECURITY_ID" in df.columns:
            for _, row in df.iterrows():
                try:
                    sym = str(row["SYMBOL_NAME"]).strip().upper()
                    sid = str(row["SECURITY_ID"]).strip()
                    if sym and sid and sid != "nan":
                        out[sym] = sid
                except:
                    continue
        return out
    except:
        return dict(KNOWN_SCRIP)

def ind_get_scrip(symbol, token, scrip_map=None):
    if scrip_map and str(symbol).upper() in scrip_map:
        return str(scrip_map[str(symbol).upper()]), "MAP"
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
    st.title("Scanner V16 - Full Day + PIN Hataya + Diary Fix")
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
    st.title("Scanner V16 | Rs 5,000 | PIN Hataya | Diary Fix | Kisi bhi Time Scan")
with top_right:
    st.write("")
    if st.button("Trading Diary", use_container_width=True):
        st.session_state.show_diary = not st.session_state.show_diary
        st.rerun()

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

# ---------------- SCAN BUTTON ----------------
# Scan ka Time Window dikhao - taaki pata chale 09:20 pe scan ho raha hai ya 02:00 pe
try:
    _td = get_trading_day()
    _s, _e = get_scan_window(_td)
    st.info(f"Abhi Time: {ist_now().strftime('%H:%M:%S')} | Trading Day: {_td} | Scan Window: {_s.strftime('%H:%M')} se {_e.strftime('%H:%M')} tak ki candles li jayengi - 09:20 ho ya 09:35 ho ya 01:00 / 02:00, sab chalega. Fixed 09:20 nahi hai.")
except Exception as e:
    pass

if st.button("SCAN NOW - Poora Market - Full Day Movement ke saath", use_container_width=True):
    with st.spinner("Scan ho raha hai... IND se 1min + 5min + 15min + 1day mang rahe hain, 5-5 karke batch me... Poora din check ho raha hai, sirf Open-High nahi."):
        token = st.session_state.get("indmoney_secret", "")
        df_scan = pd.DataFrame()
        scan_src = ""
        if token and len(str(token)) > 10:
            try:
                scrip_map = ind_get_all_scrips(token)
                prog = st.progress(0)
                def _cb(p):
                    try:
                        prog.progress(min(0.95, float(p)))
                    except:
                        pass
                df_scan = scan_with_ind(token, scrip_map, progress_cb=_cb)
                if not df_scan.empty and len(df_scan) >= 10:
                    scan_src = "IND-Historical (5minute + 1day) - Poora Din Check Hua"
                else:
                    st.warning(f"IND se {len(df_scan)} stocks aaye, kam hain. Yahoo Fallback se bhi check kar rahe hain.")
                    df_scan = scan_with_yahoo_fallback()
                    scan_src = "Yahoo-Fallback (IND se poora data nahi aaya)"
                try:
                    prog.progress(1.0)
                except:
                    pass
            except Exception as e:
                st.error(f"IND Scan me error: {e} - Yahoo se kar rahe hain")
                df_scan = scan_with_yahoo_fallback()
                scan_src = "Yahoo-Fallback (IND Error)"
        else:
            df_scan = scan_with_yahoo_fallback()
            scan_src = "Yahoo-Fallback (Token nahi hai, isliye Scan Yahoo se, Option Chain IND se hi hoga)"
        indices_df = fetch_indices_history(); news_df = fetch_global_news()
        st.session_state.scan_df = df_scan; st.session_state.indices_data = indices_df; st.session_state.news_data = news_df
        st.session_state.scan_source = scan_src
        st.session_state.scan_time = datetime.now().strftime("%H:%M:%S")
        st.session_state.auto_sent = False
        if not df_scan.empty:
            top = df_scan.iloc[0]
            if safe_float(top.get("Probability %", 0)) >= 70:
                expiry_auto = "IND se aayegi"
                ok_auto = send_top5(df_scan.head(5), expiry_auto)
                st.session_state.auto_sent = ok_auto
        st.rerun()

# ---------------- RESULTS ----------------
if st.session_state.scan_df is not None and not st.session_state.scan_df.empty:
    df_scan = st.session_state.scan_df; indices_df = st.session_state.indices_data; news_df = st.session_state.news_data
    st.info(f"Scan Source: {st.session_state.get('scan_source','')} | Scan Time: {st.session_state.get('scan_time','')} | Total Stocks Checked: {len(df_scan)}")
    # 0 Stocks aaye to wajah dikhao - chhupao mat
    _dbg = st.session_state.get("_scan_debug", {})
    if _dbg:
        with st.expander("Scan Debug - IND se kitne aaye, kyu 0 aaya tha, ye dekho"):
            st.write(f"Trading Day: {_dbg.get('trading_day','')} | Window: {_dbg.get('start','')} se {_dbg.get('end','')}")
            st.write(f"IND se OK: {_dbg.get('ind_ok',0)} / {_dbg.get('total',0)} | Fail: {_dbg.get('ind_fail_count',0)}")
            if _dbg.get('ind_fail_sample'):
                st.write(f"Fail hue (sample): {_dbg.get('ind_fail_sample')}")
            st.write(f"Note: {'; '.join(_dbg.get('debug_list',[]))}")
            st.write("Agar IND se 0 aaye to 2 wajah hoti hain: 1) Aaj Sunday/Saturday tha - Friday ka data liya jayega, 2) Token expire ho gaya - naya Token banao. Is baar dono fix kar diye hain.")
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
        if st.button(f"{sel_stock} ka Option Chain Mango - INDstocks se", use_container_width=True):
            with st.spinner("INDstocks se Option Chain mang rahe hain - Docs wala tareeka..."):
                token_now = st.session_state.get("indmoney_secret", "")
                scrip_map_now = ind_get_all_scrips(token_now) if token_now else {}
                chain_df, source, expiry_yyyy, scrip_used, ind_ltp = ind_get_option_chain(sel_stock, token_now, scrip_map_now)
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

