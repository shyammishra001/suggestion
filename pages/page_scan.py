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
from findstock.ai import build_ai_live_fallback, fetch_global_news, load_ai_live, load_ai_memory
from findstock.data import TF_LIST, get_scan_universe_216, load_tf_month, normalize_universe_to_symbols, resolve_to_symbol, tf_yyyymm
from findstock.diary import save_trade
from findstock.ind_api import ind_get_all_scrips, ind_get_multi_timeframe, ind_get_option_chain, ind_get_scrip, ind_quotes_full_docs_pattern
from findstock.notify import check_all_strikes, send_strike, send_telegram, send_top5
from findstock.scan import analyze_full_day, calc_probability_breakdown, fetch_indices_history, ind_fill_for_selected, ind_scan_all_ind_only, scan_from_saved_history, update_history_cache_after_scan
from findstock.trade import build_best_effort_call, build_trade_call, is_qualifying_row

# ---- Scan page - Topbar + Search + Scan + AI Live + Universe + History + Results - V48 split ----

def render():
    # ---------------- TOP BAR ----------------
    # V40 - System Health ek line me - Token / GitHub / Universe / Data - taaki 9:15 pe ek nazar me pata chale sab theek hai ya nahi. Cards / Dark Mode nahi - minimal hi rahega.
    try:
        _tok_ok = "✅ Login" if st.session_state.get("indmoney_secret", "") else "❌ Login nahi"
        _gh_ok = "✅ GitHub" if GITHUB_TOKEN and GITHUB_REPO else "❌ GitHub nahi"
        _uni_n = len(st.session_state.get("universe_216_df", pd.DataFrame())) if st.session_state.get("universe_216_df", None) is not None else 0
        st.caption(f"{_tok_ok} | {_gh_ok} | Universe: {_uni_n} stocks | Data: {data_freshness_line()}")
    except:
        pass
    top_left, top_right = st.columns([4, 1])
    with top_left:
        st.title("Scan Stock")
        st.caption(f"Find Stock Version {APP_VERSION}")
    with top_right:
        st.write("")
        # V21 - Trading Diary ke paas hi chhota sa Download Data Button - Mahine me 1 baar dabao
        # Jaise hi daboge, Master (FNO + Equity + Index) Download ho ke GitHub me apne aap save ho jayega.
        # Usme Exchange, Segment, Security ID, Expiry - sab likha hoga. Phir roz Expiry search nahi karni padegi.
        # V22 - Download Data sabse upar, sabse bada - Tumko Upload nahi karna, ye Button hi sab karega
        # Stock ka Expiry 1 Mahine me badalta hai, Option ka Expiry 7 Din me badalta hai - isliye 7 Din se zyada purana ho to Warning dikhayenge
        _last_dl_str = st.session_state.get("master_dl_last_date", "")
        _dl_old_msg = ""
        try:
            if _last_dl_str:
                _last_dt = datetime.strptime(_last_dl_str, "%Y-%m-%d %H:%M")
                _days_old = (ist_now() - _last_dt).days
                if _days_old >= 7:
                    _dl_old_msg = f"Data { _days_old } din purana hai."
                elif _days_old >= 1:
                    _dl_old_msg = f"Data { _days_old } din purana hai."
        except:
            pass
        if _dl_old_msg:
            st.warning(_dl_old_msg)

    if st.session_state.indmoney_connected:
        st.success("Connected")
    else:
        st.warning("Not Connected")


    # ---------------- V24 - SINGLE STOCK SEARCH - RELIANCE ya RIL likho, Suggestion dega, Sirf IND se Check karega - NSE_ + SECURITY_ID se ----------------
    # User ka naya Option: Hum jo stock search karein, stock ka naam likhein - jaise RELIANCE ya RIL likhein, to Suggestion de de RELIANCE ka, phir usko search karke bataye ki kitne Criteria pe fit ho raha hai aur 100 me se kitne ank mile.
    # Ye 5 ka example nahi hai - ye koi bhi 1 stock ke liye hai, jab tum chaaho tab check karo, poora Scan kiye bina.
    st.markdown("### Search")
    st.write("")
    # V42 - Sirf ek hi search - neeche wala dropdown. Upar wala Stock text input hata diya - do search se confusion hota tha.
    _single_resolved = None
    _single_opts_216 = []
    try:
        _raw_opts = st.session_state.get("universe_216_df", pd.DataFrame())["STOCK"].astype(str).tolist() if st.session_state.get("universe_216_df", None) is not None and not st.session_state.get("universe_216_df", pd.DataFrame()).empty else list(MARKET_STOCKS.keys())
        _single_opts_216, _ = normalize_universe_to_symbols(_raw_opts, pd.DataFrame({"STOCK": _raw_opts}))
    except Exception:
        _single_opts_216 = list(MARKET_STOCKS.keys())
    try:
        _single_resolved = st.selectbox(f"Chuno - {len(_single_opts_216)} stocks", [""] + _single_opts_216, key="single_stock_dropdown_empty")
    except Exception as _e_sel:
        st.write(f"Search me error - {_e_sel} - neeche wale AI se Puchho se puchh lo")
        _single_resolved = None
    if _single_resolved == "":
        _single_resolved = None
    if _single_resolved:
        # V22 - Single Search bhi Code se hi hoga - naam sirf Suggestion ke liye hai, andar Code se khojenge
        # Pehle Code nikal lo, phir dikhao - taaki pata chale naam se nahi, Code se search ho raha hai
        try:
            _map_single = ind_get_all_scrips(st.session_state.get("indmoney_secret", ""))
            # V39 - FIX: "STATE BANK OF INDIA" chuna ho to pehle SBIN banao, phir Code khojo - full naam se Code kabhi nahi milega
            _single_sym = _single_resolved
            try:
                _rs, _ = resolve_to_symbol(str(_single_resolved))
                if _rs:
                    _single_sym = str(_rs).upper()
            except:
                pass
            _code_single = _map_single.get(_single_sym, _map_single.get(str(_single_sym).upper(), ""))
            if _code_single:
                st.success(f"{_single_resolved} - {_code_single}")
            else:
                st.warning("Code nahi mila - Download Data dabao")
        except Exception as e:
            st.write(f"Code check me error - {e}")
        if st.button(f"{_single_resolved} - Check", use_container_width=True, key="single_check_btn"):
            with st.spinner("Check ho raha hai..."):
                # V24 - SIRF IND SE - Docs wala exact pattern, jo photo me bheja hai:
                #   headers = {'Authorization': access_token}
                #   params = {'scrip-codes': 'NSE_2885,NSE_11536'}
                #   response = requests.get('https://api.indstocks.com/market/quotes/full', headers=headers, params=params)
                #   LTP = quotes['data']['NSE_2885']['live_price'], Change = ['day_change_percentage'], Volume = ['volume']
                # Yahoo / NSE se kuch nahi mangenge - teenon ka Compromise Mix band.
                _tok3 = st.session_state.get("indmoney_secret", "")
                _scrip_map3 = ind_get_all_scrips(_tok3) if _tok3 else dict(KNOWN_SCRIP)
                # V39 - ind_get_scrip khud full naam -> Symbol kar lega, yahan bhi wahi bhej do
                _sid3, _src3 = ind_get_scrip(_single_resolved, _tok3, _scrip_map3)
                _scrip_code3 = f"NSE_{_sid3}" if _sid3 else ""
                _ind_ana = None; _ind_msg = ""; _ind_chain = pd.DataFrame(); _ind_chain_msg = ""; _ind_quote = None; _ind_quote_msg = ""
                if _sid3:
                    # STEP 1 - LTP sirf IND se - Docs wala quotes/full
                    try:
                        _qdata, _qmsg = ind_quotes_full_docs_pattern([_scrip_code3], _tok3)
                        _ind_quote_msg = _qmsg
                        if _scrip_code3 in _qdata:
                            _d = _qdata[_scrip_code3]
                            _ind_quote = {"symbol": _single_resolved, "scrip_code": _scrip_code3, "security_id": _sid3,
                                          "ltp": safe_float(_d.get("live_price", 0)), "change_pct": safe_float(_d.get("day_change_percentage", 0)),
                                          "volume": safe_float(_d.get("volume", 0)), "open": safe_float(_d.get("day_open", 0)),
                                          "high": safe_float(_d.get("day_high", 0)), "low": safe_float(_d.get("day_low", 0)),
                                          "prev_close": safe_float(_d.get("previous_close", 0)), "raw": _d}
                            _ind_msg = f"IND se aaya - {_scrip_code3} - LTP ₹{safe_float(_d.get('live_price',0))} - Change {safe_float(_d.get('day_change_percentage',0))}% - Docs wala pattern"
                        else:
                            _ind_msg = f"IND quotes/full me {_scrip_code3} nahi aaya - {_qmsg}"
                    except Exception as e:
                        _ind_quote_msg = f"IND Quote Error - {e}"
                        _ind_msg = _ind_quote_msg
                    # STEP 2 - Candle sirf IND se - Historical 5minute, NSE_ + Code se
                    try:
                        _td3 = get_trading_day()
                        _multi3 = ind_get_multi_timeframe(_single_resolved, _sid3, _tok3, _td3)
                        _df5_ind = _multi3.get("df_5min", None)
                        _dfd_ind = _multi3.get("df_daily", pd.DataFrame())
                        if _df5_ind is not None and len(_df5_ind) > 0:
                            _ind_ana = analyze_full_day(_df5_ind, _dfd_ind if _dfd_ind is not None else pd.DataFrame())
                            _ind_msg += f" | Candle IND se - {len(_df5_ind)} candles"
                        else:
                            _ind_msg += f" | IND Historical khali - Code {_sid3} - {_multi3.get('debug',[])}"
                    except Exception as e:
                        _ind_msg += f" | IND Candle Error - {e}"
                    # STEP 3 - Option Chain sirf IND se - underlying-scrip = SECURITY_ID (bina prefix), exchange=NSE, segment=EQUITY
                    try:
                        _ind_chain, _ind_chain_msg, _exp3, _scrip3, _ltp3 = ind_get_option_chain(_single_resolved, _tok3, _scrip_map3)
                        _ind_msg += f" | Option Chain IND se: {_ind_chain_msg}"
                    except Exception as e:
                        _ind_chain_msg = f"IND Option Chain Error - {e}"
                        _ind_msg += f" | Option: {_ind_chain_msg}"
                else:
                    _ind_msg = f"IND Scrip nahi mila - {_src3} - GitHub CSV me iska Sahi Naam check karo - Pehle Download Data dabao"
                # V46 - DeepSeek wali SAHI baat: Candle (Historical) fail hui to bhi Gap% quote se bhar do.
                # Quote me day_open + previous_close hota hai, isliye gap_pct = (open-prev_close)/prev_close*100 nikal sakta hai.
                # VWAP quote se NAHI aa sakta (uske liye candle chahiye - app pehle se candle se nikalta hai, Typical Price wala).
                # Volume pehle se quote se aa raha tha (Photo 3 me 5687870 dikha tha) - usme koi kami nahi thi.
                try:
                    _q_open3 = safe_float((_ind_quote or {}).get("open", 0))
                    _q_prev3 = safe_float((_ind_quote or {}).get("prev_close", 0))
                    _gap_quote3 = round((_q_open3 - _q_prev3) / _q_prev3 * 100, 2) if _q_prev3 else 0.0
                except:
                    _gap_quote3 = 0.0
                try:
                    _ana3_now = _ind_ana if "_ind_ana" in locals() else None
                    if (not _ana3_now or "error" in (_ana3_now or {})) and _gap_quote3 != 0:
                        _ind_msg += f" | Gap% quote se bhar diya - {_gap_quote3}% (Candle nahi aayi, isliye VWAP / Vol x 0 hain)"
                except:
                    pass
                st.session_state["single_result"] = {"stock": _single_resolved, "ind_ana": _ind_ana, "ind_msg": _ind_msg, "ind_chain": _ind_chain, "ind_chain_msg": _ind_chain_msg, "ind_quote": _ind_quote, "ind_quote_msg": _ind_quote_msg, "best_ana": _ind_ana, "scrip_code": _scrip_code3, "security_id": _sid3, "expiry": locals().get("_exp3", ""), "gap_quote": _gap_quote3}
                # V26 - Single Check ka bhi Candle Cache me jama kar do - taaki SCAN me is stock ka Delta hi mangna pade
                try:
                    if _ind_ana is not None and "error" not in _ind_ana:
                        # _multi3 se df5 lo - wahan se Today Cache update hoga
                        _df5_for_cache = _multi3.get("df_5min", None) if "_multi3" in locals() else None
                        if _df5_for_cache is not None and not _df5_for_cache.empty:
                            update_history_cache_after_scan({_single_resolved: _df5_for_cache}, _td3)
                except:
                    pass
            st.rerun()
    # Single ka Result dikhao
    if st.session_state.get("single_result"):
        _sr = st.session_state["single_result"]
        _stk = _sr.get("stock", "")
        st.markdown(f"### {_stk}")
        st.write(f"{_sr.get('scrip_code','')} | {_sr.get('security_id','')}")
        # SIRF IND KA TABLE - Teenon ka nahi, ek hi sahi wala - Docs wala quotes/full se LTP + Candle se baaki
        _iA = _sr.get("ind_ana") or {}; _iQ = _sr.get("ind_quote") or {}
        _ind_rows = [
            {"Cheez": "LTP", "Value": safe_float(_iQ.get("ltp",0)) if _iQ else safe_float(_iA.get("LTP",0)) if _iA else 0},
            {"Cheez": "Change %", "Value": safe_float(_iQ.get("change_pct",0)) if _iQ else safe_float(_iA.get("Gap %",0)) if _iA else 0},
            {"Cheez": "Gap %", "Value": safe_float(_iA.get("Gap %",0)) if _iA and safe_float(_iA.get("Gap %",0)) != 0 else safe_float(_sr.get("gap_quote",0))},
            {"Cheez": "VWAP", "Value": safe_float(_iA.get("VWAP",0)) if _iA else 0},
            {"Cheez": "Day High", "Value": safe_float(_iQ.get("high",0)) if _iQ else safe_float(_iA.get("Day High",0)) if _iA else 0},
            {"Cheez": "Day Low", "Value": safe_float(_iQ.get("low",0)) if _iQ else safe_float(_iA.get("Day Low",0)) if _iA else 0},
            {"Cheez": "Volume", "Value": safe_float(_iQ.get("volume",0)) if _iQ else 0},
            {"Cheez": "Volume x", "Value": safe_float(_iA.get("Vol x",0)) if _iA else 0},
        ]
        st.dataframe(pd.DataFrame(_ind_rows), use_container_width=True, hide_index=True)
        _best = _sr.get("best_ana")
        if _best is not None and "error" not in _best:
            _break_df, _total = calc_probability_breakdown(_best)
            st.markdown(f"### {_stk} - {_total}/100")
            st.dataframe(_break_df, use_container_width=True, hide_index=True)
            st.write(f"{_total}/100")
            # Pass count bhi
            _pass_n = int(sum([1 for _, r in _break_df.iterrows() if r["Pass?"] == "✅ PASS" and r["Max"] > 0 and r["Criteria"].startswith(("1.","2.","3.","4."))]))
            st.write(f"{_pass_n}/4 Pass")
            st.write(f"**Movement:** {_best.get('Movement Type','')} - {_best.get('Movement Detail','')} | **Session:** {_best.get('Session Story','')} | **Fake?** {'HAAN - TRAP' if _best.get('Fake Breakout') else 'NAHI'}")
        else:
            st.warning("Data nahi aaya - Candle (Historical) nahi aaya, isliye Gap / VWAP / Volume x 0 hain")
            st.write(f"Wajah: {_sr.get('ind_msg','')}")
        # V23 - Single ka Option Chain - sirf INDmoney se - NSE se nahi mangte
        _ind_ch_s = _sr.get("ind_chain", pd.DataFrame())
        if _ind_ch_s is not None and not _ind_ch_s.empty:
            st.write("Chain:")
            st.dataframe(_ind_ch_s.head(15), use_container_width=True, hide_index=True)
        else:
            st.write(f"Chain nahi aaya - Wajah: {_sr.get('ind_chain_msg','')}")
        # V28 - SINGLE ka bhi FINAL CALL - wahi build_trade_call, taaki Single me bhi Entry/SL/Target mile, sirf chain ke 15 row nahi
        try:
            _s_ana = _sr.get("best_ana") or {}
            if _s_ana and "error" not in _s_ana:
                _s_total = _total if "_total" in locals() else safe_float(_s_ana.get("Probability %", 0))
                # Single ke ana ko scan-row jaisa banao - Gap/ORB/Volume ke ✅/❌ bhi bhar do
                _s_gap_ok = "✅" if abs(safe_float(_s_ana.get("Gap %", 0))) > 0.30 else "❌"
                _s_vwap_ok = "✅" if ((safe_float(_s_ana.get("LTP", 0)) > safe_float(_s_ana.get("VWAP", 0)) and safe_float(_s_ana.get("Gap %", 0)) > 0) or (safe_float(_s_ana.get("LTP", 0)) < safe_float(_s_ana.get("VWAP", 0)) and safe_float(_s_ana.get("Gap %", 0)) < 0)) else "❌"
                _s_row = dict(_s_ana)
                _s_row["Stock"] = _stk
                _s_row["Probability %"] = int(_s_total)
                _s_row["Gap"] = _s_gap_ok
                _s_row["VWAP_OK"] = _s_vwap_ok
                _s_row["ORB"] = "✅" if bool(_s_ana.get("ORB Break", False)) else "❌"
                _s_row["Volume"] = "✅" if safe_float(_s_ana.get("Vol x", 0)) > 1.5 else "❌"
                _s_row["Volatility OK"] = "✅" if ("CHOPPY" not in str(_s_ana.get("Movement Type", "")) and "VOLATILE" not in str(_s_ana.get("Movement Type", ""))) else "❌"
                _s_row["Fake?"] = "HAAN - TRAP" if bool(_s_ana.get("Fake Breakout", False)) else "NAHI"
                # News bias Single ke liye - abhi ka news table neeche hai, isliye yahan NEUTRAL rakhenge, SCAN wala FINAL CALL news se adjust hota hai
                _s_call = build_trade_call(_s_row, _ind_ch_s, _sr.get("expiry", ""), "NEUTRAL")
                st.markdown(f"### {_stk}")
                if _s_call.get("status") == "TRADE":
                    st.success(f"BUY KARO: {_s_call['stock']} {_s_call['strike']} {_s_call['opt_type']} @ Rs {_s_call['entry']} - Expiry: {_s_call['expiry']} - 1 Lot Cost Rs {_s_call['cost']:.0f} (Lot { _s_call['lot']})")
                    st.write(f"BUY: Rs {_s_call['entry']} | SELL: Rs {_s_call['target']} | SL: Rs {_s_call['sl']}")
                    st.write(f"Max Profit: Rs {_s_call['max_profit']:.0f} | Max Loss: Rs {_s_call['max_loss']:.0f} | Prob: {_s_call['prob']:.0f}/100 | Direction: {_s_call['direction']} | LTP Rs {_s_call['ltp']:.1f}")
                    st.write(f"Rule: {_s_call.get('rule_line','')} | Movement: {_s_call['movement_type']} | Adjust: {_s_call.get('adjust_note','')}")
                    st.write("")
                    _s_sugg = {"date": datetime.now().strftime("%Y-%m-%d"), "time": datetime.now().strftime("%H:%M:%S"), "symbol": _s_call['stock'], "strike": _s_call['strike'], "opt_type": _s_call['opt_type'], "entry": float(_s_call['entry']), "sl": float(_s_call['sl']), "target": float(_s_call['target']), "qty_lots": 1, "qty_total": int(_s_call['lot']), "capital_used": float(_s_call['cost']), "risk": float(_s_call['max_loss']), "status": "OPEN", "reason": f"Single Search - Prob {_s_call['prob']:.0f} - {_s_call['movement_type']}", "conditions": _s_call.get('rule_line','')}
                    if st.button("Telegram", use_container_width=True, key="single_call_notify"):
                        _ok_s = send_strike(_s_call['stock'], _s_call['strike'], _s_call['opt_type'], _s_call['entry'], _s_call['sl'], _s_call['target'], _s_call['cost'], _s_call['lot'], _s_call['expiry'], str(_s_call['movement_type']))
                        if _ok_s:
                            st.success("Chala gaya ✅")
                        else:
                            st.error("Nahi gaya ❌")
                    if st.button(f"{_stk} ko Diary me Save Karo", use_container_width=True, key="single_call_diary"):
                        save_trade(_s_sugg); st.success(st.session_state.get("_diary_last_msg","Diary me save ho gaya!")); st.rerun()
                else:
                    st.warning(f"NO TRADE - {_stk} - {_s_call.get('reason','')}")
                    st.write(f"Prob: {_s_call.get('prob',0):.0f}/100 | LTP Rs {_s_call.get('ltp',0):.1f} | Movement: {_s_call.get('movement_type','')} - Zabardasti strike nahi denge, WAIT karo.")
        except Exception as _e_scall:
            st.write(f"Single FINAL CALL me error - {_e_scall}")
    st.divider()

    # ---------------- SCAN BUTTON ----------------
    # Scan ka Time Window dikhao - taaki pata chale 09:20 pe scan ho raha hai ya 02:00 pe
    try:
        _td = get_trading_day()
        _s, _e = get_scan_window(_td)
        st.info(f"{ist_now().strftime('%H:%M')} | {_td}")
    except Exception as e:
        pass

    # ---------------- V37 - AI LIVE - Market + News + Crash + Impact - AI Worker ne likha, yahan sirf dikhega ----------------
    # Website pe source ka naam nahi likhenge - sirf jaankari dikhegi
    with st.expander("AI Live - Market, News, Crash, Impact", expanded=True):
        try:
            _ai = load_ai_live()
            if not _ai:
                # V38 - Worker nahi chala to bhi khali nahi - Saved data + News se hi bana do
                _ai = build_ai_live_fallback()
                st.write("Saved data se - Worker nahi chala to bhi ye jaankari hai.")
            if _ai.get("fallback"):
                st.write("Saved data se - Live nahi hai, Scan karo to Live aa jayega.")
            else:
                _mkt = _ai.get("market", {}) or {}
                _upd = str(_ai.get("updated_at", ""))
                st.write(f"Market: {_mkt.get('direction', '')} - Nifty {safe_float(_mkt.get('nifty', 0)):.0f} ({safe_float(_mkt.get('nifty_change_pct', 0)):+.2f}%) | Bank Nifty {safe_float(_mkt.get('bank_nifty', 0)):.0f} ({safe_float(_mkt.get('bank_nifty_change_pct', 0)):+.2f}%) | Sensex {safe_float(_mkt.get('sensex', 0)):.0f} ({safe_float(_mkt.get('sensex_change_pct', 0)):+.2f}%) | VIX {safe_float(_mkt.get('vix', 0)):.1f} | Upar: {_mkt.get('advance', '')} | Neeche: {_mkt.get('decline', '')}")
                st.write(f"AI kab chala: {_upd}")
                try:
                    _upd_dt = pd.to_datetime(_upd)
                    _age_min = (datetime.now() - _upd_dt.to_pydatetime().replace(tzinfo=None) if hasattr(_upd_dt, "to_pydatetime") else datetime.now()).total_seconds() / 60 if _upd_dt is not None else 9999
                    if _age_min > 30:
                        st.write("AI ruka hua lag raha hai - thodi der baad phir dekho.")
                except:
                    pass
                _crash = _ai.get("crash_alerts", []) or []
                if _crash:
                    st.write("Crash / Tez Giravat:")
                    for _c in _crash:
                        st.write(f"  - {_c}")
                else:
                    st.write("Koi crash nahi hai.")
                _news_ai = _ai.get("news", []) or []
                if _news_ai:
                    _ndf = pd.DataFrame([{"News": str(_n.get("title", ""))[:120], "Type": str(_n.get("type", "")), "Direction": str(_n.get("direction", "")), "Asar": str(_n.get("impact", ""))} for _n in _news_ai])
                    st.dataframe(_ndf, use_container_width=True, hide_index=True)
                else:
                    st.write("Abhi koi badi khabar nahi hai.")
                _mem = load_ai_memory() or {}
                _pats = (_mem.get("patterns", []) or [])[:5]
                if _pats:
                    st.write("Pichhli baar aisa hua to kya hua:")
                    for _pt in _pats:
                        st.write(f"  - {str(_pt.get('text', ''))}")
        except Exception as _e_ai:
            st.write(f"AI Live me error - {_e_ai}")

    # ---------------- V25 - 216 UNIVERSE TABLE - Jaruri Jankari - Ek Nazar Me ----------------
    with st.expander("Universe (216)", expanded=False):
        try:
            _tok_u = st.session_state.get("indmoney_secret", "")
            _ulist_u, _udf_u, _umsg_u = get_scan_universe_216(_tok_u)
            st.write(f"{_umsg_u}")
            if _udf_u is not None and not _udf_u.empty:
                st.dataframe(_udf_u, use_container_width=True, hide_index=True)
                st.write(f"Total: {len(_udf_u)} stocks")
            else:
                st.write("Universe abhi khali hai - Download Data dabao, phir 216 wali list yahan dikhegi. Tab tak 138 wala purana list scan me chalega.")
                # Fallback - 138 wala list bhi dikha do
                _fb = pd.DataFrame([{"STOCK": k, "SECURITY_ID": KNOWN_SCRIP.get(k, ""), "SCRIP_CODE_NSE": f"NSE_{KNOWN_SCRIP.get(k, '')}" if KNOWN_SCRIP.get(k) else "", "LOT_SIZE": LOT_SIZES.get(k, ""), "EXPIRY_LIST": ""} for k in MARKET_STOCKS.keys()])
                st.dataframe(_fb, use_container_width=True, hide_index=True)
        except Exception as e:
            st.write(f"Universe Table me Error - {e}")


    # ---------------- V26 - HISTORY CACHE STATUS - GitHub se pichhla data kitna mila? ----------------
    with st.expander("History", expanded=False):
        try:
            # V34 - Sirf is mahine ki 5 file dikhao - jo file chahiye wahi khulegi, poora folder nahi
            _td_h = get_trading_day()
            _mm_h = tf_yyyymm(_td_h)
            _rows_h = []
            for _tf_h in TF_LIST:
                _df_h = load_tf_month(_tf_h, _mm_h)
                _n_h = len(_df_h) if _df_h is not None else 0
                _nstocks_h = int(_df_h["STOCK"].nunique()) if _df_h is not None and not _df_h.empty and "STOCK" in _df_h.columns else 0
                _rows_h.append({"Timeframe": _tf_h, "Mahina": _mm_h, "Candles": _n_h, "Stocks": _nstocks_h, "File": f"data/history/{_tf_h}/{_mm_h}.csv"})
            st.dataframe(pd.DataFrame(_rows_h), use_container_width=True, hide_index=True)
            st.write("5min = ORB + VWAP | 15min = Trend confirm | 1H = Trend | 4H = Trend | Daily = ATR + Trend | Weekly = Trend")
            if st.session_state.get("last_cache_msg"):
                st.write(f"**Last Scan ke baad Save:** {st.session_state.get('last_cache_msg')}")
        except Exception as e:
            st.write(f"History UI me Error - {e}")

    if st.button("Scan", use_container_width=True):
        # V24 - SIRF IND SE SCAN - Yahoo / NSE band. Docs wala pattern hi sab jagah.
        # Pehle GitHub wali IND_Scrip_Codes.csv se Scrip-Code turant mil jayega (Download Data se jama hua).
        # Phir live data sirf IND se: quotes/full (NSE_2885) + historical/5minute (NSE_2885) + option-chain (underlying-scrip=2885)
        # Jo data badalne wala nahi hai (Scrip-Code + Expiry) wo GitHub se, jo badalne wala hai (LTP/Candle/Chain) wo live IND se.
        with st.spinner("Scan ho raha hai..."):
            # V32 - Dobara Scan dabaya aur market band hai aur isi din ka scan pehle se hai to dobara IND se mat mango - wahi result turant dikhao. Pehle har baar poora scan dobara hota tha, isliye har baar utna hi time lagta tha.
            _td_now = get_trading_day()
            _reuse = False
            _prev_df = st.session_state.get("scan_df", None)
            _prev_day = st.session_state.get("scan_trading_day", "")
            if _prev_df is not None and not _prev_df.empty and str(_prev_day) == str(_td_now) and is_market_closed_for_scan(_td_now):
                df_step1 = _prev_df
                debug1 = st.session_state.get("step1_debug", {})
                _reuse = True
            else:
                df_step1, debug1 = ind_scan_all_ind_only()
                st.session_state.scan_trading_day = str(_td_now)
            # V38 - FIX: Photo me Checked 0/216 tha - IND se 0 aaya, isliye koi stock nahi mila - ab Saved data se bhi stock denge, khali nahi chhodenge
            _fallback_used = False
            _fallback_msg = ""
            try:
                _ok_n = int((debug1 or {}).get("ind_ok", 0))
            except:
                _ok_n = 0
            if (df_step1 is None or df_step1.empty or _ok_n == 0) and not _reuse:
                try:
                    _dfb, _msgb = scan_from_saved_history()
                    if _dfb is not None and not _dfb.empty:
                        df_step1 = _dfb
                        debug1 = dict(debug1 or {})
                        debug1["fallback"] = True
                        debug1["fallback_msg"] = _msgb
                        _fallback_used = True
                        _fallback_msg = _msgb
                except Exception as _e_fb:
                    _fallback_msg = f"Saved fallback me error - {_e_fb}"
            st.session_state["scan_fallback"] = _fallback_used
            st.session_state["scan_fallback_msg"] = _fallback_msg
            st.session_state.scan_df = df_step1
            st.session_state.step1_debug = debug1
            st.session_state.scan_time = datetime.now().strftime("%H:%M:%S")
            # V37 - Diary wale jeet-haar se Score +/- karna BAND - user ne mana kiya, ab AI Worker se seekhna hoga
            selected = []
            if not df_step1.empty:
                _top15 = df_step1.head(15)["Stock"].tolist() if "Stock" in df_step1.columns else []
                _prob50 = df_step1[df_step1["Probability %"] >= 50]["Stock"].tolist() if "Probability %" in df_step1.columns else []
                for _s in _top15 + _prob50:
                    if _s not in selected:
                        selected.append(_s)
                selected = selected[:20]
            for m in manual_list:
                if m not in selected:
                    selected.append(m)
            if not selected and manual_list:
                selected = manual_list[:]
            st.session_state.selected_stocks = selected
            st.session_state.scan_source = f"{debug1.get('ind_ok',0)}/{debug1.get('ind_total',0)}" if not _reuse else "Cache se"
            # Option Chain sirf Selected ke liye, sirf IND se
            token = st.session_state.get("indmoney_secret", "")
            step3_results = {}
            if selected and token and len(str(token)) > 10:
                try:
                    scrip_map = ind_get_all_scrips(token)
                except:
                    scrip_map = dict(KNOWN_SCRIP)
                # Selected ka Candle + Option Chain - ind_fill + option-chain, dono IND se
                step3_results = ind_fill_for_selected(selected, token, scrip_map)
                st.session_state.step3_results = step3_results
                # V30 - FAST SCAN - Option Chain SIRF FINAL CALL wale 1 stock ke liye, 20 stock ke liye nahi.
                # Pehle hum selected (Top 15 + Prob>=50 + Manual = 20 tak) sab ki Chain mangte the - 20 Chain x har Chain pe retries = SCAN 2-3 min slow ho jata tha.
                # Ab sirf 1 Chain mangenge - jo stock FINAL CALL me aayega (Rule se chuna gaya Top 1). Baaki stock ki Chain jab zaroorat hogi tab Section 6 / FINAL CALL ke button se 1-1 karke mang lenge.
                # Isse SCAN ka Chain wala time 20x se 1x ho jayega - SCAN poora fast ho jayega.
                _chain_map = {}
                try:
                    _final_stock_scan = ""
                    # Qualifying wala stock dhoondo - wahi FINAL CALL banega - Prob>=50 + Movement HAAN + Fake/Sideways/Choppy nahi
                    for _i_q in range(len(df_step1)):
                        _r_q = df_step1.iloc[_i_q]
                        try:
                            _ok_q2, _why_q2 = is_qualifying_row(_r_q)
                        except:
                            _ok_q2 = False
                        if _ok_q2:
                            _final_stock_scan = str(_r_q.get("Stock", ""))
                            break
                    if not _final_stock_scan and not df_step1.empty:
                        _final_stock_scan = str(df_step1.iloc[0].get("Stock", ""))
                    if _final_stock_scan:
                        try:
                            _ch, _chmsg, _ex, _sc, _lt = ind_get_option_chain(_final_stock_scan, token, scrip_map)
                            _chain_map[_final_stock_scan] = {"chain": _ch, "msg": _chmsg, "expiry": _ex}
                        except Exception as e:
                            _chain_map[_final_stock_scan] = {"chain": pd.DataFrame(), "msg": f"Error {e}", "expiry": ""}
                except Exception as _e_chain1:
                    _chain_map = {}
                st.session_state.chain_map = _chain_map
            else:
                st.session_state.step3_results = {}
                st.session_state.chain_map = {}
            # V26 - Scan ke baad History Cache update - Aaj ke naye candles GitHub me jama kar do
            # ind_fill se df_5min milta hai - usi se Today Cache banao, Daily Cache sirf market band hone pe finalize hoga
            try:
                _s3_for_cache = st.session_state.get("step3_results", {})
                _cache_by_stock = {}
                for _cs, _cv in _s3_for_cache.items():
                    try:
                        if isinstance(_cv, dict) and _cv.get("df_5min") is not None and not _cv.get("df_5min").empty:
                            _cache_by_stock[_cs] = _cv.get("df_5min")
                    except:
                        continue
                if _cache_by_stock:
                    _td_cache = get_trading_day()
                    _d_df, _t_df, _cmsg = update_history_cache_after_scan(_cache_by_stock, _td_cache)
                    st.session_state["last_cache_msg"] = _cmsg
                    st.session_state["history_cache_saved"] = True
            except Exception as e:
                st.session_state["last_cache_msg"] = f"History Cache save me Error - {e}"
        # Indices + News - ye company/news ki jaankari ke liye hai, price ke liye nahi - price sirf IND se
        try:
            indices_df = fetch_indices_history(); news_df = fetch_global_news()
        except:
            indices_df = pd.DataFrame(); news_df = pd.DataFrame()
        st.session_state.indices_data = indices_df; st.session_state.news_data = news_df
        st.session_state.auto_sent = False
        # V28 - SCAN ke turant baad FINAL CALL bana ke rakh do - taaki RESULTS me upar hi dikh jaye, dobara click na karna pade
        try:
            _nb = "NEUTRAL"
            try:
                if news_df is not None and not news_df.empty and "Impact" in news_df.columns:
                    _neg = len(news_df[news_df["Impact"] == "NEGATIVE"]); _pos = len(news_df[news_df["Impact"] == "POSITIVE"])
                    _nb = "NEGATIVE" if _neg > _pos else "POSITIVE" if _pos > _neg else "NEUTRAL"
            except:
                _nb = "NEUTRAL"
            st.session_state["top_call_news_bias"] = _nb
            if not df_step1.empty:
                _cmap_top = st.session_state.get("chain_map", {})
                # Pehle qualifying wala stock lo, nahi to Top1 - qualifying ka matlab Rule pass + Movement suru + Fake/Sideways/Choppy nahi
                _final_row = None; _final_chain = pd.DataFrame(); _final_expiry = ""
                for _i in range(len(df_step1)):
                    _r = df_step1.iloc[_i]
                    _ok_q, _why_q = is_qualifying_row(_r)
                    if _ok_q:
                        _final_row = _r; break
                if _final_row is None:
                    _final_row = df_step1.iloc[0]
                _fstock = str(_final_row.get("Stock", ""))
                if _fstock in _cmap_top:
                    _final_chain = _cmap_top[_fstock].get("chain", pd.DataFrame())
                    _final_expiry = _cmap_top[_fstock].get("expiry", "")
                _top_call = build_trade_call(_final_row, _final_chain, _final_expiry, _nb)
                # V36 - Koi rule pass nahi karta to bhi 1 stock do - BEST EFFORT - khali mat chhodo, Score ke saath bata do pakka nahi hai
                if _top_call.get("status") == "NO_TRADE":
                    _top_call = build_best_effort_call(_final_row, _final_chain, _final_expiry, _nb, 0)
                # Session me sirf scalar rakhenge - chain DataFrame dobara chain_map se milegi
                st.session_state["top_call"] = _top_call
                st.session_state["top_call_stock"] = _fstock
        except Exception as _e_topcall:
            st.session_state["top_call"] = {"status": "NO_TRADE", "stock": "", "reason": f"FINAL CALL banane me error - {_e_topcall}", "expiry": ""}
        if not df_step1.empty:
            top = df_step1.iloc[0]
            if safe_float(top.get("Probability %", 0)) >= 70:
                ok_auto = send_top5(df_step1.head(5), "")
                st.session_state.auto_sent = ok_auto
        st.rerun()


    def _safe_cols(df, wanted):
        # V27 - KeyError Fix - Kabhi bhi df[[...]] se crash nahi hoga
        # Wajah: SCAN wali df me jo column nahi hai, usko seedha df[[...]] se mangne pe pandas KeyError deta hai - "['Probability %'] not in index" - aur poora app lal ho jata hai.
        # Ab sirf wahi column dikhayenge jo df me hai, jo nahi hai wo chhod denge - app kabhi crash nahi hoga.
        try:
            if df is None or df.empty:
                return []
            return [c for c in wanted if c in df.columns]
        except:
            return []

    # ---------------- RESULTS ----------------
    if st.session_state.scan_df is not None and not st.session_state.scan_df.empty:
        df_scan = st.session_state.scan_df; indices_df = st.session_state.indices_data; news_df = st.session_state.news_data
        st.info(f"{st.session_state.get('scan_time','')} | {len(df_scan)} stocks")
        if st.session_state.get("scan_fallback"):
            st.warning(f"Saved data se hai - Live nahi hai - {st.session_state.get('scan_fallback_msg','')} - dobara Scan karo to Live aa jayega.")
        # ---------------- V28 - FINAL CALL SABSE UPAR - Yehi mool function hai, data jama karna nahi ----------------
        # Pehle ye sabse neeche Section 6 me tha - wahan tak pahunchne ke liye 216-row wali 2 table + Debug + IND Fill scroll karna padta tha.
        # Ab SCAN ke turant baad yahin dikhega: Rule se chuna gaya 1 stock + uski Chain + Rs 5000 wala Strike + Entry / SL / Target + BUY / SELL.
        # News Bias yahin pehle nikal lo - taaki SL/Target news se adjust ho jaye, neeche wali News table baad me bhi dikhegi.
        _news_bias_top = st.session_state.get("top_call_news_bias", "NEUTRAL")
        try:
            if news_df is not None and not news_df.empty and "Impact" in news_df.columns:
                _neg_t = len(news_df[news_df["Impact"] == "NEGATIVE"]); _pos_t = len(news_df[news_df["Impact"] == "POSITIVE"])
                _news_bias_top = "NEGATIVE" if _neg_t > _pos_t else "POSITIVE" if _pos_t > _neg_t else "NEUTRAL"
        except:
            pass
        # FINAL CALL - session me hai to wahi, nahi to abhi bana lo (purana V27 wala scan ho to bhi kaam karega, dobara SCAN ki zaroorat nahi)
        _final_call = st.session_state.get("top_call", None)
        try:
            _cmap_top2 = st.session_state.get("chain_map", {})
            if not _final_call or not isinstance(_final_call, dict) or not _final_call.get("stock"):
                _frow = None
                for _i2 in range(len(df_scan)):
                    _r2 = df_scan.iloc[_i2]
                    _ok2, _why2 = is_qualifying_row(_r2)
                    if _ok2:
                        _frow = _r2; break
                if _frow is None:
                    _frow = df_scan.iloc[0]
                _fstock2 = str(_frow.get("Stock", ""))
                _fchain2 = _cmap_top2.get(_fstock2, {}).get("chain", pd.DataFrame()) if _fstock2 in _cmap_top2 else pd.DataFrame()
                _fexp2 = _cmap_top2.get(_fstock2, {}).get("expiry", "") if _fstock2 in _cmap_top2 else ""
                _final_call = build_trade_call(_frow, _fchain2, _fexp2, _news_bias_top)
                if _final_call.get("status") == "NO_TRADE":
                    _final_call = build_best_effort_call(_frow, _fchain2, _fexp2, _news_bias_top, 0)
                st.session_state["top_call"] = _final_call
        except Exception as _e_fc:
            _final_call = {"status": "NO_TRADE", "stock": "", "reason": f"FINAL CALL me error - {_e_fc}", "expiry": ""}
        st.markdown("### Best Stock")
        st.write(f"News: {_news_bias_top}")
        # V37 - Diary wala Seekha hata diya - ab AI Live neeche se aayega
        if _final_call and _final_call.get("status") == "TRADE":
            st.success(f"BUY KARO: {_final_call['stock']} {_final_call['strike']} {_final_call['opt_type']} @ Rs {_final_call['entry']} - Expiry: {_final_call['expiry']} - 1 Lot Cost Rs {_final_call['cost']:.0f} (Lot {_final_call['lot']})")
            st.write(f"**BUY:** Rs {_final_call['entry']} pe BUY karo | **SELL (Target):** Rs {_final_call['target']} pe SELL karo | **STOP LOSS:** Rs {_final_call['sl']} pe nikal jao - SL se neeche mat ruko")
            st.write(f"Max Profit: Rs {_final_call['max_profit']:.0f} | Max Loss: Rs {_final_call['max_loss']:.0f} | Prob: {_final_call['prob']:.0f}/100 | Direction: {_final_call['direction']} | Stock LTP Rs {_final_call['ltp']:.1f}")
            st.write(f"{_final_call.get('rule_line','')}")
            st.write(f"Movement: {_final_call['movement_type']} - {_final_call.get('movement_detail','')} | Session: {_final_call.get('session','')}")
            st.write(f"{_final_call.get('adjust_note','')}")
            _fc_sugg = {"date": datetime.now().strftime("%Y-%m-%d"), "time": datetime.now().strftime("%H:%M:%S"), "symbol": _final_call['stock'], "strike": _final_call['strike'], "opt_type": _final_call['opt_type'], "entry": float(_final_call['entry']), "sl": float(_final_call['sl']), "target": float(_final_call['target']), "qty_lots": 1, "qty_total": int(_final_call['lot']), "capital_used": float(_final_call['cost']), "risk": float(_final_call['max_loss']), "status": "OPEN", "reason": f"FINAL CALL - Prob {_final_call['prob']:.0f} - {_final_call['movement_type']}", "conditions": _final_call.get('rule_line','')}
            _c1, _c2 = st.columns(2)
            with _c1:
                if st.button("Telegram", use_container_width=True, key="final_call_notify"):
                    _ok_fc = send_strike(_final_call['stock'], _final_call['strike'], _final_call['opt_type'], _final_call['entry'], _final_call['sl'], _final_call['target'], _final_call['cost'], _final_call['lot'], _final_call['expiry'], str(_final_call['movement_type']))
                    if _ok_fc:
                        st.success("Chala gaya ✅")
                    else:
                        st.error("Nahi gaya ❌")
            with _c2:
                if st.button("Diary", use_container_width=True, key="final_call_diary"):
                    save_trade(_fc_sugg); st.success(st.session_state.get("_diary_last_msg","Diary me save ho gaya!")); st.rerun()
        elif _final_call and _final_call.get("status") == "BEST_EFFORT":
            # V36 - Sab rule pass nahi hua, par Top me sabse behtar yahi hai - 1 stock to do, Score ke saath, neeche Telegram bhi hai
            st.warning(f"BEST EFFORT - Sab rule pass nahi hua - Score {_final_call.get('score',0)}% - Pakka setup nahi, apne risk pe lo, chhota lot lo")
            st.write(f"Wajah: {_final_call.get('reason','')}")
            st.success(f"BUY KARO: {_final_call['stock']} {_final_call['strike']} {_final_call['opt_type']} @ Rs {_final_call['entry']} - Expiry: {_final_call['expiry']} - 1 Lot Cost Rs {_final_call['cost']:.0f} (Lot {_final_call['lot']})")
            st.write(f"**BUY:** Rs {_final_call['entry']} pe BUY karo | **SELL (Target):** Rs {_final_call['target']} pe SELL karo | **STOP LOSS:** Rs {_final_call['sl']} pe nikal jao")
            st.write(f"Max Profit: Rs {_final_call['max_profit']:.0f} | Max Loss: Rs {_final_call['max_loss']:.0f} | Prob: {_final_call['prob']:.0f}/100 | Score: {_final_call.get('score',0)}% | Direction: {_final_call['direction']} | Stock LTP Rs {_final_call['ltp']:.1f}")
            st.write(f"{_final_call.get('rule_line','')}")
            st.write(f"Movement: {_final_call['movement_type']} - {_final_call.get('movement_detail','')} | Session: {_final_call.get('session','')}")
            st.write(f"{_final_call.get('adjust_note','')}")
            _fc_sugg2 = {"date": datetime.now().strftime("%Y-%m-%d"), "time": datetime.now().strftime("%H:%M:%S"), "symbol": _final_call['stock'], "strike": _final_call['strike'], "opt_type": _final_call['opt_type'], "entry": float(_final_call['entry']), "sl": float(_final_call['sl']), "target": float(_final_call['target']), "qty_lots": 1, "qty_total": int(_final_call['lot']), "capital_used": float(_final_call['cost']), "risk": float(_final_call['max_loss']), "status": "OPEN", "reason": f"BEST EFFORT - Score {_final_call.get('score',0)}% - {_final_call.get('reason','')}", "conditions": ""}
            _c1b, _c2b = st.columns(2)
            with _c1b:
                if st.button("Telegram", use_container_width=True, key="best_effort_notify"):
                    _ok_be = send_strike(_final_call['stock'], _final_call['strike'], _final_call['opt_type'], _final_call['entry'], _final_call['sl'], _final_call['target'], _final_call['cost'], _final_call['lot'], _final_call['expiry'], str(_final_call['movement_type']))
                    if _ok_be:
                        st.success("Chala gaya ✅")
                    else:
                        st.error("Nahi gaya ❌")
            with _c2b:
                if st.button("Diary", use_container_width=True, key="best_effort_diary"):
                    save_trade(_fc_sugg2); st.success(st.session_state.get("_diary_last_msg","Diary me save ho gaya!")); st.rerun()
        elif _final_call and _final_call.get("status") == "NO_CHAIN":
            st.error(f"Rule pass hai - {_final_call.get('stock','')} - Prob {_final_call.get('prob',0):.0f}/100 - {_final_call.get('movement_type','')}")
            st.write(f"Wajah: {_final_call.get('reason','')}")
            if st.button(f"{_final_call.get('stock','')} ka Chain Mango", use_container_width=True, key="final_chain_fetch"):
                with st.spinner("Chain la rahe hain..."):
                    _tok_fc = st.session_state.get("indmoney_secret", "")
                    _smap_fc = ind_get_all_scrips(_tok_fc) if _tok_fc else {}
                    _ch_fc, _msg_fc, _ex_fc, _sc_fc, _lt_fc = ind_get_option_chain(_final_call.get('stock',''), _tok_fc, _smap_fc)
                    _cm_fc = st.session_state.get("chain_map", {})
                    _cm_fc[_final_call.get('stock','')] = {"chain": _ch_fc, "msg": _msg_fc, "expiry": _ex_fc}
                    st.session_state["chain_map"] = _cm_fc
                    # Chain mil gayi to FINAL CALL dobara banao
                    try:
                        _frow_fc = df_scan[df_scan["Stock"] == _final_call.get('stock','')].iloc[0]
                        st.session_state["top_call"] = build_trade_call(_frow_fc, _ch_fc, _ex_fc, _news_bias_top)
                    except:
                        pass
                st.rerun()
            if st.button("Telegram - Top 5", use_container_width=True, key="nochain_telegram"):
                _ok_nc = send_top5(df_scan.head(5), "")
                if _ok_nc:
                    st.success("Chala gaya ✅")
                else:
                    st.error("Nahi gaya ❌")
        elif _final_call and _final_call.get("status") == "NO_FIT":
            st.warning(f"Rule pass hai - {_final_call.get('stock','')} - Prob {_final_call.get('prob',0):.0f}/100 - par Rs 5000 wala strike nahi mila")
            st.write(f"Wajah: {_final_call.get('reason','')}")
            st.write(f"Movement: {_final_call.get('movement_type','')} - {_final_call.get('movement_detail','')}")
            if st.button("Telegram - Top 5", use_container_width=True, key="nofit_telegram"):
                _ok_nf = send_top5(df_scan.head(5), "")
                if _ok_nf:
                    st.success("Chala gaya ✅")
                else:
                    st.error("Nahi gaya ❌")
        else:
            _nt_stock = _final_call.get('stock','') if _final_call else ""
            _nt_prob = _final_call.get('prob',0) if _final_call else 0
            st.warning(f"NO TRADE - WAIT KARO - {_nt_stock} bhi pakka setup nahi hai" if _nt_stock else "NO TRADE - WAIT KARO - Aaj koi pakka setup nahi mila")
            st.write(f"Wajah: {_final_call.get('reason','') if _final_call else 'Koi qualifying stock nahi mila'}")
            if _nt_stock:
                st.write(f"Top stock: {_nt_stock} - Prob {_nt_prob:.0f}/100 | Movement: {_final_call.get('movement_type','')} - {_final_call.get('movement_detail','')} - Zabardasti strike nahi denge, warna premium ghis jayega.")
            st.write("Top 5 neeche dekh lo - koi 50+ wala ho to usko Single Search me alag se check karo, par jab tak Movement suru nahi hota, entry mat lo.")
            if st.button("Telegram - Top 5", use_container_width=True, key="notrade_telegram"):
                _ok_nt = send_top5(df_scan.head(5), "")
                if _ok_nt:
                    st.success("Chala gaya ✅")
                else:
                    st.error("Nahi gaya ❌")

        # 3-STEP DEBUG - Har step me kitne aaye, kyu fail hua, sab dikhao - chhupao mat
        _dbg1 = st.session_state.get("step1_debug", {})
        _sel = st.session_state.get("selected_stocks", [])
        _s2 = st.session_state.get("step2_results", {})
        _s3 = st.session_state.get("step3_results", {})
        _need = st.session_state.get("need_ind", [])
        with st.expander("Debug"):
            st.write(f"OK {_dbg1.get('ind_ok',0)} / {_dbg1.get('ind_total',216)} | Fail: {len(_dbg1.get('ind_fail',[]))}")
            st.write(f"Universe: {_dbg1.get('universe_msg','')} | Total Checked: {_dbg1.get('ind_total',0)}")
            st.write(f"Selected (Top 15 + Prob>=50 + Manual News wale - 5 sirf example tha): {_sel}")
            st.write("")
            st.write("")
            if _s3:
                for _k, _v in _s3.items():
                    st.write(f"  - {_k}: {_v.get('reason','')}")
            st.write("")
        _logs5b = st.session_state.get("ind_5x5_logs", [])
        if _logs5b:
            st.write("Log:")
            for _ll in _logs5b:
                st.write(f"  - {_ll}")
        # V19 - Top 5 ka 100 me se Score kaise bana - yehi gayab ho gaya tha
        if not df_scan.empty:
            with st.expander("Score", expanded=False):
                for _idx in range(min(5, len(df_scan))):
                    _row = df_scan.iloc[_idx]
                    _stk = _row.get("Stock", "")
                    _prob = int(safe_float(_row.get("Probability %", 0)))
                    st.markdown(f"**{_idx+1}. {_stk} - { _prob }/100**")
                    # Is row se breakdown banao - df_scan me saare Criteria hain
                    _brows = [
                        {"Criteria": "1. Gap", "Value": f"{safe_float(_row.get('Gap %',0)):+.2f}%", "Pass?": _row.get("Gap",""), "Ank": 15 if _row.get("Gap","")=="✅" else 0, "Max": 15},
                        {"Criteria": "2. VWAP", "Value": f"LTP {safe_float(_row.get('LTP',0)):.2f} vs VWAP {safe_float(_row.get('VWAP',0)):.2f}", "Pass?": _row.get("VWAP_OK", _row.get("VWAP","")), "Ank": 15 if _row.get("VWAP_OK", _row.get("VWAP",""))=="✅" else 0, "Max": 15},
                        {"Criteria": "3. ORB Break", "Value": f"ORB High {safe_float(_row.get('ORB High',0)):.2f}", "Pass?": _row.get("ORB",""), "Ank": 20 if _row.get("ORB","")=="✅" else 0, "Max": 20},
                        {"Criteria": "4. Volume", "Value": f"{safe_float(_row.get('Vol x',0)):.2f}x", "Pass?": _row.get("Volume",""), "Ank": 15 if _row.get("Volume","")=="✅" else 0, "Max": 15},
                        {"Criteria": "5. Movement Started?", "Value": str(_row.get("Movement Started?","")), "Pass?": "✅" if str(_row.get("Movement Started?",""))=="HAAN" else "❌", "Ank": 15 if str(_row.get("Movement Started?",""))=="HAAN" else 0, "Max": 15},
                        {"Criteria": "6. Trending / 7. Volatility", "Value": f"{_row.get('Movement Type','')} | Pass: {_row.get('Pass','')}", "Pass?": _row.get("Volatility OK",""), "Ank": "Baki 20 ank Trending+Volatility se - poora hisab Single Search me dekho", "Max": 20},
                        {"Criteria": "KATOTI Fake/Choppy", "Value": f"Fake: {_row.get('Fake?','')} | Movement: {_row.get('Movement Type','')}", "Pass?": "❌ KATA" if "TRAP" in str(_row.get("Fake?","")) else "✅ SAHI", "Ank": "-30 agar Fake hai", "Max": 0},
                    ]
                    st.dataframe(pd.DataFrame(_brows), use_container_width=True, hide_index=True)
                    st.write(f"Final: {_prob}/100")

        _cmap = st.session_state.get("chain_map", {})
        # IND-ONLY TABLE - Data jama wala hissa - ab band (collapsed) expander me, taaki FINAL CALL ke upar na aaye
        with st.expander("Data", expanded=False):
            if _s3:
                st.markdown("### Detail")
                _rows3 = []
                for _k, _v in _s3.items():
                    _rows3.append({"Stock": _k, "OK?": "✅" if _v.get("ok") else "❌"})
                st.dataframe(pd.DataFrame(_rows3), use_container_width=True, hide_index=True)
            _cmap = st.session_state.get("chain_map", {})
            if _cmap:
                st.markdown("### Chain")
                _rowsC = []
                for _k, _v in _cmap.items():
                    _ch = _v.get("chain", pd.DataFrame())
                    _rowsC.append({"Stock": _k, "Expiry": _v.get("expiry",""), "Chain Rows": len(_ch) if _ch is not None else 0})
                st.dataframe(pd.DataFrame(_rowsC), use_container_width=True, hide_index=True)
        if st.session_state.get("auto_sent"):
            st.success("Chala gaya ✅")
        st.markdown("### Index")
        if indices_df is not None and not indices_df.empty:
            st.dataframe(indices_df, use_container_width=True, hide_index=True)
        st.markdown("### News")
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
        st.markdown("### Top 5")
        top5 = df_scan.head(5)
        st.dataframe(top5[_safe_cols(top5, ["Stock", "LTP", "Gap %", "Direction", "Pattern", "Movement Type", "Probability %", "Movement", "Movement Started?", "Pass"])], use_container_width=True, hide_index=True)
        top1 = df_scan.iloc[0]; top1_stock = str(top1.get("Stock", "")); top1_prob = safe_float(top1.get("Probability %", 0)); top1_ltp = safe_float(top1.get("LTP", 0))
        st.success(f"No.1: {top1_stock} - Prob {top1_prob:.0f}% - LTP Rs {top1_ltp:.1f} - {top1.get('Movement Type','')}")
        st.write(f"No.1 ka Poora Din: {top1.get('Movement Detail','')}")
        st.write(f"Session: {top1.get('Session Story','')}")
        if st.button("Telegram - Top 5", use_container_width=True):
            ok = send_top5(top5, "")
            if ok:
                st.success("Chala gaya ✅")
            else:
                st.error("Nahi gaya ❌")
        st.markdown("### Movement")
        st.write("Sideways = Option mat lo, wait karo. Bhag Raha = Option le sakte ho. Volatile/Choppy = Premium kha jayega, mat lo. Fake = Trap tha.")
        st.dataframe(df_scan[_safe_cols(df_scan, ["Stock", "LTP", "Day Range %", "Net Move %", "Range vs ATR", "Movement Type", "Session Story", "VWAP Cross", "Wick", "Reversal", "Fake?", "Probability %"])], use_container_width=True, hide_index=True)
        st.markdown("### Market")
        # V27 - PURA MARKET me VWAP float nahi, ✅/❌ dikhana hai - isliye display copy me VWAP = VWAP_OK kar do, original df_scan ka VWAP float bacha rahega
        _disp_pura = df_scan.copy()
        try:
            if "VWAP_OK" in _disp_pura.columns:
                _disp_pura["VWAP"] = _disp_pura["VWAP_OK"]
        except:
            pass
        st.dataframe(_disp_pura[_safe_cols(_disp_pura, ["Stock", "LTP", "Gap %", "Direction", "Pattern", "Movement Type", "Probability %", "Gap", "VWAP", "ORB", "Volume", "Volatility OK", "Movement Started?", "Pass"])], use_container_width=True, hide_index=True)
        st.markdown("### Chain")
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
            if st.button(f"{sel_stock} ka Option Chain Mango - Sirf IND Se", use_container_width=True):
                with st.spinner("Sirf IND se Option Chain dekh rahe hain - underlying-scrip = SECURITY_ID se..."):
                    # V24 - Option Chain sirf IND se - chain_map me pehle se IND se aaya hua hai, wahi use karo, nahi to abhi IND se mango
                    _cmap2 = st.session_state.get("chain_map", {})
                    _ind_oc = None
                    _ind_msg = ""
                    if sel_stock in _cmap2:
                        _ind_oc = _cmap2[sel_stock].get("chain", pd.DataFrame())
                        _ind_msg = _cmap2[sel_stock].get("msg", "")
                    if _ind_oc is not None and not _ind_oc.empty and len(_ind_oc) >= 5:
                        st.session_state[f"chain_{sel_stock}"] = _ind_oc
                        st.session_state[f"chain_source_{sel_stock}"] = _ind_msg if _ind_msg else "Chain Map se aaya (msg khali tha)"
                        st.session_state[f"expiry_{sel_stock}"] = _cmap2[sel_stock].get("expiry", "")
                        st.session_state[f"scrip_{sel_stock}"] = f"NSE_{scrip_used}"
                        st.session_state[f"indltp_{sel_stock}"] = sel_ltp
                    else:
                        # chain_map me nahi tha to abhi IND se mango
                        token_now = st.session_state.get("indmoney_secret", "")
                        scrip_map_now = ind_get_all_scrips(token_now) if token_now else {}
                        chain_df, source, expiry_yyyy, scrip_used, ind_ltp = ind_get_option_chain(sel_stock, token_now, scrip_map_now)
                        st.session_state[f"chain_{sel_stock}"] = chain_df
                        st.session_state[f"chain_source_{sel_stock}"] = source
                        st.session_state[f"expiry_{sel_stock}"] = expiry_yyyy
                        st.session_state[f"scrip_{sel_stock}"] = scrip_used
                        st.session_state[f"indltp_{sel_stock}"] = ind_ltp
                    st.rerun()
            chain_key = f"chain_{sel_stock}"
            if chain_key in st.session_state and st.session_state[chain_key] is not None and not st.session_state[chain_key].empty:
                chain_df = st.session_state[chain_key]; source = st.session_state.get(f"chain_source_{sel_stock}", ""); expiry_shown = st.session_state.get(f"expiry_{sel_stock}", ""); scrip_shown = st.session_state.get(f"scrip_{sel_stock}", ""); ind_ltp_shown = st.session_state.get(f"indltp_{sel_stock}", "")
                st.success(f"Expiry: {expiry_shown} - Strikes: {len(chain_df)}")
                st.dataframe(chain_df, use_container_width=True, hide_index=True)
                # V25 - Lot Size pehle Universe (Master FNO) se, nahi to purana LOT_SIZES se - FNO me LOT_SIZE likha hota hai
                lot = LOT_SIZES.get(sel_stock, 100)
                try:
                    _udf_lot = st.session_state.get("universe_216_df", None)
                    if _udf_lot is not None and not _udf_lot.empty and "STOCK" in _udf_lot.columns and "LOT_SIZE" in _udf_lot.columns:
                        _lr = _udf_lot[_udf_lot["STOCK"].astype(str).str.upper() == str(sel_stock).upper()]
                        if not _lr.empty and str(_lr.iloc[0]["LOT_SIZE"]).strip() not in ("", "nan", "0"):
                            lot = int(float(str(_lr.iloc[0]["LOT_SIZE"]).strip()))
                except:
                    pass
                check_df, best = check_all_strikes(chain_df, lot, sel_ltp, row.get("Direction", ""), budget=5000)
                st.markdown(f"#### Strikes (Lot: {lot})")
                if not check_df.empty:
                    st.dataframe(check_df, use_container_width=True, hide_index=True)
                    fits_df = check_df[check_df["Fits"] == True]
                    st.write(f"Total: {len(check_df)} | Fit: {len(fits_df)}")
                    if not fits_df.empty:
                        st.dataframe(fits_df[["Strike", "Type", "Premium", "1 Lot Cost", "Fit?", "OI", "IV"]], use_container_width=True, hide_index=True)
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
                    if st.button("Telegram", use_container_width=True):
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
                _chain_msg_show = st.session_state.get(f'chain_source_{sel_stock}','')
                st.error(f"❌ Option Chain nahi aaya - Wajah: {_chain_msg_show}")
                st.write("")
                if "Rate limit" in _chain_msg_show:
                    st.write("1-2 minute ruko, phir Chain Mango dabao - bar-bar dabane se limit aur badhegi.")
                else:
                    st.write("Dobara try karo, ya Download Data se Master FNO dobara lo.")
            else:
                st.info("Chain Mango dabao")
    else:
        # V33 - Scan khali aaya to neeche blank mat chhodo - pehle blank rehta tha, isliye lagta tha Best Stock + Telegram gayab ho gaya. Ab wajah + Telegram dikhega.
        if st.session_state.get("scan_time"):
            st.markdown("### Best Stock")
            st.warning("Nahi mila - Koi data nahi hai")
            _dbg_e = st.session_state.get("step1_debug", {})
            _ok_e = _dbg_e.get("ind_ok", 0)
            _tot_e = _dbg_e.get("ind_total", 216)
            st.write(f"Checked: {_ok_e}/{_tot_e} - 0 hai to matlab IND se data aaya hi nahi.")
            # V39 - Asli wajah dikhao, Token pe ilzaam nahi - Scrip Map kitna bada tha, pehli fail kis wajah se hui
            if _dbg_e.get("scrip_map_size") is not None:
                st.write(f"Scrip Map: {_dbg_e.get('scrip_map_size')} entries - 216 se kam hai to bahut stock ka Code hi nahi mila.")
            if _dbg_e.get("first_fail_reason"):
                st.write(f"Pehli fail wajah: {_dbg_e.get('first_fail_reason')}")
            st.write("Kya karo: 1) Download Data dabao - Saved data aayega | 2) Phir Scan dabao.")
            if _dbg_e.get("fallback_msg"):
                st.write(f"Saved se bhi nahi mila: {_dbg_e.get('fallback_msg')}")
            if st.button("Telegram", use_container_width=True, key="empty_telegram"):
                _ok_t = send_telegram("Scan khali aaya - koi stock nahi mila. Dobara Scan dabao.")
                if _ok_t:
                    st.success("Chala gaya ✅")
                else:
                    st.error("Nahi gaya ❌")
