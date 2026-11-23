# ai_worker.py - AI Worker - Hamesha chalta rahega, bina bole
# Kaam: Market ka saara News + Direction + Crash + Impact - sab dekh ke data/ai_live.json me likhega
# Aur pichhle News se seekh ke data/ai_memory.json me yaad rakhega - "Pichhli baar aisa hua to kya hua"
#
# Chalane ke 2 tareeke (dono me koi secret code me nahi hai - sab env se aayega):
#  1) Laptop pe:  python ai_worker.py  (hamesha chalega, har 15 min me check karega)
#  2) GitHub Actions: .github/workflows/ai_worker.yml - har 15 min me apne aap chalega, bina bole
#
# Seekhna Diary wale jeet-haar se nahi hai - News ke baad Market me kya hua, usse seekhega.
# Jaise: "Crude tez wali khabar ke baad Paint stocks 1 ghante me neeche gaye" - ye yaad rahega.

import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

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
    "AUTO": ["auto", "maruti", "tata motors", "mahindra", "bajaj auto", "hero moto", "ev"],
    "POWER": ["power", "ntpc", "adani power", "tata power", "suzlon", "renewable", "solar"],
    "METAL": ["metal", "steel", "hindalco", "tata steel", "jsw steel", "coal", "vedanta"],
    "GLOBAL": ["dow jones", "nasdaq", "s&p", "wall street", "china", "us market", "europe"],
    "FII_DII": ["fii", "dii", "foreign investor", "fii buying", "fii selling"],
    "GEOPOLITICAL": ["war", "attack", "border", "sanction", "tariff", "trade war"],
}

# Is type ki khabar ka kiske upar asar hota hai
IMPACT_MAP = {
    "RBI": "Bank, NBFC, Auto, Realty pe asar - Rate badha to Bank upar, Auto neeche",
    "FED": "IT, Bank, Export wale stocks pe asar",
    "CRUDE": "Oil, Paint, Aviation, Tyre pe asar - Crude tez to Paint/Aviation neeche",
    "EARNINGS": "Usi company + uske sector pe asar",
    "IT": "TCS, Infosys, Wipro, HCL Tech pe asar",
    "BANK": "HDFC, ICICI, SBI, Axis, Kotak pe asar",
    "PHARMA": "Sun Pharma, Cipla, Divis pe asar",
    "AUTO": "Maruti, Tata Motors, Mahindra, Bajaj Auto pe asar",
    "POWER": "NTPC, Power, Suzlon pe asar",
    "METAL": "Hindalco, Tata Steel, JSW Steel pe asar",
    "GLOBAL": "Poora market pe asar - Nifty khulne pe gap de sakta hai",
    "FII_DII": "Poora market pe asar - FII bech raha to market neeche",
    "GEOPOLITICAL": "Poora market + Crude + Gold pe asar",
    "OTHER": "Usi stock / sector pe asar",
}

POS_WORDS = ["rate cut", "cut", "growth", "profit", "record", "rally", "rise", "surge", "positive", "deal", "order", "approval", "buying", "bullish", "upgrade"]
NEG_WORDS = ["rate hike", "hike", "fall", "drop", "crash", "crisis", "war", "inflation", "recession", "loss", "selling", "bearish", "downgrade", "fraud", "scam", "penalty"]


def fetch_rss(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
        root = ET.fromstring(data)
        items = []
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            pub = (it.findtext("pubDate") or "").strip()
            if title:
                items.append({"title": title, "link": link, "pubDate": pub})
        return items
    except Exception:
        return []


def classify_news(title):
    low = title.lower()
    ntype = "OTHER"
    for t, words in TYPE_KEYWORDS.items():
        if any(w in low for w in words):
            ntype = t
            break
    pos = sum(1 for w in POS_WORDS if w in low)
    neg = sum(1 for w in NEG_WORDS if w in low)
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
    # Breadth - 10 bade stocks me kitne upar, kitne neeche
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


def github_push(path, data, message):
    # GitHub me save karo - token env se, code me koi secret nahi
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPO", "")
    if not token or not repo:
        return False
    try:
        content = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode()
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
    from collections import Counter, defaultdict
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
    # 4) Live file banao
    live = {
        "updated_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
        "market": market,
        "crash_alerts": crash_alerts,
        "news": all_news,
    }
    save_json_file("data/ai_live.json", live)
    save_json_file("data/ai_memory.json", memory)
    github_push("data/ai_live.json", live, f"AI Live {live['updated_at']}")
    github_push("data/ai_memory.json", memory, f"AI Memory {live['updated_at']}")
    # 5) Crash / badi khabar ho to Telegram - bina bole bhi pata chalega
    if crash_alerts:
        msg = "AI ALERT - " + datetime.now(IST).strftime("%d %b %H:%M") + "\n" + "\n".join(crash_alerts)
        msg += f"\nNifty {market.get('nifty', 0):.0f} ({market.get('nifty_change_pct', 0):+.2f}%) | VIX {market.get('vix', 0):.1f}"
        send_telegram(msg)
    print(f"AI Worker chala - {live['updated_at']} - News {len(all_news)} - Crash {len(crash_alerts)} - Direction {market.get('direction')}")
    return live


def main():
    if "--once" in sys.argv:
        run_once()
        return
    print("AI Worker hamesha chalega - har 15 min me check karega. Band karne ke liye Ctrl+C.")
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"AI Worker error - {e}")
        time.sleep(900)  # 15 min


if __name__ == "__main__":
    main()
