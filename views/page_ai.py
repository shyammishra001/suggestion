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
from findstock.ai import ask_stock_ai
from findstock.data import resolve_to_symbol

# ---- AI Chat page - V48 split ----

def render():
    # ---------------- V38 - AI CHAT - ChatGPT jaisa, par sirf stock ke liye ----------------
    # Har stock ka kyu bhaga / kyu gira - apne data se batayega, banayi hui wajah nahi bolega
    with st.expander("AI se Puchho - Koi bhi stock kyu bhaga / kyu gira", expanded=False):
        try:
            _q_in = st.text_input("Sawaal", placeholder="RELIANCE kyu bhaga? ya Market kyu gira?", key="ai_chat_input")
            if st.button("Puchho", use_container_width=True, key="ai_chat_ask"):
                if _q_in:
                    with st.spinner("AI soch raha hai..."):
                        _ans = ask_stock_ai(_q_in)
                    st.write(_ans)
                    st.session_state["ai_chat_last"] = _ans
                else:
                    st.write("Sawaal likho - jaise 'RELIANCE kyu bhaga?'")
            elif st.session_state.get("ai_chat_last"):
                st.write(st.session_state.get("ai_chat_last"))
        except Exception as _e_chat:
            st.write(f"AI Chat me error - {_e_chat}")

    # Manual News wala stock - jaise BHEL me 2.5 lakh crore ka deal hua to BHEL bhag sakta hai, wo Yahoo Top 5 me nahi bhi ho to bhi hum usko Step 2 me lenge
    st.markdown("### News")
    manual_input = st.text_input("News Stock", placeholder="BHEL, SUZLON", key="manual_news_input")
    manual_list = []
    if manual_input:
        for _x in manual_input.split(","):
            _x = _x.strip()
            if not _x:
                continue
            _m_sym, _m_sugg = resolve_to_symbol(_x)
            if _m_sym:
                manual_list.append(_m_sym)
            elif _m_sugg:
                st.info(f"{_x} se kai mile - {_m_sugg[:5]} - Ek saaf naam likho")
            elif _x:
                st.warning(f"{_x} se koi stock nahi mila - Symbol ya poora naam likho, jaise BHEL ya ADANI ENERGY SOLUTION LTD")
    if manual_list:
        st.success(f"Add hoga: {', '.join(manual_list)}")
    st.session_state["manual_list"] = manual_list  # V49 - Scan page ke liye save - split me local variable dusre page tak nahi jata tha


