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
from findstock.data import resolve_to_symbol
from findstock.diary import get_all_trades
from findstock.helpers import APP_DIR, MARKET_STOCKS, MASTER_FOLDER, _push_master_to_github, safe_float
from findstock.scan import scan_from_saved_history

# ---- V48 split: ye module app_v47.py se nikala gaya, code same hai ----
def load_ai_live():
    # V37 - AI Worker ne jo Market + News + Crash + Impact likha hai, wo yahan se padhenge - Local file -> GitHub data/ai_live.json
    # 5 min ka cache - har click pe dobara download nahi hoga
    try:
        import streamlit as _st
        _cached = _st.session_state.get("_ai_live_cache", None)
        _ct = _st.session_state.get("_ai_live_time", None)
        if _cached is not None and _ct is not None:
            try:
                if (datetime.now() - _ct).total_seconds() < 300:
                    return _cached
            except:
                pass
    except:
        pass
    _data = None
    try:
        for _cand in [APP_DIR / MASTER_FOLDER / "ai_live.json", Path.cwd() / MASTER_FOLDER / "ai_live.json", APP_DIR / "ai_live.json"]:
            try:
                if _cand.is_file():
                    import json as _js
                    _data = _js.loads(_cand.read_text(encoding="utf-8", errors="ignore"))
                    break
            except:
                continue
    except:
        pass
    if _data is None and GITHUB_REPO:
        # V43 - Branch main ho ya master, dono try karo - repo ki default branch jo bhi ho, AI mil jayega
        for _branch in ["main", "master"]:
            try:
                _r = requests.get(f"https://raw.githubusercontent.com/{GITHUB_REPO}/{_branch}/{MASTER_FOLDER}/ai_live.json", timeout=10)
                if _r.status_code == 200 and len(_r.text.strip()) > 20:
                    import json as _js
                    _data = _js.loads(_r.text)
                    break
            except:
                continue
    try:
        import streamlit as _st
        if _data is not None:
            _st.session_state["_ai_live_cache"] = _data
            _st.session_state["_ai_live_time"] = datetime.now()
    except:
        pass
    return _data


def load_ai_memory():
    # V37 - AI ki yaad - pichhli baar aisa hua to kya hua - Local -> GitHub data/ai_memory.json
    try:
        for _cand in [APP_DIR / MASTER_FOLDER / "ai_memory.json", Path.cwd() / MASTER_FOLDER / "ai_memory.json"]:
            try:
                if _cand.is_file():
                    import json as _js
                    return _js.loads(_cand.read_text(encoding="utf-8", errors="ignore"))
            except:
                continue
    except:
        pass
    if GITHUB_REPO:
        try:
            _r = requests.get(f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{MASTER_FOLDER}/ai_memory.json", timeout=10)
            if _r.status_code == 200 and len(_r.text.strip()) > 20:
                import json as _js
                return _js.loads(_r.text)
        except:
            pass
    return None


def build_ai_live_fallback():
    # V38 - Worker nahi chala to bhi AI Live khali nahi rahega - App ke saved data + News se hi bana do
    try:
        _dfb, _msgb = scan_from_saved_history()
        _up = _down = 0
        _avg_gap = 0.0
        if _dfb is not None and not _dfb.empty:
            _up = int((_dfb["Gap %"] > 0).sum()) if "Gap %" in _dfb.columns else 0
            _down = int((_dfb["Gap %"] < 0).sum()) if "Gap %" in _dfb.columns else 0
            _avg_gap = round(safe_float(_dfb["Gap %"].mean()), 2) if "Gap %" in _dfb.columns else 0.0
        if _up >= _down * 1.5 and _up >= 10:
            _dir = "BULLISH"
        elif _down >= _up * 1.5 and _down >= 10:
            _dir = "BEARISH"
        else:
            _dir = "SIDEWAYS"
        _news_f = []
        try:
            _ndf = fetch_global_news()
            if _ndf is not None and not _ndf.empty:
                for _, _r in _ndf.head(10).iterrows():
                    _news_f.append({"title": str(_r.get("News", "")), "type": "OTHER", "direction": str(_r.get("Impact", "")), "impact": "Is khabar ka asar dekhne ke liye AI se Puchho me stock ka naam likho"})
        except:
            pass
        _alerts = []
        if _down >= 150:
            _alerts.append(f"POORA MARKET NEECHE - Saved data me 216 me se {_down} neeche")
        elif _up >= 150:
            _alerts.append(f"POORA MARKET UPAR - Saved data me 216 me se {_up} upar")
        return {"updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "fallback": True,
                "market": {"direction": _dir, "nifty": 0, "nifty_change_pct": _avg_gap, "bank_nifty": 0, "bank_nifty_change_pct": 0, "sensex": 0, "sensex_change_pct": 0, "vix": 0, "advance": _up, "decline": _down},
                "crash_alerts": _alerts, "news": _news_f, "fallback_msg": _msgb}
    except Exception as e:
        return {"updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "fallback": True,
                "market": {"direction": "SIDEWAYS", "nifty": 0, "nifty_change_pct": 0, "bank_nifty": 0, "bank_nifty_change_pct": 0, "sensex": 0, "sensex_change_pct": 0, "vix": 0, "advance": 0, "decline": 0},
                "crash_alerts": [], "news": [], "fallback_msg": f"Fallback me error - {e}"}


_NEWS_RSS_CACHE = {}

def fetch_stock_news_rss(stock, company=""):
    # V44 - ASLI KHABAR INTERNET SE - Google News RSS, bina key ke.
    # User ne sahi bola: Gap / Volume / VWAP / ORB se ye nahi pata chalta ki log KYU bech rahe hain -
    # koi meeting hua, deal hua, results aaye, downgrade hua - ye sirf khabar se pata chalega.
    # Isliye AI answer me pehle ye khabar aayegi, chart baad me. Cache 10 min - har sawaal pe dobara internet mat kholo.
    # Fail ho to [] - app kabhi crash nahi hoga, jawaab me imandari se "khabar nahi mili" likh denge.
    try:
        _sym = str(stock or "").strip().upper()
        if not _sym:
            return []
        _now = time.time()
        _hit = _NEWS_RSS_CACHE.get(_sym)
        if _hit and (_now - _hit[0] < 600):
            return _hit[1]
        import xml.etree.ElementTree as _ET
        import urllib.parse as _up
        import email.utils as _eu
        _out = []
        _queries = [f"{_sym} stock"]
        if company and str(company).strip().upper() != _sym:
            _queries.append(str(company).strip())
        for _q in _queries:
            try:
                _url = "https://news.google.com/rss/search?q=" + _up.quote(_q) + "&hl=en-IN&gl=IN&ceid=IN:en"
                _r = requests.get(_url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
                if _r.status_code != 200 or not _r.text:
                    continue
                _root = _ET.fromstring(_r.text)
                for _it in _root.findall(".//item"):
                    _tt = (_it.findtext("title") or "").strip()
                    _src2 = ""
                    _s_el = _it.find("source")
                    if _s_el is not None and _s_el.text:
                        _src2 = _s_el.text.strip()
                    _pub = (_it.findtext("pubDate") or "").strip()
                    _d = ""
                    if _pub:
                        try:
                            _d = _eu.parsedate_to_datetime(_pub).strftime("%d %b %H:%M")
                        except:
                            _d = _pub[:16]
                    if _tt and _tt not in [x["title"] for x in _out]:
                        _out.append({"title": _tt, "source": _src2, "date": _d})
                    if len(_out) >= 6:
                        break
                if _out:
                    break
            except:
                continue
        _NEWS_RSS_CACHE[_sym] = (_now, _out)
        return _out
    except:
        return []

def _news_theme_line(items):
    # Khabaron se ek line ka matlab - sirf jo khabar me likha hai, wahi bolenge, kahani nahi banayenge.
    try:
        _all = " ".join([str(x.get("title", "")) for x in (items or [])]).lower()
        _themes = []
        if any(w in _all for w in ["acquir", "acquisition", "takeover", "stake", "merger", "buyout", "deal"]):
            _themes.append("khabar me deal / acquisition / stake khareedne ki baat hai")
        if "block deal" in _all:
            _themes.append("bada block deal hua hai")
        if "promoter" in _all:
            _themes.append("promoter stake ki baat hai")
        if any(w in _all for w in ["debt", "loan", "borrow"]):
            _themes.append("karz / debt ki baat hai")
        if any(w in _all for w in ["downgrade", "target cut", "cuts target"]):
            _themes.append("broker ne downgrade kiya hai")
        if any(w in _all for w in ["results", "profit", "q2", "q3", "earnings", "quarter"]):
            _themes.append("results / profit ki khabar hai")
        if any(w in _all for w in ["order", "contract"]):
            _themes.append("naya order / contract mila hai")
        if any(w in _all for w in ["probe", "raid", "fraud", "default", "sebi", "penalty"]):
            _themes.append("jaanch / penalty / default jaisi negative khabar hai")
        if not _themes:
            return ""
        return " | ".join(_themes[:2]) + " - isliye log bech / khareed rahe hain."
    except:
        return ""

def _github_models_token():
    # V50 - GitHub Models token: Streamlit Secrets me GITHUB_MODELS_TOKEN naam se daalo (GitHub PAT, models:read permission).
    # Token kabhi chat me mat likho, kabhi print mat karo.
    try:
        import streamlit as _st_t
        for _k in ("GITHUB_MODELS_TOKEN", "GITHUB_TOKEN", "GH_MODELS_TOKEN"):
            try:
                _v = _st_t.secrets.get(_k, "") if hasattr(_st_t, "secrets") else ""
            except:
                _v = ""
            if _v:
                return str(_v).strip()
    except:
        pass
    try:
        import os
        for _k in ("GITHUB_MODELS_TOKEN", "GITHUB_TOKEN", "GH_MODELS_TOKEN"):
            if os.environ.get(_k):
                return str(os.environ[_k]).strip()
    except:
        pass
    return ""


def _github_models_reply(question):
    # V50 - Chatbot advance: GitHub Models (LLM) se jawab. Sirf apne data ke context ke saath, taaki LLM kahani na banaye.
    # Token na ho ya API fail ho to None - caller rule-based chatbot pe gir jayega. Kabhi crash nahi.
    try:
        _tok = _github_models_token()
        if not _tok:
            return None
        import requests as _rq_g
        _ctx_parts = []
        try:
            import streamlit as _st3
            _sdf3 = _st3.session_state.get("scan_df", None)
            if _sdf3 is not None and not _sdf3.empty:
                _ctx_parts.append("SCAN DATA (aaj ka scan):\n" + _sdf3.head(20).to_string(index=False)[:3000])
        except:
            pass
        try:
            _live3 = load_ai_live()
            if _live3:
                _ctx_parts.append("LIVE/MARKET NOTE:\n" + str(_live3)[:1500])
        except:
            pass
        _ctx = "\n\n".join(_ctx_parts)[:4500]
        _msgs = [{"role": "system", "content": "Tum ek Indian stock market (NSE/BSE, F&O) trading assistant ho. Hindi/Hinglish me jawab do, chhota aur number ke saath. Sirf diye gaye DATA se jawab do - data me jo nahi hai uspe 'pata nahi' bolo, kahani mat banao. Trading advice nahi, sirf data ki vyakhya."}]
        if _ctx:
            _msgs.append({"role": "system", "content": "DATA:\n" + _ctx})
        _msgs.append({"role": "user", "content": str(question)})
        _r = _rq_g.post("https://models.github.ai/inference/chat/completions",
            headers={"Authorization": f"Bearer {_tok}", "Content-Type": "application/json", "Accept": "application/vnd.github+json"},
            json={"model": "openai/gpt-4o-mini", "messages": _msgs, "temperature": 0.3, "max_tokens": 800},
            timeout=20)
        if _r.status_code != 200:
            return None
        _j = _r.json()
        _txt = str((_j.get("choices") or [{}])[0].get("message", {}).get("content", "") or "").strip()
        return _txt or None
    except:
        return None


def ask_stock_ai(question):
    # V38 - AI Chat - ChatGPT jaisa, par sirf stock ke liye, aur sirf apne data se - banayi hui wajah nahi bolega
    # Kya batayega: Koi stock kyu bhaga / kyu gira - Gap, Volume, VWAP, ORB, News, Diary - sab number ke saath
    # Jo data me nahi hai, uspe "pata nahi" bolega, kahani nahi banayega
    # Har sawaal-jawaab data/ai_chat.json me judta jayega (kabhi delete nahi hoga) - isi se AI seekhega
    try:
        _q = str(question or "").strip()
        if not _q:
            return "Sawaal likho - jaise 'RELIANCE kyu bhaga?' ya 'Market kyu gira?'"
        # V50 - Pehle GitHub Models (LLM) se advanced jawab. Token na ho / API fail ho to neeche rule-based chalega.
        try:
            _gh = _github_models_reply(_q)
            if _gh:
                return _gh
        except:
            pass
        _qu = _q.upper()
        # 1) Stock dhoondho - sawaal me kaunsa stock hai
        _stock = ""
        try:
            import streamlit as _st2
            _sdf = _st2.session_state.get("scan_df", None)
            _cands = []
            if _sdf is not None and not _sdf.empty and "Stock" in _sdf.columns:
                _cands = [str(x).upper() for x in _sdf["Stock"].tolist()]
            for _k in list(MARKET_STOCKS.keys()):
                if _k not in _cands:
                    _cands.append(str(_k).upper())
            for _c in _cands:
                if _c and len(_c) >= 3 and _c in _qu:
                    _stock = _c
                    break
            if not _stock:
                # V39 - FIX: Poora sawaal ek saath nahi, tukde-tukde karke dekho - "SBI kyu bhaga?" me "SBI" alag se milega -> SBIN
                _words = _q.replace("?", " ").replace(",", " ").split()
                _found = ""
                for _n in (4, 3, 2, 1):
                    for _i in range(0, max(0, len(_words) - _n + 1)):
                        _phrase = " ".join(_words[_i:_i+_n])
                        try:
                            _s2, _ = resolve_to_symbol(_phrase)
                        except:
                            _s2 = None
                        if _s2:
                            _found = str(_s2).upper()
                            break
                    if _found:
                        break
                if _found:
                    _stock = _found
                else:
                    _sym2, _sugg2 = resolve_to_symbol(_q)
                    if _sym2:
                        _stock = str(_sym2).upper()
        except:
            pass
        # 2) General sawaal - Market / Crash / Best
        if not _stock:
            if any(w in _qu for w in ["MARKET", "NIFTY", "CRASH", "SENSEX", "POORA"]):
                _ai = load_ai_live()
                if not _ai:
                    _ai = build_ai_live_fallback()
                _m = (_ai or {}).get("market", {}) or {}
                _ans = f"Market: {_m.get('direction', '')} - Upar: {_m.get('advance', '')} | Neeche: {_m.get('decline', '')}"
                _cr = (_ai or {}).get("crash_alerts", []) or []
                if _cr:
                    _ans += "\nCrash: " + " | ".join(_cr)
                else:
                    _ans += "\nKoi crash nahi hai."
                _nw = (_ai or {}).get("news", []) or []
                if _nw:
                    _ans += "\nBadi khabar: " + str(_nw[0].get("title", ""))[:120]
                _save_ai_chat(_q, _ans)
                return _ans
            if any(w in _qu for w in ["BEST", "TOP", "KAUN SA", "KON SA", "KAUNSA"]):
                try:
                    import streamlit as _st3
                    _sdf3 = _st3.session_state.get("scan_df", None)
                    if _sdf3 is not None and not _sdf3.empty:
                        _top = _sdf3.iloc[0]
                        _ans = f"Top stock: {str(_top.get('Stock',''))} - Score {safe_float(_top.get('Probability %',0)):.0f}/100 - {str(_top.get('Direction',''))} - {str(_top.get('Movement Type',''))} - Gap {safe_float(_top.get('Gap %',0)):+.2f}% - Vol {safe_float(_top.get('Vol x',0)):.1f}x"
                        _save_ai_chat(_q, _ans)
                        return _ans
                except:
                    pass
                _ans = "Abhi Scan nahi hua hai - pehle Scan dabao, phir Best stock bata paunga."
                _save_ai_chat(_q, _ans)
                return _ans
            _ans = "Kis stock ke baare me puchh rahe ho, naam likho - jaise 'RELIANCE kyu bhaga?'"
            _save_ai_chat(_q, _ans)
            return _ans
        # 3) Stock wala sawaal - Row + News + Diary + History se jawaab banao
        _row = None
        try:
            import streamlit as _st4
            _sdf4 = _st4.session_state.get("scan_df", None)
            if _sdf4 is not None and not _sdf4.empty and "Stock" in _sdf4.columns:
                _m4 = _sdf4[_sdf4["Stock"].astype(str).str.upper() == _stock]
                if not _m4.empty:
                    _row = _m4.iloc[0]
        except:
            pass
        if _row is None:
            try:
                _dfb2, _ = scan_from_saved_history()
                if _dfb2 is not None and not _dfb2.empty and "Stock" in _dfb2.columns:
                    _m5 = _dfb2[_dfb2["Stock"].astype(str).str.upper() == _stock]
                    if not _m5.empty:
                        _row = _m5.iloc[0]
            except:
                pass
        if _row is None:
            _ans = f"{_stock} ka data abhi nahi hai - pehle Scan ya Download Data dabao, phir bata paunga."
            _save_ai_chat(_q, _ans)
            return _ans
        _gap = safe_float(_row.get("Gap %", 0)); _volx = safe_float(_row.get("Vol x", 0)); _ltp = safe_float(_row.get("LTP", 0))
        _vwap = safe_float(_row.get("VWAP", 0)); _orb = str(_row.get("ORB", "")); _moved = str(_row.get("Movement Started?", ""))
        _mtype = str(_row.get("Movement Type", "")); _dir = str(_row.get("Direction", "")); _score = safe_float(_row.get("Probability %", 0))
        _is_up = "BHAGA" in _qu or "UPAR" in _qu or "BADHA" in _qu or "TEZ" in _qu
        _is_down = "GIRA" in _qu or "NEECHE" in _qu or "CRASH" in _qu or "GIR" in _qu
        _parts = []
        _parts.append(f"{_stock} - LTP Rs {_ltp:.1f} - Score {_score:.0f}/100 - {_dir} - {_mtype}")
        _reasons = []
        if abs(_gap) >= 0.5:
            _reasons.append(f"Gap {_gap:+.2f}% tha - khulte hi {'upar' if _gap > 0 else 'neeche'} khula")
        if _volx >= 1.5:
            _reasons.append(f"Volume {_volx:.1f}x tha - normal se zyada log khareed/bech rahe the")
        if _ltp > _vwap and _dir == "BULLISH":
            _reasons.append(f"VWAP ({_vwap:.1f}) se upar tha - khareedne wale bhari the")
        elif _ltp < _vwap and _dir == "BEARISH":
            _reasons.append(f"VWAP ({_vwap:.1f}) se neeche tha - bechne wale bhari the")
        if _orb == "✅" or _moved == "HAAN":
            _reasons.append("ORB toota tha - subah ke range se bahar nikla, isliye movement aaya")
        # Diary - is stock me pehle kya hua
        _diary_hit = ""
        try:
            _dd = get_all_trades()
            if _dd is not None and not _dd.empty and "symbol" in _dd.columns:
                _dg = _dd[_dd["symbol"].astype(str).str.upper() == _stock]
                if not _dg.empty:
                    _last = _dg.iloc[-1]
                    _diary_hit = f"Diary me isme pichhli baar {str(_last.get('status',''))} hua tha (Entry Rs {safe_float(_last.get('entry',0))})"
        except:
            pass
        if _diary_hit:
            _reasons.append(_diary_hit)
        if _is_up:
            _parts.append("Kyu bhaga / upar gaya - asli wajah:")
        elif _is_down:
            _parts.append("Kyu gira / neeche gaya - asli wajah:")
        else:
            _parts.append("Kya hua - asli wajah:")
        # V44 - ASLI WAJAH PEHLE, CHART BAAD ME - Gap / Volume / VWAP / ORB se ye nahi pata chalta
        # ki log KYU bech rahe hain. Isliye pehle internet (Google News RSS) se is stock ki aaj ki khabar.
        _news_items = fetch_stock_news_rss(_stock)
        if _news_items:
            _parts.append("Asli Wajah (Aaj ki Khabar se - internet):")
            for _ni in _news_items[:5]:
                _parts.append(f"  - [{_ni.get('date', '')}] {_ni.get('title', '')} ({_ni.get('source', '')})")
            _theme = _news_theme_line(_news_items)
            if _theme:
                _parts.append(f"Iska matlab: {_theme}")
        else:
            _parts.append("Aaj is stock ki koi badi khabar internet pe nahi mili - isliye neeche sirf chart wali wajah dikha rahe hain.")
        _parts.append("Chart me kya dikha (sirf support ke liye):")
        if _reasons:
            for _r in _reasons:
                _parts.append(f"  - {_r}")
        else:
            _parts.append("  - Chart me koi saaf wajah nahi mili - Gap, Volume me kuch khaas nahi tha. Upar wali khabar hi asli wajah hai.")
        _ans = "\n".join(_parts)
        _save_ai_chat(_q, _ans)
        return _ans
    except Exception as e:
        return f"AI se puchhne me error - {e} - pehle Scan ya Download Data dabao"


def _save_ai_chat(question, answer):
    # V38 - Har sawaal-jawaab judta jayega, kabhi delete nahi hoga - isi se AI seekhega
    try:
        import json as _js
        _rec = {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "q": str(question)[:300], "a": str(answer)[:2000]}
        _existing = []
        try:
            for _cand in [APP_DIR / MASTER_FOLDER / "ai_chat.json", Path.cwd() / MASTER_FOLDER / "ai_chat.json"]:
                if _cand.is_file():
                    _existing = _js.loads(_cand.read_text(encoding="utf-8", errors="ignore")) or []
                    break
        except:
            _existing = []
        if not isinstance(_existing, list):
            _existing = []
        _existing.append(_rec)
        _existing = _existing[-500:]
        _txt = _js.dumps(_existing, ensure_ascii=False, indent=2)
        try:
            _push_master_to_github("ai_chat.json", _txt)
        except:
            pass
        try:
            _p = APP_DIR / MASTER_FOLDER / "ai_chat.json"
            _p.parent.mkdir(parents=True, exist_ok=True)
            _p.write_text(_txt, encoding="utf-8")
        except:
            pass
    except:
        pass


def fetch_global_news():
    news_rows = []; seen = set()
    for ticker in ["^NSEI", "^NSEBANK", "^BSESN"]:
        try:
            tk = yf.Ticker(ticker)
            news = tk.news if hasattr(tk, 'news') else []
            for n in news[:5]:
                title = n.get('title', '') if isinstance(n, dict) else getattr(n, 'title', '')
                if not title or title in seen:
                    continue
                seen.add(title)
                provider = n.get('provider', '') if isinstance(n, dict) else ''
                low = title.lower()
                neg = sum(1 for w in ["fed", "rate hike", "hike", "election", "uncertainty", "war", "fall", "drop", "negative", "crisis", "inflation", "recession"] if w in low)
                pos = sum(1 for w in ["rate cut", "cut", "growth", "positive", "rise", "rally", "policy", "reform", "profit", "record"] if w in low)
                if neg > pos:
                    sentiment = "NEGATIVE"; impact = "NEGATIVE"
                elif pos > neg:
                    sentiment = "POSITIVE"; impact = "POSITIVE"
                else:
                    sentiment = "NEUTRAL"; impact = "NEUTRAL"
                news_rows.append({"News": title[:120], "Source": provider, "Sentiment": sentiment, "Impact": impact})
        except:
            continue
    if len(news_rows) == 0:
        news_rows = [{"News": "Fed ka faisla aane wala hai.", "Source": "Global Check", "Sentiment": "NEUTRAL", "Impact": "NEUTRAL"}]
    return pd.DataFrame(news_rows)

# ---------------- TELEGRAM ----------------