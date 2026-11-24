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
from findstock.helpers import safe_float, safe_int

# ---- V48 split: ye module app_v47.py se nikala gaya, code same hai ----
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