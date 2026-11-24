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
from findstock.helpers import CSV_FILE, DB_FILE, GITHUB_CSV_PATH

# ---- V48 split: ye module app_v47.py se nikala gaya, code same hai ----
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
            return False, "GitHub Secrets me nahi hai, isliye sirf Local me save hua"
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