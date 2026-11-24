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
from findstock.data import TF_API, TF_API_TRY, TF_DELTA, TF_LIST, TF_LOOKBACK_DAYS, build_universe_from_masters, check_saved_history, resolve_to_symbol, save_tf_month, tf_rows_from_candles_df
from findstock.helpers import IND_BASE, KNOWN_SCRIP, MARKET_STOCKS, _push_master_to_github, from_ts_seconds, get_scan_window, get_trading_day, ist_now, read_local_csv, safe_float, safe_int, to_ms

# ---- V51 - Option Chain alag file me: findstock/option_chain.py ----
# Chain ka saara logic (expiry + parser + fetcher + 429 lock) wahan chala gaya.
# Yahan sirf re-export hai, taaki `from findstock.ind_api import ind_get_option_chain` wala purana code (page_scan.py) na toote.
from findstock.option_chain import (
    _get_429_until,
    _parse_option_chain_data,
    _set_429_until,
    get_expiry_from_master_file,
    get_nearest_thursday_fallback,
    get_next_monthly_expiries,
    ind_get_expiries,
    ind_get_option_chain,
    nse_get_option_chain,
)


# ---- V48 split: ye module app_v47.py se nikala gaya, code same hai ----
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
        return [], "Pehle Login karo - bina Login ke Master Download nahi hoga"
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
        return {}, "Login nahi hua - dobara Login karo"
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
                            time.sleep(0.35)
                        except Exception as e:
                            result[sname] = {"candles": [], "mode": "SINGLE-1", "ok": False, "msg": f"1-1 Error - {e}"}
                            logs.append(f"  -> {sname}: 1-1 ❌ Error - {e}")
                # Batch ke baad thoda ruk jao - 5/sec limit na toote
                time.sleep(0.35)
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
                time.sleep(0.35)
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




# ---------------- HISTORICAL DATA - INDstocks - TUMHARE PHOTO WALA PAGE ----------------
def ind_get_historical_batch(scrip_codes, interval, start_ms, end_ms, token):
    # Docs: GET /market/historical/{interval}?scrip-codes=NSE_3045,NFO_51011&start_time=...&end_time=...
    # scrip-codes MAX 5 hai - 5 se zyada bhejoge to 400 aayega. Isliye caller ko 5-5 karke bhejna hai.
    # start_time / end_time MILLISECONDS me, candle ka ts SECONDS me aayega.
    # Response: {"success": true, "data": {"NSE_3045": {"candles": [{"ts":..., "o":..., "h":..., "l":..., "c":..., "v":...}]}}}
    # Jo code ka data nahi hai, wo "data" me aayega hi nahi - isliye keys check karo.
    if not token or not scrip_codes:
        return {}, "Login ya Scrip khali"
    if len(scrip_codes) > 5:
        return {}, "Ek baar me max 5 scrip-codes - batching galat hui"
    try:
        params = {"scrip-codes": ",".join(scrip_codes), "start_time": int(start_ms), "end_time": int(end_ms)}
        r = requests.get(f"{IND_BASE}/market/historical/{interval}", headers=ind_headers(token), params=params, timeout=15)
        # V41 - 429 aaya to turant haar mat maano - 2 sec ruk ke ek baar dobara try karo, phir bhi 429 hai to hi fail bolo
        if r.status_code == 429:
            try:
                time.sleep(2)
                r = requests.get(f"{IND_BASE}/market/historical/{interval}", headers=ind_headers(token), params=params, timeout=15)
            except:
                pass
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
    if (
        trading_day == now.date()
        and (
            now.hour < 15
            or (now.hour == 15 and now.minute <= 30)
        )
    ):
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