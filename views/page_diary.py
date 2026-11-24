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
from findstock.diary import get_all_trades, update_trade_exit, update_trade_status

# ---- Diary page - V48 split ----

def render():
    st.session_state.show_diary = True  # Diary page pe aaye to Diary khuli hi samjho
    # ---------------- DIARY ----------------
    if st.session_state.show_diary:
        st.markdown("## Diary")
        # V21 - Diary ke andar bhi wahi Download Data Button - Kona me chhota sa, Diary ke paas hi
        # Mahine me 1 baar dabao - Master GitHub me apne aap save ho jayega, Expiry wahi se milegi
        # V35 - FIX: Download ki lambi linein Diary ke upar mat dikhao - Photo me yahi dikkat thi, trade neeche dab gaye the
        if st.session_state.get("_master_dl_msg"):
            with st.expander("Download ka haal", expanded=False):
                st.write(st.session_state["_master_dl_msg"])
        if st.session_state.get("master_dl_last_date"):
            st.caption(f"Last Master Download: {st.session_state['master_dl_last_date']}")
        if st.session_state.get("_diary_last_msg"):
            st.success(st.session_state["_diary_last_msg"])
        # GitHub Secrets ka status - yahi secret jagah hai
        if GITHUB_TOKEN and GITHUB_REPO:
            st.success("GitHub Connected")
        else:
            st.warning("GitHub nahi hai")
            with st.expander("Secrets"):
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
                        # V35 - Exit Edit: Target/SL pe nahi nikle, kisi aur price pe nikle to yahan se dalo - stock change hua to bhi yahin se
                        _exit_val = st.number_input(f"Exit Price - #{row['id']}", value=float(row['entry']) if pd.notna(row['entry']) else 0.0, key=f"ex{row['id']}")
                        if st.button(f"Exit Save Karo - #{row['id']}", key=f"exb{row['id']}"):
                            update_trade_exit(row['id'], _exit_val, "EXITED"); st.rerun()
                    else:
                        # Band trade ka exit price galat dala ho to yahan se badlo - status wahi rahega, PnL naya ban jayega
                        _exit_old = float(row['exit_price']) if pd.notna(row['exit_price']) and str(row['exit_price']) not in ("", "nan") else float(row['entry'])
                        _exit_new = st.number_input(f"Exit Badlo - #{row['id']}", value=_exit_old, key=f"exc{row['id']}")
                        if st.button(f"Exit Badlo Save - #{row['id']}", key=f"excb{row['id']}"):
                            update_trade_exit(row['id'], _exit_new, str(row['status'])); st.rerun()
            st.download_button("CSV Download Karo", data=trades_df_all.to_csv(index=False), file_name="all_trades.csv", mime="text/csv")
        st.divider()
