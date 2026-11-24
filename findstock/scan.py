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
from findstock.data import get_scan_universe_216, load_history_cache_from_github, load_tf_month, save_tf_month, tf_candles_for_stock, tf_yyyymm, FULL_NAME_ALIASES
from findstock.helpers import KNOWN_SCRIP, MARKET_STOCKS, get_scan_window, get_trading_day, is_market_closed_for_scan, ist_now, safe_float, safe_int, to_ms
from findstock.ind_api import ind_candles_to_df, ind_get_all_scrips, ind_get_historical_batch, ind_get_scrip, ind_historical_5x5_with_retry, ind_quotes_full_docs_pattern

# ---- V48 split: ye module app_v47.py se nikala gaya, code same hai ----
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
    rows.append({"Criteria": "1. Gap - Khula kitna upar/neeche", "Value": f"{safe_float(ana.get('Gap %',0)):+.2f}% (Chahiye >0.30%)", "Pass?": "✅ PASS" if gap_pass else "❌ FAIL", "Ank": gap_pts, "Max": 15})
    # 2 VWAP
    ltp = safe_float(ana.get("LTP", 0)); vwap = safe_float(ana.get("VWAP", 0)); gap = safe_float(ana.get("Gap %", 0))
    vwap_pass = (ltp > vwap and gap > 0) or (ltp < vwap and gap < 0)
    vwap_pts = 15 if vwap_pass else 0
    total += vwap_pts
    rows.append({"Criteria": "2. VWAP - LTP VWAP ke sahi taraf hai?", "Value": f"LTP {ltp:.2f} vs VWAP {vwap:.2f}", "Pass?": "✅ PASS" if vwap_pass else "❌ FAIL", "Ank": vwap_pts, "Max": 15})
    # 3 ORB
    orb_pass = bool(ana.get("ORB Break", False))
    orb_pts = 20 if orb_pass else 0
    total += orb_pts
    rows.append({"Criteria": "3. ORB 09:15-09:30 Break", "Value": f"ORB High {safe_float(ana.get('ORB High',0)):.2f} / Low {safe_float(ana.get('ORB Low',0)):.2f} - Break: {orb_pass}", "Pass?": "✅ PASS" if orb_pass else "❌ FAIL", "Ank": orb_pts, "Max": 20})
    # 4 Volume
    volx = safe_float(ana.get("Vol x", 0))
    vol_pass = volx > 1.5
    vol_pts = 15 if vol_pass else 0
    total += vol_pts
    rows.append({"Criteria": "4. Volume - Aaj zyada Volume hai?", "Value": f"{volx:.2f}x (Chahiye >1.5x)", "Pass?": "✅ PASS" if vol_pass else "❌ FAIL", "Ank": vol_pts, "Max": 15})
    # 5 Movement Started
    mv_started = str(ana.get("Movement Started?", "")) == "HAAN"
    mv_pts = 15 if mv_started else 0
    total += mv_pts
    rows.append({"Criteria": "5. Movement Started? - Abhi bhag raha hai ya so raha hai", "Value": str(ana.get("Movement Started?", "")), "Pass?": "✅ PASS" if mv_started else "❌ FAIL", "Ank": mv_pts, "Max": 15})
    # 6 Trending
    trend_score = safe_float(ana.get("Trending Score", 0))
    trend_pass = trend_score >= 60
    trend_pts = 10 if trend_pass else 0
    total += trend_pts
    rows.append({"Criteria": "6. Trending Score >=60", "Value": f"{trend_score:.0f}", "Pass?": "✅ PASS" if trend_pass else "❌ FAIL", "Ank": trend_pts, "Max": 10})
    # 7 Volatility OK
    mov_type = str(ana.get("Movement Type", ""))
    vol_ok = ("CHOPPY" not in mov_type and "VOLATILE" not in mov_type)
    vol_ok_pts = 10 if vol_ok else 0
    total += vol_ok_pts
    rows.append({"Criteria": "7. Volatility OK - Choppy / Volatile to nahi", "Value": mov_type, "Pass?": "✅ PASS" if vol_ok else "❌ FAIL", "Ank": vol_ok_pts, "Max": 10})
    # Katoti
    fake = bool(ana.get("Fake Breakout", False))
    fake_pts = -30 if fake else 0
    total += fake_pts
    rows.append({"Criteria": "KATOTI: Fake Breakout - Trap hai?", "Value": "HAAN - TRAP" if fake else "NAHI", "Pass?": "❌ KATA" if fake else "✅ SAHI", "Ank": fake_pts, "Max": 0})
    choppy = "CHOPPY" in mov_type
    choppy_pts = -20 if choppy else 0
    total += choppy_pts
    rows.append({"Criteria": "KATOTI: Choppy", "Value": mov_type, "Pass?": "❌ KATA" if choppy else "✅ SAHI", "Ank": choppy_pts, "Max": 0})
    side = "SIDEWAYS" in mov_type
    side_pts = -15 if side else 0
    total += side_pts
    rows.append({"Criteria": "KATOTI: Sideways", "Value": mov_type, "Pass?": "❌ KATA" if side else "✅ SAHI", "Ank": side_pts, "Max": 0})
    # V40 - Gemini sahi tha: Fake -30 + Choppy -20 + Sideways -15 = -65 ho jata tha, mazboot stock bhi 5-10 pe aa jata tha
    # Katoti kabhi -30 se zyada nahi hogi - taaki ek hi wajah se stock poora khatam na ho
    _kat_total = fake_pts + choppy_pts + side_pts
    if _kat_total < -30:
        _adj = -30 - _kat_total
        total += _adj
        rows.append({"Criteria": "KATOTI CAP: Katoti -30 se zyada nahi", "Value": f"Katoti {_kat_total} thi, cap karke -30 ki", "Pass?": "✅ CAP", "Ank": _adj, "Max": 0})
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
    "TCS": "TCS", "TECHM": "TECHM", "TCHM": "TECHM", "TECH MAHINDRA": "TECHM", "STATE BANK OF INDIA": "SBIN", "STATE BANK": "SBIN",
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
                    "Wick": 0.0, "Reversal": 0, "Pattern": "", "Movement Detail": f"Saved din {_last_day} - Gap {_gap:+.2f}% - Vol {_volx:.1f}x - {_mtype}",
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
            # V43 FIX - _earliest_last kabhi naive ho to IST laga do, nahi to _delta_start < end_dt pe wahi Fill Error
            try:
                if _earliest_last is not None and getattr(_earliest_last, "tzinfo", None) is None:
                    _earliest_last = _earliest_last.replace(tzinfo=IST)
            except:
                pass
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
            rows.append({"Index": _code_to_name.get(_c, _c), "LTP": safe_float(_d.get("live_price", 0)), "Change %": safe_float(_d.get("day_change_percentage", 0)), "Volume": safe_float(_d.get("volume", 0))})
        return pd.DataFrame(rows)
    except Exception as e:
        return pd.DataFrame()