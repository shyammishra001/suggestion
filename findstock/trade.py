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
from findstock.helpers import LOT_SIZES, safe_float, safe_int
from findstock.notify import check_all_strikes

# ---- V48 split: ye module app_v47.py se nikala gaya, code same hai ----
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
                    "reason": f"BEST EFFORT - Sab rule pass nahi hua ({_why_q}) - Score {_score}% - Chain bhi nahi aaya", "expiry": expiry or "",
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
            return {"status": "NO_CHAIN", "stock": stock, "ltp": ltp, "prob": prob, "direction": direction, "movement_type": mtype, "reason": "Rule to pass ho gaya, par IND se Option Chain nahi aaya - dobara try karo", "expiry": expiry or "", "pattern": str(row.get("Pattern", "")), "movement_detail": str(row.get("Movement Detail", "")), "session": str(row.get("Session Story", ""))}
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