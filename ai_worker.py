# ai_worker_v2.py - AI Worker V2 - Trading ke liye bana ChatGPT jaisa AI (Python me)
# ============================================================================================
# Pattern: GitHub ke bade AI-trading repo jaisa (TradingAgents / trAIde / llm-trading-bot / zAck)
#   - Analyst Team: Technical Analyst + News Analyst (ek saath kaam karte hain)
#   - Researcher Team: Bull vs Bear - dono taraf ki bahas, phir faisla
#   - Trader Agent: sab report jod ke CALL banata hai
#   - Risk Manager: VIX / Crash / Market dekh ke rok lagata hai
#   - Memory / RAG: News ka asar + Diary ki seekh + CSV History ki direction - sab yaad rehta hai
#
# SABSE BADI BAAT - ye worker 2 tareeke se chalta hai:
#   1) BINA LLM KEY KE: niyam + memory + CSV history se jawab dega (hamesha chalega, kabhi band nahi)
#   2) LLM KEY HO TO: upar wale tathyon ko LLM ko de ke jawab ko ChatGPT jaisa polish karwayega
#      Key code me KABHI nahi hogi - sirf GitHub Secrets / env me: LLM_API_KEY ya OPENAI_API_KEY ya GEMINI_API_KEY
#      Key nahi hai to bhi sab kaam chalega, bas jawab niyam wala hoga - koi crash nahi.
#
# YE WORKER KABHI ORDER NAHI LAGAYEGA - sirf jaankari dega, trade tum haath se loge.
#
# Data kahan se:
#   - News: RSS (koi key nahi chahiye) - Moneycontrol / ET / Livemint
#   - Market: Yahoo public quotes - sirf Nifty / BankNifty / Sensex / VIX / Crude (index ke liye)
#   - Stock Direction: data/history/*.csv - jo CSV app ne IND se download karke rakhi hai, USI se
#     (CSV hi IND ka data hai - isliye stock ki direction CSV se nikalte hain, dobara API nahi maarte)
#   - Seekh: trades_diary/all_trades.csv (tumhare trade) + news ka 1 ghante baad wala asar
#
# Chalane ke tareeke:
#   python ai_worker_v2.py --once              (GitHub Actions har 15 min me yahi chalata hai)
#   python ai_worker_v2.py --learn             (bazaar band ke baad - Diary + Memory se seekho)
#   python ai_worker_v2.py --ask "RELIANCE kidhar jayega?"   (sawal poochho, jawab pao)
#   python ai_worker_v2.py --brief             (aaj ka ek page ka Hindi brief banao)
#   python ai_worker_v2.py                      (laptop pe hamesha chalega, har 15 min me)
# ============================================================================================

import base64
import csv
import json
import os
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict

IST = timezone(timedelta(hours=5, minutes=30))

# ---------------- CONFIGURATION - sab setting yahin, code me bikhri nahi ----------------
# (TradingAgents jaise repo me bhi config alag hota hai - yahan upar hi hai taaki ek jagah dikhe)
AI_CONFIG = {
    "version": "V2",
    # Watchlist - in stocks ki direction har run me nikaalenge (poore 220 pe har 15 min me bhaari padega)
    "watchlist": ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "ITC", "LT", "TITAN", "HINDUNILVR"],
    # Naam ke chhote roop - SBI likho to SBIN samjhega, REL likho to RELIANCE
    "aliases": {
        "SBI": "SBIN", "STATE BANK": "SBIN", "STATE BANK OF INDIA": "SBIN",
        "REL": "RELIANCE", "RIL": "RELIANCE", "RELIANCE INDUSTRIES": "RELIANCE",
        "HDFC": "HDFCBANK", "ICICI": "ICICIBANK", "TATA": "TATAMOTORS",
        "TECHM": "TECHM", "TCHM": "TECHM", "TECH MAHINDRA": "TECHM",
        "ADANI ENERGY": "ADANIENSOL", "ADANIENSOL": "ADANIENSOL",
    },
    # Risk - in haal me Risk Manager trade ko rok dega
    "risk": {"max_vix_trade": 20.0, "crash_nifty_pct": -2.0, "fear_vix": 20.0},
    # Data kitna purana ho to "purana" maanenge (minute me)
    "freshness_minutes": 30,
    # History me kitne candle dekh ke direction nikaalenge
    "history_candles": 60,
}

# ---------------- News - RSS (koi API key nahi chahiye) ----------------
RSS_FEEDS = [
    "https://www.moneycontrol.com/rss/Markets.xml",
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://www.livemint.com/rss/markets",
    "https://www.moneycontrol.com/rss/business.xml",
]

# Khabar ka type - title me ye shabd aaye to ye type
TYPE_KEYWORDS = {
    "RBI": ["rbi", "reserve bank", "repo", "interest rate", "monetary policy", "governor"],
    "FED": ["fed", "federal reserve", "us fed", "powell", "us rate"],
    "CRUDE": ["crude", "oil price", "opec", "petrol", "diesel"],
    "EARNINGS": ["result", "quarter", "q1", "q2", "q3", "q4", "profit", "net profit", "earnings"],
    "IT": ["infosys", "tcs", "wipro", "hcl tech", "tech mahindra", "it stocks", "indian it"],
    "BANK": ["bank", "hdfc", "icici", "sbi", "axis bank", "kotak", "nbfc"],
    "PHARMA": ["pharma", "sun pharma", "cipla", "dr reddy", "divis", "drug"],
    "AUTO": ["auto", "maruti", "tata motors", "mahindra", "hero moto", "bajaj auto", "ev"],
    "METAL": ["metal", "steel", "tata steel", "jsw", "hindalco", "coal"],
    "ADANI": ["adani", "adani green", "adani ports", "adani energy"],
    "RELIANCE": ["reliance", "jio", "ril"],
}

IMPACT_MAP = {
    "RBI": "Rate / RBI wali khabar - Bank / NBFC / Realty pe seedha asar",
    "FED": "US Fed wali khabar - IT / Export wale stocks pe asar",
    "CRUDE": "Crude wali khabar - Paint / Aviation / Oil pe asar",
    "EARNINGS": "Result wali khabar - us stock pe seedha asar",
    "IT": "IT sector wali khabar",
    "BANK": "Bank sector wali khabar",
    "PHARMA": "Pharma sector wali khabar",
    "AUTO": "Auto sector wali khabar",
    "METAL": "Metal sector wali khabar",
    "ADANI": "Adani group wali khabar",
    "RELIANCE": "Reliance wali khabar - Nifty pe bhi asar daal sakti hai",
    "OTHER": "Aam market khabar",
}

# Sector -> uske stock (News Analyst isi se stock se khabar jodta hai)
SECTOR_STOCKS = {
    "IT": ["TCS", "INFY", "TECHM", "WIPRO", "HCLTECH"],
    "BANK": ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK"],
    "PHARMA": ["SUNPHARMA", "CIPLA", "DIVISLAB", "DRREDDY"],
    "AUTO": ["TATAMOTORS", "MARUTI", "M&M", "HEROMOTOCO", "BAJAJ-AUTO"],
    "METAL": ["TATASTEEL", "JSWSTEEL", "HINDALCO"],
    "ADANI": ["ADANIENSOL", "ADANIENT", "ADANIPORTS", "ADANIGREEN"],
    "RELIANCE": ["RELIANCE"],
    "CRUDE": ["RELIANCE", "ONGC", "BPCL"],
}


def fetch_rss(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
        root = ET.fromstring(data)
        items = []
        for it in root.iter("item"):
            t = it.findtext("title") or ""
            l = it.findtext("link") or ""
            if t:
                items.append({"title": t.strip(), "link": l.strip()})
        return items[:20]
    except Exception:
        return []


def classify_news(title):
    tl = title.lower()
    for ntype, words in TYPE_KEYWORDS.items():
        for w in words:
            if w in tl:
                break
        else:
            continue
        break
    else:
        ntype = "OTHER"
    neg_words = ["gir", "fall", "down", "crash", "drop", "loss", "nuksan", "slowdown", "weak", "fear", "tension", "war", "ban"]
    pos_words = ["badh", "rise", "up", "gain", "record", "high", "profit", "jeet", "strong", "rally", "jump", "order"]
    neg = sum(1 for w in neg_words if w in tl)
    pos = sum(1 for w in pos_words if w in tl)
    if neg > pos:
        direction = "NEGATIVE"
    elif pos > neg:
        direction = "POSITIVE"
    else:
        direction = "NEUTRAL"
    return ntype, direction, IMPACT_MAP.get(ntype, IMPACT_MAP["OTHER"])


def fetch_quote(symbol, timeout=15):
    # Yahoo chart API - sirf index/rate ke liye, scanner ke liye nahi
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=15m"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read().decode())
        res = (j.get("chart") or {}).get("result") or []
        if not res:
            return None
        meta = res[0].get("meta") or {}
        price = meta.get("regularMarketPrice")
        prev = meta.get("previousClose") or meta.get("chartPreviousClose")
        closes = ((res[0].get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
        closes = [c for c in closes if c is not None]
        change_pct = ((price - prev) / prev * 100) if price and prev else 0.0
        chg_15m = 0.0
        if len(closes) >= 2 and closes[-2]:
            chg_15m = (closes[-1] - closes[-2]) / closes[-2] * 100
        return {"price": float(price or 0), "prev": float(prev or 0), "change_pct": round(change_pct, 2), "chg_15m": round(chg_15m, 2)}
    except Exception:
        return None


MAJOR_STOCKS = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "ITC.NS", "LT.NS", "TITAN.NS", "HINDUNILVR.NS"]


def fetch_market():
    nifty = fetch_quote("%5ENSEI") or {}
    bank = fetch_quote("%5ENSEBANK") or {}
    sensex = fetch_quote("%5EBSESN") or {}
    vix = fetch_quote("%5EINDIAVIX") or {}
    crude = fetch_quote("CL=F") or {}
    adv = dec = 0
    for s in MAJOR_STOCKS:
        q = fetch_quote(s)
        if q:
            if q["change_pct"] >= 0:
                adv += 1
            else:
                dec += 1
    nifty_chg = nifty.get("change_pct", 0)
    if nifty_chg >= 0.5:
        direction = "BULLISH"
    elif nifty_chg <= -0.5:
        direction = "BEARISH"
    else:
        direction = "SIDEWAYS"
    return {
        "direction": direction,
        "nifty": nifty.get("price", 0),
        "nifty_change_pct": nifty_chg,
        "nifty_15m_pct": nifty.get("chg_15m", 0),
        "bank_nifty": bank.get("price", 0),
        "bank_nifty_change_pct": bank.get("change_pct", 0),
        "sensex": sensex.get("price", 0),
        "sensex_change_pct": sensex.get("change_pct", 0),
        "vix": vix.get("price", 0),
        "vix_change_pct": vix.get("change_pct", 0),
        "crude_change_pct": crude.get("change_pct", 0),
        "advance": adv,
        "decline": dec,
    }


def detect_crash(market):
    alerts = []
    n = market.get("nifty_change_pct", 0)
    n15 = market.get("nifty_15m_pct", 0)
    b = market.get("bank_nifty_change_pct", 0)
    v = market.get("vix", 0)
    vc = market.get("vix_change_pct", 0)
    c = market.get("crude_change_pct", 0)
    if n <= -2:
        alerts.append(f"MARKET CRASH - Nifty {n:+.2f}% gira")
    elif n15 <= -1:
        alerts.append(f"TEZ GIRAVAT - Nifty 15 min me {n15:+.2f}% gira")
    if b <= -2:
        alerts.append(f"BANK CRASH - Bank Nifty {b:+.2f}% gira")
    if v >= 20 and vc >= 15:
        alerts.append(f"FEAR BADH RAHA - VIX {v:.1f} ({vc:+.1f}%)")
    if c >= 3:
        alerts.append(f"CRUDE TEZ - Crude {c:+.2f}% upar - Paint / Aviation pe dabav aa sakta hai")
    elif c <= -3:
        alerts.append(f"CRUDE GIRA - Crude {c:+.2f}% neeche - Paint / Aviation ko fayda ho sakta hai")
    if market.get("decline", 0) >= 8:
        alerts.append(f"POORA MARKET NEECHE - 10 bade stocks me se {market.get('decline')} neeche")
    return alerts


# ---------------- File kaam ----------------
def load_json_file(path):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def save_json_file(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_text_file(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def github_push_raw(path, text, message):
    # GitHub me save karo - token env se, code me koi secret nahi
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPO", "")
    if not token or not repo:
        return False
    try:
        content = base64.b64encode(text.encode()).decode()
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"}
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        sha = None
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as r:
                sha = json.loads(r.read().decode()).get("sha")
        except Exception:
            sha = None
        payload = {"message": message, "content": content}
        if sha:
            payload["sha"] = sha
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="PUT")
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status in (200, 201)
    except Exception:
        return False


def github_push(path, data, message):
    return github_push_raw(path, json.dumps(data, ensure_ascii=False, indent=2), message)


def send_telegram(msg):
    token = os.environ.get("TELEGRAM_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return False
    try:
        payload = json.dumps({"chat_id": str(chat), "text": msg}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.status == 200
    except Exception:
        return False


# ---------------- V2 NAYA: Data kitna taaza hai? ----------------
def check_freshness():
    # "Data current hai ya nahi" - yahi asli sawal hai, kahan se aaya ye nahi.
    # Har zaroori file ki umar napo - taaza hai to dikhao, purana hai to app dobara download karega.
    now = time.time()
    limit = AI_CONFIG["freshness_minutes"] * 60
    out = {"is_fresh": True, "files": [], "stale": []}
    watch = ["data/ai_live.json", "data/ai_memory.json", "data/IND_Master_FNO.csv", "data/IND_Universe_216.csv"]
    for p in watch:
        if os.path.exists(p):
            age_min = round((now - os.path.getmtime(p)) / 60, 1)
            fresh = age_min <= limit
            out["files"].append({"file": p, "age_min": age_min, "fresh": fresh})
            if not fresh:
                out["stale"].append(p)
        else:
            out["files"].append({"file": p, "age_min": None, "fresh": False})
            out["stale"].append(p + " (mila nahi)")
    # History - sabse nayi history file kitni purani hai
    newest = 0
    hist_dir = "data/history"
    if os.path.isdir(hist_dir):
        for root, _d, files in os.walk(hist_dir):
            for fn in files:
                if fn.endswith(".csv"):
                    try:
                        newest = max(newest, os.path.getmtime(os.path.join(root, fn)))
                    except Exception:
                        pass
    if newest:
        age_min = round((now - newest) / 60, 1)
        out["files"].append({"file": "data/history (sabse nayi)", "age_min": age_min, "fresh": age_min <= limit})
        if age_min > limit:
            out["stale"].append("data/history")
    out["is_fresh"] = len(out["stale"]) == 0
    out["message"] = "Data taaza hai" if out["is_fresh"] else "Data purana hai - " + ", ".join(out["stale"]) + " ko dobara download karna hai"
    return out


# ---------------- V2 NAYA: CSV History se Stock ki Direction ----------------
def _pick(row, names):
    for n in names:
        if n in row and row[n] not in (None, ""):
            return row[n]
    return None


def _to_float(x):
    try:
        return float(str(x).replace(",", "").strip())
    except Exception:
        return None


def load_stock_history(symbol):
    # data/history ke neeche wali CSV se is stock ke candle lao.
    # File ka format kuch bhi ho - symbol wala column ho ya file ka naam hi stock ka ho - dono chalega.
    symbol = str(symbol).upper().strip()
    candles = []
    hist_dir = "data/history"
    if not os.path.isdir(hist_dir):
        return []
    # Pehle file ke naam me stock dhoondho (tez rasta)
    candidates = []
    for root, _d, files in os.walk(hist_dir):
        for fn in files:
            if fn.endswith(".csv"):
                candidates.append(os.path.join(root, fn))
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    name_hit = [p for p in candidates if symbol in os.path.basename(p).upper()]
    # Naam se mila to wahi, nahi to nayi wali 40 file me symbol column dhoondho
    to_read = name_hit[:5] if name_hit else candidates[:40]
    for path in to_read:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    continue
                fn_lower = {str(k).strip().lower(): k for k in reader.fieldnames}
                has_sym = any(k in fn_lower for k in ("symbol", "stock", "scrip", "name"))
                for raw in reader:
                    row = {(str(k).strip().lower()): v for k, v in raw.items()}
                    if has_sym:
                        sv = str(_pick(row, ["symbol", "stock", "scrip", "name"]) or "").upper()
                        if symbol not in sv:
                            continue
                    c = _to_float(_pick(row, ["close", "ltp", "price", "last"]))
                    o = _to_float(_pick(row, ["open"]))
                    h = _to_float(_pick(row, ["high"]))
                    l = _to_float(_pick(row, ["low"]))
                    v = _to_float(_pick(row, ["volume", "vol", "qty"])) or 0.0
                    t = str(_pick(row, ["date", "time", "timestamp", "datetime", "day"]) or "")
                    if c is None:
                        continue
                    candles.append({"t": t, "o": o if o is not None else c, "h": h if h is not None else c,
                                    "l": l if l is not None else c, "c": c, "v": v})
            if candles and name_hit:
                break
        except Exception:
            continue
    candles = candles[-AI_CONFIG["history_candles"]:]
    return candles


def stock_direction_from_history(symbol, candles):
    # Candle se direction: VWAP ke upar/neeche + aakhri trend + range - yehi asli direction hai
    if not candles or len(candles) < 5:
        return {"symbol": symbol, "direction": "PATA NAHI", "reason": "History CSV me is stock ke kaafi candle nahi mile - pehle Download Data se history lao",
                "last": 0, "change_pct": 0, "support": 0, "resistance": 0, "vwap": 0, "candles": len(candles)}
    closes = [c["c"] for c in candles]
    last = closes[-1]
    first = closes[0]
    change_pct = round((last - first) / first * 100, 2) if first else 0.0
    tot_v = sum(c["v"] for c in candles)
    vwap = round(sum(c["c"] * c["v"] for c in candles) / tot_v, 2) if tot_v > 0 else round(sum(closes) / len(closes), 2)
    half = max(1, len(closes) // 2)
    trend = round(sum(closes[-half:]) / half - sum(closes[:half]) / half, 2)
    trend_pct = round(trend / closes[0] * 100, 2) if closes[0] else 0.0
    atr = round(sum(c["h"] - c["l"] for c in candles[-14:]) / min(14, len(candles)), 2)
    support = round(min(c["l"] for c in candles[-20:]), 2)
    resistance = round(max(c["h"] for c in candles[-20:]), 2)
    rng_pct = round((resistance - support) / last * 100, 2) if last else 0.0
    if last > vwap and trend > 0:
        direction, why = "UPAR", f"VWAP {vwap} ke upar hai aur trend +{trend_pct}% upar hai"
    elif last < vwap and trend < 0:
        direction, why = "NEECHE", f"VWAP {vwap} ke neeche hai aur trend {trend_pct}% neeche hai"
    elif rng_pct > 3:
        direction, why = "VOLATILE", f"Range {rng_pct}% bada hai - upar-neeche dono tez ho raha hai"
    else:
        direction, why = "SIDEWAYS", f"VWAP ke aas-paas hi ghoom raha hai, trend {trend_pct}%"
    return {"symbol": symbol, "direction": direction, "reason": why, "last": round(last, 2),
            "change_pct": change_pct, "support": support, "resistance": resistance,
            "vwap": vwap, "atr": atr, "range_pct": rng_pct, "candles": len(candles)}


# ---------------- V2 NAYA: Multi-Agent Team (TradingAgents jaisa, bina LLM ke bhi chalta hai) ----------------
def agent_technical(symbol, hist):
    # Technical Analyst - candle, VWAP, support/resistance se
    if hist.get("direction") == "PATA NAHI":
        return {"agent": "Technical", "verdict": "NEUTRAL", "score": 0, "reasons": [hist.get("reason", "")]}
    score = 0
    reasons = [hist["reason"]]
    if hist["direction"] == "UPAR":
        score += 40
    elif hist["direction"] == "NEECHE":
        score -= 40
    if hist["change_pct"] >= 2:
        score += 20
        reasons.append(f"History me {hist['change_pct']:+.2f}% ka move hai")
    elif hist["change_pct"] <= -2:
        score -= 20
        reasons.append(f"History me {hist['change_pct']:+.2f}% ka move hai")
    if hist["direction"] == "VOLATILE":
        score -= 10
        reasons.append("Volatile hai - bade move se bacho")
    reasons.append(f"Support {hist['support']} | Resistance {hist['resistance']} | VWAP {hist['vwap']}")
    verdict = "BULLISH" if score >= 30 else "BEARISH" if score <= -30 else "NEUTRAL"
    return {"agent": "Technical", "verdict": verdict, "score": score, "reasons": reasons}


def agent_news(symbol, news_list, memory):
    # News Analyst - is stock / iske sector ki khabar dhoondho
    related = []
    for n in news_list or []:
        title = str(n.get("title", ""))
        tl = title.lower()
        if symbol.lower() in tl:
            related.append(n)
            continue
        for sec, stocks in SECTOR_STOCKS.items():
            if symbol in stocks and n.get("type") == sec:
                related.append(n)
                break
    pos = sum(1 for n in related if n.get("direction") == "POSITIVE")
    neg = sum(1 for n in related if n.get("direction") == "NEGATIVE")
    score = (pos - neg) * 15
    reasons = []
    for n in related[:3]:
        reasons.append(f"{n.get('title', '')[:90]} ({n.get('direction', '')})")
    if not related:
        reasons.append("Is stock ki koi taaza khabar nahi mili")
    # Memory se - is type ki khabar ke baad pehle kya hua tha
    for p in (memory or {}).get("patterns", [])[:5]:
        if any(n.get("type") == p.get("type") for n in related):
            reasons.append("Pehla anubhav: " + p.get("text", ""))
    verdict = "BULLISH" if score > 0 else "BEARISH" if score < 0 else "NEUTRAL"
    return {"agent": "News", "verdict": verdict, "score": score, "reasons": reasons, "related_count": len(related)}


def agent_debate(tech, news):
    # Researcher Team - Bull vs Bear bahas
    bull = []
    bear = []
    if tech["verdict"] == "BULLISH":
        bull += tech["reasons"]
    elif tech["verdict"] == "BEARISH":
        bear += tech["reasons"]
    else:
        bull.append("Technical side se koi tez disha nahi")
        bear.append("Technical side se koi tez disha nahi")
    if news["verdict"] == "BULLISH":
        bull += news["reasons"]
    elif news["verdict"] == "BEARISH":
        bear += news["reasons"]
    total = tech["score"] + news["score"]
    winner = "BULL" if total > 10 else "BEAR" if total < -10 else "BARABAR"
    return {"agent": "Debate", "winner": winner, "score": total, "bull_points": bull[:4], "bear_points": bear[:4]}


def agent_risk(market, tech):
    # Risk Manager - kab trade rokna hai
    reasons = []
    allow = True
    vix = market.get("vix", 0)
    if vix and vix >= AI_CONFIG["risk"]["max_vix_trade"]:
        allow = False
        reasons.append(f"VIX {vix:.1f} zyada hai - bada jhatka aa sakta hai, isliye ruko")
    if market.get("nifty_change_pct", 0) <= AI_CONFIG["risk"]["crash_nifty_pct"]:
        allow = False
        reasons.append(f"Nifty {market.get('nifty_change_pct', 0):+.2f}% gira - crash jaisa mahaul, trade mat karo")
    if market.get("direction") == "BEARISH" and tech.get("verdict") == "BULLISH":
        reasons.append("Market neeche hai par stock upar - market ke khilaaf mat jao, chhota socho")
    if not reasons:
        reasons.append("Risk side se koi bada khatra nahi dikh raha")
    return {"agent": "Risk", "allow": allow, "reasons": reasons}


def agent_trader(symbol, tech, news, debate, risk):
    # Trader Agent - sab jod ke aakhri CALL (sirf jaankari, order kabhi nahi)
    if not risk["allow"]:
        return {"agent": "Trader", "call": "RUKO - TRADE MAT KARO", "reason": " | ".join(risk["reasons"])}
    if debate["winner"] == "BULL" and tech["verdict"] == "BULLISH":
        return {"agent": "Trader", "call": "UPAR KI TARAF DEKHO", "reason": "Technical + News dono upar ki taraf bol rahe hain - par apna SL / Target Scanner se lo"}
    if debate["winner"] == "BEAR" and tech["verdict"] == "BEARISH":
        return {"agent": "Trader", "call": "NEECHE KI TARAF DEKHO", "reason": "Technical + News dono neeche ki taraf bol rahe hain - par apna SL / Target Scanner se lo"}
    return {"agent": "Trader", "call": "SIDEWAYS - JALDI MAT KARO", "reason": "Disha saaf nahi hai - jab tak Scanner me setup na bane, haath mat lagao"}


def analyze_stock(symbol, news_list, memory, market):
    # Poori team ko ek stock pe chalao
    candles = load_stock_history(symbol)
    hist = stock_direction_from_history(symbol, candles)
    tech = agent_technical(symbol, hist)
    news = agent_news(symbol, news_list, memory)
    debate = agent_debate(tech, news)
    risk = agent_risk(market, tech)
    trader = agent_trader(symbol, tech, news, debate, risk)
    return {"symbol": symbol, "history": hist, "technical": tech, "news": news,
            "debate": debate, "risk": risk, "trader": trader}


# ---------------- V2 NAYA: Diary se seekhna ----------------
def learn_from_diary():
    # trades_diary/all_trades.csv - tumhare asli trade se seekho, andaze se nahi
    path = "trades_diary/all_trades.csv"
    lessons = []
    stats = {"total": 0, "wins": 0, "losses": 0, "win_pct": 0, "total_pnl": 0}
    if not os.path.exists(path):
        return stats, lessons
    try:
        with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return stats, lessons
        per_setup = defaultdict(lambda: {"total": 0, "wins": 0, "pnl": 0.0})
        for r in rows:
            row = {(str(k).strip().lower()): v for k, v in r.items()}
            pnl = _to_float(_pick(row, ["pnl", "profit", "pl", "profit_loss", "net_pnl"]))
            result = str(_pick(row, ["result", "win_loss", "outcome"]) or "").upper()
            setup = str(_pick(row, ["strategy", "setup", "pattern", "type"]) or "UNKNOWN").strip() or "UNKNOWN"
            stock = str(_pick(row, ["stock", "symbol", "scrip"]) or "")
            if pnl is None:
                if "WIN" in result or "PROFIT" in result:
                    pnl = 1.0
                elif "LOSS" in result or "LOSE" in result:
                    pnl = -1.0
                else:
                    continue
            stats["total"] += 1
            stats["total_pnl"] += pnl
            won = pnl > 0
            if won:
                stats["wins"] += 1
            else:
                stats["losses"] += 1
            per_setup[setup]["total"] += 1
            per_setup[setup]["pnl"] += pnl
            if won:
                per_setup[setup]["wins"] += 1
            per_setup[setup].setdefault("stocks", Counter())[stock] += 1
        if stats["total"]:
            stats["win_pct"] = round(stats["wins"] / stats["total"] * 100, 1)
            stats["total_pnl"] = round(stats["total_pnl"], 2)
        for setup, d in per_setup.items():
            if d["total"] >= 2:
                wp = round(d["wins"] / d["total"] * 100, 1)
                top_stock = d.get("stocks", Counter()).most_common(1)[0][0] if d.get("stocks") else ""
                word = "jeeta" if wp >= 50 else "haara"
                lessons.append(f"Diary: {setup} wala setup {d['total']} baar me {d['wins']} baar {word} ({wp}%)" + (f" - {top_stock} me sabse zyada" if top_stock else ""))
        lessons.sort()
    except Exception:
        pass
    return stats, lessons[:10]


# ---------------- V2 NAYA: LLM - ChatGPT jaisa polish (key ho to, nahi to niyam wala jawab) ----------------
def call_llm(prompt):
    # Key env se hi aayegi - code me kabhi nahi. Key nahi hai to None - niyam wala jawab chalega.
    key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""
    if not key:
        return None
    provider = (os.environ.get("LLM_PROVIDER") or ("gemini" if os.environ.get("GEMINI_API_KEY") and not os.environ.get("OPENAI_API_KEY") else "openai")).lower()
    try:
        if provider == "gemini":
            model = os.environ.get("LLM_MODEL", "gemini-2.0-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            body = {"contents": [{"parts": [{"text": prompt}]}]}
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as r:
                j = json.loads(r.read().decode())
            return (((j.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [{}])[0].get("text", "") or None
        model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        body = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 800}
        req = urllib.request.Request(f"{base}/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.loads(r.read().decode())
        return ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or None
    except Exception:
        return None


def resolve_question_stock(question):
    # Sawal me kaun sa stock hai - SBI likha to SBIN, REL likha to RELIANCE
    q = " " + str(question).upper() + " "
    for alias, sym in AI_CONFIG["aliases"].items():
        if f" {alias} " in q:
            return sym
    for sym in AI_CONFIG["watchlist"]:
        if f" {sym} " in q:
            return sym
    # Universe CSV se bhi dhoondho agar hai to
    try:
        if os.path.exists("data/IND_Universe_216.csv"):
            with open("data/IND_Universe_216.csv", "r", encoding="utf-8", errors="ignore", newline="") as f:
                for r in csv.DictReader(f):
                    s = str(r.get("STOCK") or r.get("Stock") or "").upper().strip()
                    if s and len(s) >= 3 and f" {s} " in q:
                        return s
    except Exception:
        pass
    return None


def answer_question(question, market=None, news_list=None, memory=None):
    # ChatGPT jaisa sawal-jawab - pehle tathya jama karo, phir jawab banao.
    # Tathya hamesha apne data se - LLM sirf bhasha sudharega, tathya nahi banayega.
    q = str(question or "").strip()
    if not q:
        return "Sawal khali hai - kisi stock ka naam likh ke poochho, jaise 'RELIANCE kidhar jayega?'"
    ql = q.lower()
    if market is None:
        try:
            market = fetch_market()
        except Exception:
            market = {}
    if news_list is None:
        news_list = []
    if memory is None:
        memory = load_json_file("data/ai_memory.json") or {"news": [], "patterns": []}
    symbol = resolve_question_stock(q)
    facts = []
    rule_answer = ""
    if symbol:
        report = analyze_stock(symbol, news_list, memory, market)
        h = report["history"]
        facts.append(f"{symbol}: Direction {h['direction']} - {h['reason']}. Last {h['last']}, Support {h['support']}, Resistance {h['resistance']}, VWAP {h['vwap']}.")
        facts.append(f"Technical: {report['technical']['verdict']} (score {report['technical']['score']}). News: {report['news']['verdict']}. Debate: {report['debate']['winner']}. Trader CALL: {report['trader']['call']}.")
        if "kyu" in ql or "kyon" in ql or "kyun" in ql or "kaisa" in ql or "haal" in ql:
            extra = " | ".join(report["news"]["reasons"][:2]) if report["news"]["reasons"] else "Koi taaza khabar nahi mili"
            rule_answer = (f"{symbol} abhi {h['direction']} disha me hai - {h['reason']}. Support {h['support']} aur Resistance {h['resistance']} hai. "
                           f"Khabar: {extra}. Trader ki rai: {report['trader']['call']} - {report['trader']['reason']}")
        elif "kharid" in ql or "buy" in ql or "lun" in ql or "lu" in ql or "lena" in ql:
            rule_answer = (f"{symbol} ke liye Trader ki rai: {report['trader']['call']}. Wajah: {report['trader']['reason']} "
                           f"Risk wale ne {'rok diya hai' if not report['risk']['allow'] else 'koi rok nahi lagayi'}. "
                           f"Entry / SL / Target Scanner se lo - ye AI sirf disha batata hai, order kabhi nahi lagata.")
        else:
            rule_answer = (f"{symbol} ki direction: {h['direction']} - {h['reason']}. Last {h['last']}, Support {h['support']}, Resistance {h['resistance']}. "
                           f"Technical {report['technical']['verdict']}, News {report['news']['verdict']}, Debate me {report['debate']['winner']} jeeta. "
                           f"Trader CALL: {report['trader']['call']}.")
    elif "nifty" in ql or "market" in ql or "bazaar" in ql or "vix" in ql:
        facts.append(f"Nifty {market.get('nifty', 0)} ({market.get('nifty_change_pct', 0):+.2f}%), Direction {market.get('direction')}, VIX {market.get('vix', 0)}, Advance {market.get('advance')}, Decline {market.get('decline')}.")
        rule_answer = (f"Market abhi {market.get('direction', 'PATA NAHI')} hai - Nifty {market.get('nifty', 0):.0f} ({market.get('nifty_change_pct', 0):+.2f}%), "
                       f"Bank Nifty {market.get('bank_nifty_change_pct', 0):+.2f}%, VIX {market.get('vix', 0):.1f}. "
                       f"10 bade stocks me {market.get('advance', 0)} upar, {market.get('decline', 0)} neeche hain.")
    elif "khabar" in ql or "news" in ql:
        top = [n.get("title", "") for n in (news_list or [])[:5]]
        rule_answer = "Taaza khabrein:\n" + ("\n".join("- " + t for t in top) if top else "- Abhi koi taaza khabar nahi mili")
    elif "diary" in ql or "mera trade" in ql or "kitna" in ql and "jeeta" in ql:
        stats, lessons = learn_from_diary()
        rule_answer = (f"Diary me kul {stats['total']} trade hain - {stats['wins']} jeete ({stats['win_pct']}%), kul P&L {stats['total_pnl']}. " +
                       ("Seekh: " + " | ".join(lessons) if lessons else "Abhi seekhne layak pattern nahi bana - aur trade likho."))
    else:
        rule_answer = ("Main trading wala AI hun - kisi stock ka naam le ke poochho, jaise 'RELIANCE kidhar jayega?', 'SBI ka kya haal hai?', 'Nifty kaisa hai?', 'Aaj ki khabar kya hai?'. "
                       "Main CSV History + News + Market + Diary se jawab dunga. Order main kabhi nahi lagata.")
    # LLM key hai to isi tathya se jawab ko sudharwao - tathya bahar se nahi aayega
    if facts:
        llm = call_llm("Tu ek Indian stock market trading assistant hai. Neeche diye TATHYON se bahar mat jao, koi naya number mat banao. "
                       "Hindi/Hinglish me, chhota aur saaf jawab do. Order lagane ki salah mat do, sirf jaankari do.\nTATHYA:\n" + "\n".join(facts) +
                       f"\nSAWAL: {q}")
        if llm:
            return llm.strip()
    return rule_answer


# ---------------- Memory: News ka asar + seekhna ----------------
def update_memory(memory, news_list, market):
    # Pichhli khabar ka asar napo - 1 ghanta ho gaya ho to Nifty ab vs khabar ke waqt ka Nifty
    # Memory kabhi delete nahi hogi - sirf judti jayegi
    if memory is None:
        memory = {"news": [], "patterns": []}
    seen_titles = {str(n.get("title", "")) for n in memory.get("news", [])}
    now = datetime.now(IST)
    now_s = now.strftime("%Y-%m-%d %H:%M:%S")
    nifty_now = market.get("nifty", 0)
    for n in news_list:
        if n["title"] not in seen_titles:
            memory["news"].append({
                "title": n["title"], "type": n["type"], "direction": n["direction"],
                "time": now_s, "nifty_at_news": nifty_now, "outcome": "", "nifty_after_1h": None,
            })
    # Purani khabar jiska outcome nahi hai, 1 ghanta ho gaya - outcome bharo
    for n in memory.get("news", []):
        if n.get("outcome"):
            continue
        try:
            t = datetime.strptime(n.get("time", ""), "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
            if (now - t).total_seconds() < 3600:
                continue
            base = float(n.get("nifty_at_news") or 0)
            if base and nifty_now:
                move = (nifty_now - base) / base * 100
                n["outcome"] = "UP" if move >= 0.3 else "DOWN" if move <= -0.3 else "FLAT"
                n["nifty_after_1h"] = nifty_now
                n["move_pct"] = round(move, 2)
        except Exception:
            continue
    # Pattern banao - is type ki khabar ke baad aksar kya hua
    by_type = defaultdict(list)
    for n in memory.get("news", []):
        if n.get("outcome"):
            by_type[n["type"]].append(n["outcome"])
    patterns = []
    for t, outs in by_type.items():
        if len(outs) >= 2:
            c = Counter(outs)
            top, cnt = c.most_common(1)[0]
            pct = round(cnt / len(outs) * 100)
            word = "upar gaya" if top == "UP" else "neeche gaya" if top == "DOWN" else "wahi raha"
            patterns.append({
                "type": t,
                "text": f"{t} wali khabar ke baad Nifty {len(outs)} me se {cnt} baar ({pct}%) {word}",
                "count": len(outs),
            })
    patterns.sort(key=lambda x: -x["count"])
    memory["patterns"] = patterns[:20]
    # Memory bahut badi na ho - sirf aakhri 2000 khabar rakho, pattern sab rahega
    if len(memory.get("news", [])) > 2000:
        memory["news"] = memory["news"][-2000:]
    memory["updated_at"] = now_s
    return memory


# ---------------- Daily Brief - ek page ka Hindi summary ----------------
def build_daily_brief(market, crash_alerts, news_list, stock_reports, diary_stats, diary_lessons, freshness):
    now_s = datetime.now(IST).strftime("%d %b %Y, %H:%M")
    lines = [f"# Aaj ka Market Brief - {now_s}", ""]
    lines.append(f"**Market:** {market.get('direction', '')} - Nifty {market.get('nifty', 0):.0f} ({market.get('nifty_change_pct', 0):+.2f}%), Bank Nifty {market.get('bank_nifty_change_pct', 0):+.2f}%, VIX {market.get('vix', 0):.1f}")
    lines.append(f"**Data:** {freshness.get('message', '')}")
    lines.append("")
    if crash_alerts:
        lines.append("**ALERT:**")
        for a in crash_alerts:
            lines.append(f"- {a}")
        lines.append("")
    lines.append("**Taaza Khabar:**")
    for n in (news_list or [])[:6]:
        lines.append(f"- [{n.get('type', '')} / {n.get('direction', '')}] {n.get('title', '')}")
    if not news_list:
        lines.append("- Koi taaza khabar nahi mili")
    lines.append("")
    lines.append("**Bade Stocks ki Direction (CSV History se):**")
    for sym, rep in (stock_reports or {}).items():
        h = rep.get("history", {})
        lines.append(f"- {sym}: {h.get('direction', '')} - Last {h.get('last', 0)}, Support {h.get('support', 0)}, Resistance {h.get('resistance', 0)} | Trader: {rep.get('trader', {}).get('call', '')}")
    lines.append("")
    lines.append(f"**Diary se Seekh:** {diary_stats.get('total', 0)} trade, {diary_stats.get('wins', 0)} jeete ({diary_stats.get('win_pct', 0)}%), P&L {diary_stats.get('total_pnl', 0)}")
    for les in (diary_lessons or [])[:5]:
        lines.append(f"- {les}")
    lines.append("")
    lines.append("_Ye AI sirf jaankari deta hai - order kabhi nahi lagata._")
    return "\n".join(lines)


# ---------------- Ek run - sab kuch ----------------
def run_once():
    # 1) News - saare RSS se
    all_news = []
    seen = set()
    for feed in RSS_FEEDS:
        for it in fetch_rss(feed):
            title = it["title"]
            if title in seen:
                continue
            seen.add(title)
            ntype, direction, impact = classify_news(title)
            all_news.append({"title": title[:200], "link": it.get("link", ""), "type": ntype, "direction": direction, "impact": impact})
    all_news = all_news[:30]
    # 2) Market - Direction + Crash
    market = fetch_market()
    crash_alerts = detect_crash(market)
    # 3) Memory - seekhna
    memory = load_json_file("data/ai_memory.json") or {"news": [], "patterns": []}
    # GitHub se bhi memory lao agar local khali hai
    if not memory.get("news"):
        repo = os.environ.get("GITHUB_REPO", "")
        if repo:
            try:
                req = urllib.request.Request(f"https://raw.githubusercontent.com/{repo}/main/data/ai_memory.json", headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    memory = json.loads(r.read().decode())
            except Exception:
                pass
    memory = update_memory(memory, all_news, market)
    # 4) V2 - Data taaza hai ya nahi
    freshness = check_freshness()
    # 5) V2 - Watchlist pe poori Agent Team chalao (CSV History se direction)
    stock_reports = {}
    for sym in AI_CONFIG["watchlist"]:
        try:
            stock_reports[sym] = analyze_stock(sym, all_news, memory, market)
        except Exception as e:
            stock_reports[sym] = {"symbol": sym, "error": str(e)}
    # 6) V2 - Diary se seekhna
    diary_stats, diary_lessons = learn_from_diary()
    # 7) V2 - Daily Brief
    brief = build_daily_brief(market, crash_alerts, all_news, stock_reports, diary_stats, diary_lessons, freshness)
    # 8) Live + Knowledge file banao - app ka AI Chat inhi se jawab dega
    now_s = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    live = {
        "updated_at": now_s,
        "worker_version": AI_CONFIG["version"],
        "market": market,
        "crash_alerts": crash_alerts,
        "news": all_news,
        "freshness": freshness,
        "stock_reports": stock_reports,
        "diary_stats": diary_stats,
        "diary_lessons": diary_lessons,
    }
    knowledge = {
        "updated_at": now_s,
        "patterns": memory.get("patterns", []),
        "diary_stats": diary_stats,
        "diary_lessons": diary_lessons,
        "stock_direction": {s: {"direction": r.get("history", {}).get("direction", ""), "last": r.get("history", {}).get("last", 0),
                               "support": r.get("history", {}).get("support", 0), "resistance": r.get("history", {}).get("resistance", 0),
                               "call": r.get("trader", {}).get("call", "")} for s, r in stock_reports.items()},
        "market": market,
        "freshness": freshness,
    }
    save_json_file("data/ai_live.json", live)
    save_json_file("data/ai_memory.json", memory)
    save_json_file("data/ai_knowledge.json", knowledge)
    save_text_file("data/ai_brief.md", brief)
    github_push("data/ai_live.json", live, f"AI Live {now_s}")
    github_push("data/ai_memory.json", memory, f"AI Memory {now_s}")
    github_push("data/ai_knowledge.json", knowledge, f"AI Knowledge {now_s}")
    github_push_raw("data/ai_brief.md", brief, f"AI Brief {now_s}")
    # 9) Crash / badi khabar ho to Telegram - bina bole bhi pata chalega
    if crash_alerts:
        msg = "AI ALERT - " + datetime.now(IST).strftime("%d %b %H:%M") + "\n" + "\n".join(crash_alerts)
        msg += f"\nNifty {market.get('nifty', 0):.0f} ({market.get('nifty_change_pct', 0):+.2f}%) | VIX {market.get('vix', 0):.1f}"
        send_telegram(msg)
    print(f"AI Worker V2 chala - {now_s} - News {len(all_news)} - Crash {len(crash_alerts)} - Direction {market.get('direction')} - Stocks {len(stock_reports)} - Data: {freshness.get('message', '')}")
    return live


def run_learn():
    # Bazaar band ke baad wala run - sirf seekhna, news nahi
    memory = load_json_file("data/ai_memory.json") or {"news": [], "patterns": []}
    market = fetch_market()
    memory = update_memory(memory, [], market)
    diary_stats, diary_lessons = learn_from_diary()
    save_json_file("data/ai_memory.json", memory)
    knowledge = load_json_file("data/ai_knowledge.json") or {}
    knowledge.update({"updated_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
                      "patterns": memory.get("patterns", []), "diary_stats": diary_stats, "diary_lessons": diary_lessons})
    save_json_file("data/ai_knowledge.json", knowledge)
    github_push("data/ai_memory.json", memory, "AI Learn - Memory")
    github_push("data/ai_knowledge.json", knowledge, "AI Learn - Knowledge")
    print(f"AI Learn ho gaya - Diary {diary_stats.get('total', 0)} trade, {diary_stats.get('wins', 0)} jeete, Patterns {len(memory.get('patterns', []))}")
    return knowledge


def main():
    if "--ask" in sys.argv:
        i = sys.argv.index("--ask")
        q = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
        print(answer_question(q))
        return
    if "--learn" in sys.argv:
        run_learn()
        return
    if "--brief" in sys.argv:
        live = load_json_file("data/ai_live.json") or {}
        market = live.get("market", {}) or fetch_market()
        brief = build_daily_brief(market, live.get("crash_alerts", []), live.get("news", []),
                                  live.get("stock_reports", {}), live.get("diary_stats", {}),
                                  live.get("diary_lessons", []), live.get("freshness", {}))
        save_text_file("data/ai_brief.md", brief)
        print(brief)
        return
    if "--once" in sys.argv:
        run_once()
        return
    print("AI Worker V2 hamesha chalega - har 15 min me check karega. Band karne ke liye Ctrl+C.")
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"AI Worker error - {e}")
        time.sleep(900)  # 15 min


if __name__ == "__main__":
    main()
