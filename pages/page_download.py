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
from findstock.data import check_master_freshness
from findstock.ind_api import download_monthly_master_all

# ---- Download Data page - Freshness pehle, download sirf jab zaroorat ho - V48 split ----

def render():
    st.markdown("## Download Data")
    st.caption("Master - Mahine me 1 baar - FNO + Equity + Index + Scrip Codes + Universe")
    try:
        _fresh, _detail, _per = check_master_freshness()
    except Exception as _e_f:
        _fresh, _detail, _per = False, f"Check nahi hua - {_e_f}", []
    for _fn, _stt, _dt in _per:
        st.write(f"{_fn} - {_stt} {_dt}")
    if _fresh:
        st.success(f"✅ Data is already updated - {_detail}")
        st.write("Dobara download karne ki zaroorat nahi hai. Phir bhi chahiye to neeche dabao.")
        _force = True
    else:
        st.warning(_detail)
        _force = False
    if (not _fresh) or st.button("Phir bhi dobara Download karo", use_container_width=True, key="dl_force"):
        _tok_dl = st.session_state.get("indmoney_secret", "")
        if not _tok_dl or len(str(_tok_dl)) < 10:
            st.session_state["_master_dl_msg"] = "Pehle Login karo"
        else:
            with st.spinner("Monthly Master Download ho raha hai... FNO + Equity + Index - GitHub me apne aap save ho raha hai..."):
                _res_dl, _msg_dl = download_monthly_master_all(_tok_dl)
                _lines_dl = []
                for _fn2, _b2, _df2, _ok2, _m2 in _res_dl:
                    _lines_dl.append(f"{_fn2}: {_m2}")
                st.session_state["_master_dl_msg"] = " | ".join(_lines_dl)
                st.session_state["master_dl_last_date"] = ist_now().strftime("%Y-%m-%d %H:%M")
            st.rerun()
    if st.session_state.get("_master_dl_msg"):
        with st.expander("Download ka haal", expanded=False):
            st.write(st.session_state["_master_dl_msg"])
    if st.session_state.get("master_dl_last_date"):
        st.caption(f"Last Master Download: {st.session_state['master_dl_last_date']}")
