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

from findstock.helpers import *
from findstock.helpers import APP_DIR, KNOWN_SCRIP, MARKET_STOCKS, MASTER_FOLDER, _push_master_to_github, ist_now, read_local_csv
from findstock.scan import FULL_NAME_ALIASES

# ---- V48 split: ye module app_v47.py se nikala gaya, code same hai ----
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
        # V43 FIX - Fill Error wali jad: CSV se Time bina timezone (naive) aata hai, baad me end_dt (IST, aware) se compare hota hai -> "can't compare offset-naive and offset-aware" -> poora Fill gir jata tha, Scan 0 aata tha. Isliye yahin pe IST laga do.
        try:
            if _sub["Time"].dt.tz is None:
                _sub["Time"] = _sub["Time"].dt.tz_localize(IST)
        except:
            pass
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

# ---------------- V48 - MASTER FRESHNESS - "Data is already updated" ----------------
# Master mahine me 1 baar download hota hai. Isliye fresh = sab 5 Master files maujood + is mahine ki.
# Agar sab fresh hain to Download Data dobara download nahi karega, sirf "Data is already updated" bolega.
MASTER_FILES = ["IND_Master_FNO.csv", "IND_Master_Equity.csv", "IND_master_index.csv", "IND_Scrip_Codes.csv", "IND_Universe_216.csv"]
def check_master_freshness():
    try:
        today = ist_now().date()
        per = []
        all_fresh = True
        for _fn in MASTER_FILES:
            _p = APP_DIR / MASTER_FOLDER / _fn
            if not _p.is_file():
                _p2 = APP_DIR / _fn
                _p = _p2 if _p2.is_file() else _p
            if not _p.is_file():
                per.append((_fn, "Nahi hai", ""))
                all_fresh = False
                continue
            try:
                _sz = _p.stat().st_size
                _mt = datetime.fromtimestamp(_p.stat().st_mtime, IST).date()
            except:
                _sz, _mt = 0, None
            if _sz <= 0:
                per.append((_fn, "Khali hai", ""))
                all_fresh = False
            elif _mt is not None and (_mt.year, _mt.month) == (today.year, today.month):
                per.append((_fn, "Updated", _mt.strftime("%d %b")))
            else:
                per.append((_fn, "Purana", _mt.strftime("%d %b") if _mt else ""))
                all_fresh = False
        if all_fresh:
            _detail = "Data is already updated - sab Master files is mahine ki hain"
        else:
            _miss = [fn for fn, s, _ in per if s != "Updated"]
            _detail = f"{len(_miss)} file purani / nahi hai: {', '.join(_miss)}"
        return all_fresh, _detail, per
    except Exception as e:
        return False, f"Check nahi hua - {e}", []
